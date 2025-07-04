#!/usr/bin/env python3
import datetime
import os
import sys
from typing import List
from urllib.parse import urlparse, urlunparse, urljoin
import json

import requests_html
from os.path import exists
from shutil import move
from hashlib import md5
import configparser
import networkx as nx
session = requests_html.HTMLSession()
import argparse
parser = argparse.ArgumentParser()


class Echo:
    def __init__(self):
        self.streams = []

    def write(self, message):
        for stream in self.streams:
            stream.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass

    def close(self):
        for stream in self.streams:
            if stream is not sys.stdout:
                stream.close()

def convert2cytoscapeJSON(G):
    # load all nodes into nodes array
    final = {}
    final["nodes"] = []
    final["edges"] = [] 
    for node in G.nodes():
        nx = {}
        nx["data"] = {}
        nx["data"]["id"] = node
        nx["data"]["label"] = node
        final["nodes"].append(nx.copy())
    #load all edges to edges array
    for edge in G.edges():
        nx = {}
        nx["data"]={}
        nx["data"]["id"]=edge[0]+edge[1]
        nx["data"]["source"]=edge[0]
        nx["data"]["target"]=edge[1]
        final["edges"].append(nx)
    return json.dumps(final)


def get_page_hash(text: str):
    text = text.replace(' ', '').replace('\r', '').replace('\n', '')

    return md5(text.encode('utf-8')).hexdigest()


def make_postfix(parse_result, base_parse, current_href):
    postfix = parse_result.path
    if parse_result.query:
        postfix += "?" + parse_result.query

    if len(postfix) == 0:
        postfix = "/"
    
    if parse_result.hostname != base_parse.hostname:
        postfix = current_href

    return postfix


def is_member_of_target(parse_result, base_parse, postfix):
    return parse_result.hostname == base_parse.hostname and base_parse.path in postfix


def is_excluded(exclude, postfix):
    for prefix in exclude:
        if postfix[:len(prefix)] == prefix:
            return True
        
    return False


def spider(target, exclude, create_network):
    network = None
    if create_network:
        network = nx.DiGraph()
    parsed_target = urlparse(target)
    return spider_rec(dict(), dict(), target, parsed_target, exclude, network, [])


def spider_rec(links, checksums, current_href, base_parse, exclude, network, process_status):
    target_url = urlunparse(base_parse)
    parse_result = urlparse(urljoin(target_url, current_href))
    
    postfix = make_postfix(parse_result, base_parse, current_href)

    if is_excluded(exclude, postfix):
        return None

    if postfix in process_status:
        return None
    else:
        process_status.append(postfix)
    
    if is_member_of_target(parse_result, base_parse, postfix):
        r = session.get(urlunparse(parse_result))
        
        hrefs = r.html.absolute_links
        try:
            r.html.render(timeout=15)
        except Exception:
            pass
        else:
            hrefs = r.html.absolute_links

        checksums[postfix] = get_page_hash(r.html.text)
        links[postfix] = 1
        if network is not None:
            network.add_node(postfix)

        for href in hrefs:
            if "mailto:" not in href:
                href_parse = urlparse(urljoin(target_url, href))
                href = make_postfix(href_parse, base_parse, href)

                spider_rec(links, checksums, href, base_parse, exclude, network, process_status)

                if is_member_of_target(href_parse, base_parse, href) and not is_excluded(exclude, href):
                    if network is not None:
                        network.add_edge(postfix, href)

                    links[href] += 1

    return links, checksums, network


def cmp(p1, p2):
    with open(p1, 'r') as f1:
        with open(p2, 'r') as f2:
            l1 = f1.readlines()
            l2 = f2.readlines()
            if len(l1) == len(l2):
                for i in range(len(l1)):
                    if l1[i] != l2[i]:
                        return False
            else:
                return False

    return True


def main(args):
    args.create_network = args.create_network and args.to_stdout

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if not args.custom:
        print("Reading conf...")

        config = configparser.ConfigParser()
        config.read('crawl.conf')
        config = config['Config']

        target = config['site']
        path = config['target']
        checksums_path = config['checksums']

        ignores = config['ignore'].split(', ')
    else:
        target = args.site
        path = args.target
        checksums_path = args.checksums
        ignores = args.ignores.split(',')

    checksums = dict()
    try:
        with open(checksums_path, 'r') as checksums_file:
            for line in checksums_file.readlines():
                thirds = line.split()
                checksums[thirds[0]] = thirds[1:]
    except FileNotFoundError:
        print("No checksums file found at path, new file will be created.")

    print("Crawling site...")
    links, new_checksums, network = spider(target, ignores, args.create_network)
    date = datetime.datetime.utcnow()

    print("Writing to target file...")
    echoer = Echo()
    if args.to_stdout:
        echoer.streams.append(sys.stdout)
    
    if args.target:
        existed = exists(path)
        oldpath = path
        if existed:
            print("Sitemap already exists, creating temp...")
            path = "newmap.xml"

        echoer.streams.append(open(path, 'w'))
    
    out = echoer
    out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
    out.write("<!--\n")
    out.write("\tSitemap generator by Ben Morgan - www.benrmorgan.com\n")
    out.write("-->\n")
    out.write("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")

    sorted_links = dict(sorted(links.items(), key=lambda item: item[1], reverse=True))

    ordered = []
    level = 0
    old_num = sorted_links[list(sorted_links.keys())[0]]
    for l in sorted_links.keys():
        if sorted_links[l] != old_num:
            level += 1
            old_num = sorted_links[l]

        ordered.append((l, str(float(str(round(pow(0.8, level), 2))))))

    checksums_out = open(checksums_path, 'w')

    different_count = 0
    for l in ordered:
        lastmod = date.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        if l[0] in checksums.keys() and checksums[l[0]][0] == new_checksums[l[0]]:
            lastmod = checksums[l[0]][1]
        else:
            different_count += 1
        
        checksums_out.write(f"{l[0]} {new_checksums[l[0]]} {lastmod}\n")
        
        if l[0] == '/':
            l = (target + l[0], l[1])

        out.write("\t<url>\n")
        out.write("\t\t<loc>" + l[0] + "</loc>\n")
        out.write("\t\t<lastmod>" + lastmod + "</lastmod>\n")
        out.write("\t\t<priority>" + str(l[1]) + "</priority>\n")
        out.write("\t</url>\n")

    out.write("</urlset>\n")

    checksums_out.close()

    if args.target:
        out.close()

        if existed and not cmp(oldpath, path):
            print("Creating old sitemap backup...")
            move(oldpath, oldpath + "-old")
            print("Overwriting old sitemap with new one...")
            move(path, oldpath)
        elif existed:
            print("Sitemaps are the same, removing temp...")
            os.remove(path)

    print("Done.")
    print(f"Crawled {len(links.keys())} pages.")
    print(f"Found {different_count} modified pages.")

    if network is not None:
        print(convert2cytoscapeJSON(network))

parser.add_argument("-c", "--custom-opts", action='store_true', dest='custom', help="Specify options, config is ignored")
parser.add_argument("-o", "--to-stdout", action='store_true', dest='to_stdout', help="Print generated sitemap to console.")
parser.add_argument("-n", "--network", action='store_true', dest='create_network', help="Create visual network of sitemap. Output as JSON")
parser.add_argument("-f", "--to-file", dest='target', default=False, help="Save generated sitemap to file.")
parser.add_argument('site', nargs='?')
parser.add_argument('checksums', nargs='?')
parser.add_argument('ignores', nargs='?')
args = parser.parse_args()

main(args)
