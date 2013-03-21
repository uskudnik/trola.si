#! -*- encoding: utf-8 -*-
#!/usr/bin/python

import csv
import re

sbyr = "stations-by-route-org.csv"

station_number = re.compile("[0-9]{6}")
ROUTE_SEPARATOR = "----" * 10

ROUTE_COUNT = 0
next_line_name = False


# def route_name_cleanup(route_name):
#     route_name = route_name.split("-")
#     route_name = [x.strip() for x in route_name]
#     if len(route_name) == 2:
#         return " - ".join([route_name[1], route_name[0]])
#     if len(route_name) == 3:
#         return " - ".join([route_name[2], route_name[1], route_name[0]])

route_1, route_2 = list(), list()


def write_route_to_file(route):
    with open("stations-on-route.csv", "a") as csvf:
        csvwriter = csv.writer(csvf)
        csvwriter.writerows(route)
    csvf.close()

with open(sbyr, 'r') as csvfile:
    stationreader = csv.reader(csvfile)
    station_num = 1
    for row in stationreader:
        if row[0] == ROUTE_SEPARATOR or row[0] == "\xef\xbb\xbf" + "----" * 10:
            next_line_name = True
            ROUTE_COUNT += 1
            station_num = 1
            write_route_to_file(route_1)
            write_route_to_file(route_2)
            route_1, route_2 = [], []
            continue

        if next_line_name:
            route_num, route_name, x, y = row
            # Used during data cleanup
            # if route_name_cleanup(route_name2) != route_name1:
                # print 'Route name not the same'
                # print route_name1, route_name2
            # else:
            #     print route_name1
            next_line_name = False
            continue

        # print row
        route_num1, route_name1, route_num2, route_name2 = row
        if route_num1 != "":
            route_1 += [(route_num, route_name, station_num, route_num1, route_name1)]
        if route_num2 != "":
            route_2 += [(route_num, route_name, station_num, route_num2, route_name2)]
        station_num += 1
print ROUTE_COUNT
