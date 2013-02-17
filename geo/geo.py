#!/usr/bin/python
#! -*- encoding: utf-8 -*-

import sys
import os
import pickle
from bisect import bisect_left
from operator import itemgetter

from imposm.parser import OSMParser
from scipy.spatial import KDTree

OSM_file = "slovenia.osm.pbf"

# prvi priblizek al neki, TODO find a proper formula
latlng_to_m = lambda x: (79059.912289 + 98966.2121133 + 87476.3735091) / 3 * x


def binary_search(a, x):
    # array, element to find
    i = bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i
    raise ValueError


def get_lpp_stations():
    busstations = open('lpp-postaje.txt', "r").readlines()

    stations = []

    def name_cleaner(name):
        return name.split("\n")[0]

    for st in xrange(0, len(busstations), 3):
        stara_st = busstations[st + 0]
        nova_st = busstations[st + 1]
        ime = busstations[st + 2]

        station = [int(nova_st), int(stara_st), name_cleaner(ime)]
        stations += [station]

    return stations


class BusStationGetter(object):
    stations = []

    def nodes(self, nodes):
        # callback method for nodes
        for osmid, tags, latlng in nodes:
            # print tags
            if 'highway' in tags:
                if tags['highway'] == 'bus_stop':
                    if 'name' in tags:
                        name = tags['name']
                        try:
                            int(name[:6])
                            num, name = name.split(" ~ ")
                            self.stations += [[int(num), name, latlng]]
                        except ValueError:
                            pass


def get_coordinates_for_stations(lpp_stations, osm_stations):
    nf = 0
    to_delete = list()
    osm_stations_indexes = [num for num, name, latlong in osm_stations]

    for i, station in enumerate(lpp_stations):
        numn, numo, name = station

        try:
            n = binary_search(osm_stations_indexes, numn)
            station += [osm_stations[n][2]]
        except ValueError:
            nf += 1
            to_delete += [i]
            # print "Coordinates not found: ", num, name

    print "Got %s station coordinates, missing: %s" % (len(lpp_stations), nf)

    # this is prototype, lets just look at what we know is good
    return [station for i, station in enumerate(lpp_stations) if i not in to_delete]


class GeoSys:
    def __init__(self, reload_data=False):
        if not os.path.exists("lpp-station-geo-data.pypickle") or\
                reload_data:
            self.reload_data()

        self.stations = pickle.load(open("lpp-station-geo-data.pypickle", "r"))
        latlng_stations = [station[3] for station in self.stations]
        self.kdtree = KDTree(latlng_stations)

    def find_k_nearest(self, latlng, k=10):
        kdq = self.kdtree.query(latlng, k=k)
        # [(distance, station), ...]
        outlist = list()
        for x in xrange(k):
            outlist += [(latlng_to_m(kdq[0][x]), self.stations[kdq[1][x]])]
        return outlist

    def reload_data(self):
        print "Reloading data"
        osm_stations = BusStationGetter()
        p = OSMParser(concurrency=4, nodes_callback=osm_stations.nodes)
        p.parse(OSM_file)

        osm_stations = sorted(osm_stations.stations, key=itemgetter(0))
        lpp_stations = sorted(get_lpp_stations(), key=itemgetter(0))
        stations = get_coordinates_for_stations(lpp_stations, osm_stations)
        pickle.dump(stations, open("lpp-station-geo-data.pypickle", "wb"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'reload':
        geo = GeoSys(reload_data=True)
        exit()
    geo = GeoSys()

    print """Slovenija avto:  [803012, 93, 'Slovenija avto', (14.486484600000127, 46.07392840000003)]
Kneza Koclja:  [803082, 124, 'Kneza Koclja', (14.480646500000148, 46.07146660000009)]"""

    mk30 = (14.48203150, 46.07096130)
    print "Searching near: ", mk30

    nstations = geo.find_k_nearest(mk30)

    for distance, station in nstations:
        print "dist: %sm, station name: %s" % (int(distance), station[2])
