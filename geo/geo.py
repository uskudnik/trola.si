#!/usr/bin/python
#! -*- encoding: utf-8 -*-

import sys
import os
import pickle
import csv
from bisect import bisect_left
from operator import itemgetter

from imposm.parser import OSMParser
from scipy.spatial import KDTree
import networkx

OSM_file = "slovenia.osm.pbf"
STATIONS_ON_ROUTES_FILES = "./stations_on_route.csv"


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
            self.reload()

        self.stations = sorted(
            pickle.load(open("lpp-station-geo-data.pypickle", "r")),
            key=itemgetter(1))

        self.stations_new_numbers = [station[0] for station in self.stations]
        self.stations_old_numbers = [station[1] for station in self.stations]
        self.postaje = pickle.load(open("lpp-stations.pypickle", "r"))
        self.postaje_dict = pickle.load(open("lpp-station-connections.pypickle", "r"))

        latlng_stations = [station[3] for station in self.stations]
        self.kdtree = KDTree(latlng_stations)

        self.graph = networkx.DiGraph()
        self.graph.add_nodes_from(self.postaje)

        for p in self.postaje_dict:
            postaja = self.postaje_dict[p]
            self.graph.node[p]['linije'] = postaja['bus']
            next = postaja['next']
            for np in next:
                self.graph.add_edge(p, np)

    def find_k_nearest(self, latlng, k=10):
        kdq = self.kdtree.query(latlng, k=k)
        # [(distance, station), ...]
        outlist = list()
        for x in xrange(k):
            outlist += [(latlng_to_m(kdq[0][x]), self.stations[kdq[1][x]])]
        return outlist

    def get_station(self, number):
        return self.stations[binary_search(self.stations_old_numbers, number)]

    def from_to(self, startpoint, endpoint):
        if type(startpoint) is str:
            # find station
            pass
        if type(endpoint) is str:
            pass

        # shortest_paths = networkx.shortest_path(self.graph, source=startpoint, target=endpoint)
        shortest_paths = networkx.all_shortest_paths(self.graph, source=startpoint, target=endpoint)

        return shortest_paths
        # for station in shortest_path:
        #     try:
        #         print self.get_station(station)[2]
        #     except ValueError:
        #         print "Station not found, ID: ", station
        # return shortest_path

    def reload(self):
        self.reload_position_data()

        self.reload_graph_data()

    def reload_position_data(self):
        print "Reloading (OSM) position data"
        osm_stations = BusStationGetter()
        p = OSMParser(concurrency=4, nodes_callback=osm_stations.nodes)
        p.parse(OSM_file)

        osm_stations = sorted(osm_stations.stations, key=itemgetter(0))
        lpp_stations = sorted(get_lpp_stations(), key=itemgetter(0))
        stations = get_coordinates_for_stations(lpp_stations, osm_stations)
        pickle.dump(stations, open("lpp-station-geo-data.pypickle", "wb"))
        print "Reloaded position data"

    def reload_graph_data(self, data_file=STATIONS_ON_ROUTES_FILES):
        print "Reloading graph data"

        with open(data_file, "r") as csvfile:
            route_reader = csv.reader(csvfile, delimiter=';')
            proge = dict()
            bze = 0

            postaje = list()  # nodes
            for row in route_reader:
                # print row
                proga, ime_proge, st_proge, vrstni_red, ime_postaje, st_postaje = row
                if not bze:
                    proga = proga.split("\xef\xbb\xbf")[1]
                    bze = 1
                stop_strings = ["Semaforji", "Semafor", "Satnerjeva Z01", "Sattnerjeva Z02", "Opekarska Z02", "Opekarska Z01", "p2", "g02", "os2", "os1", "G01", "p1", '']
                if st_postaje in stop_strings or ime_postaje in stop_strings:
                    continue
                proga, st_proge, vrstni_red, st_postaje = \
                    proga, int(st_proge), int(vrstni_red), int(st_postaje)
                if st_proge != '':
                    if not st_proge in proge:
                        proge[st_proge] = set()
                    postaje += [st_postaje]  # nodes
                    proge[st_proge].add((proga, vrstni_red, st_postaje))

            postaje_dict = dict()

            for st_proge, proga in proge.items():
                # st_proge, proga = kv
                proga = sorted(proga, key=itemgetter(1))

                for i, kv in enumerate(proga):
                    linija, vrstni_red, postaja = kv
                    if not postaja in postaje_dict:
                        postaje_dict[postaja] = {
                            'next': [],
                            'prev': [],
                            'bus': []
                        }
                    try:
                        prev_station = proga[i - 1]
                        postaje_dict[postaja]['prev'] += [prev_station[2]]
                    except IndexError:
                        prev_station = None

                    try:
                        next_station = proga[i + 1]
                        postaje_dict[postaja]['next'] += [next_station[2]]
                    except IndexError:
                        next_station = None

                    if not linija in postaje_dict[postaja]['bus']:
                        postaje_dict[postaja]['bus'] += [linija]

            pickle.dump(postaje, open("lpp-stations.pypickle", "wb"))
            pickle.dump(postaje_dict, open("lpp-station-connections.pypickle", "wb"))
            print "Reloaded graph data"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'reload':
        geo = GeoSys(reload_data=True)
        exit()
    geo = GeoSys()

    # slovenija avto to astra
    print "Shortest path:"
    shortest_paths = geo.from_to(43, 29)
    for path in shortest_paths:
        oo = []
        for s in path:
            try:
                oo += [geo.get_station(s)[2]]
            except ValueError:
                oo += [str(s)]
        print " - ".join(oo)

    print "\n" * 2
    print "Find 10 nearest stations (with distance):"

    print """Slovenija avto:  [803012, 93, 'Slovenija avto', (14.486484600000127, 46.07392840000003)]
Kneza Koclja:  [803082, 124, 'Kneza Koclja', (14.480646500000148, 46.07146660000009)]"""

    mk30 = (14.48203150, 46.07096130)
    print "Searching near: ", mk30

    nstations = geo.find_k_nearest(mk30)

    for distance, station in nstations:
        print "dist: %sm, station name: %s" % (int(distance), station)



