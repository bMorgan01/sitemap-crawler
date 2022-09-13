#!/usr/bin/env python3
from calendar import different_locale
import datetime
import os
import bs4
from urllib.request import Request, urlopen
from os.path import exists
from shutil import move
from hashlib import md5
import configparser


def get_page_hash(text: str):
    text = text.replace(' ', '').replace('\r', '').replace('\n', '')

    return md5(text.encode('utf-8')).hexdigest()

def spider(prefix, domain, exclude):
    return spider_rec(dict(), dict(), prefix, domain, "/", exclude)


def spider_rec(links, checksums, prefix, domain, postfix, exclude):
    req = Request(prefix + domain + postfix)
    html_page = urlopen(req)

    soup = bs4.BeautifulSoup(html_page, "lxml")

    checksums[postfix] = get_page_hash(soup.getText())
    links[postfix] = 1

    for link in soup.findAll('a'):
        href = link.get('href')
        if "mailto:" not in href and (domain in href or href[0] == '/'):
            if href not in links.keys():
                found = False
                for d in exclude:
                    if d in href:
                        found = True
                        break

                if found:
                    continue

                href = href.replace(" ", "%20")

                if domain in href:
                    spider_rec(links, checksums, "", "", href, exclude)
                else:
                    spider_rec(links, checksums, prefix, domain, href, exclude)
            else:
                links[href] += 1
    return links, checksums


def cmp(p1, p2):
    with open(p1, 'r') as f1:
        with open(p2, 'r') as f2:
            l1 = f1.readlines()
            l2 = f2.readlines()
            if len(l1) == len(l2):
                for i in range(len(l1)):
                    if l1[i] != l2[i]:
                        if "<lastmod>" not in l1[i]:
                            return False
            else:
                return False

    return True


def main():
    print("Reading conf...")

    config = configparser.ConfigParser()
    config.read('crawl.conf')
    config = config['Config']

    domain = config['domain']
    prefix = config['prefix']
    path = config['target']
    checksums_path = config['checksums']

    ignores = config['ignore'].split(', ')

    checksums = dict()
    try:
        with open(checksums_path, 'r') as checksums_file:
            for line in checksums_file.readlines():
                thirds = line.split()
                checksums[thirds[0]] = (thirds[1:])
    except FileNotFoundError:
        print("No checksums file found at path, new file will be created.")

    print("Crawling site...")
    links, new_checksums = spider(prefix, domain, ignores)
    date = datetime.datetime.utcnow()

    existed = exists(path)
    oldpath = path
    if existed:
        print("Sitemap already exists, creating temp...")
        path = "newmap.xml"

    print("Writing to target file...")
    out = open(path, 'w')
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
        if l in checksums.keys() and checksums[l[0]] == new_checksums[l[0]]:
            lastmod = checksums[l[0]][1]
            different_count += 1
        
        checksums_out.write(f"{l[0]} {new_checksums[l[0]]} {lastmod}\n")
        
        if l[0] == '/':
            l = prefix + domain + l[0]

        out.write("\t<url>\n")
        out.write("\t\t<loc>" + l[0] + "</loc>\n")

        out.write("\t\t<lastmod>" + lastmod + "</lastmod>\n")
        out.write("\t\t<priority>" + str(l[1]) + "</priority>\n")
        out.write("\t</url>\n")

    out.write("</urlset>\n")
    out.close()

    checksums_out.close()

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


main()
