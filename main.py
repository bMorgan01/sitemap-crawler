import datetime
import bs4
from urllib.request import Request, urlopen


def spider(prefix, domain, exclude):
    return spider_rec(dict(), prefix, domain, "/", exclude)


def spider_rec(links, prefix, domain, postfix, exclude):
    links[postfix] = 1

    req = Request(prefix + domain + postfix)
    html_page = urlopen(req)

    soup = bs4.BeautifulSoup(html_page, "lxml")
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
                    spider_rec(links, "", "", href, exclude)
                else:
                    spider_rec(links, prefix, domain, href, exclude)
            else:
                links[href] += 1
    return links


def main():
    conf = []
    with open('crawl.conf', 'r') as file:
        for line in file.readlines():
            if line[0] != '#':
                line = line.replace("\n", "")
                line = line.replace("\r", "")
                conf.append(line)

    domain = conf[0]
    prefix = conf[1]

    ignores = conf[2::]

    links = spider(prefix, domain, ignores)
    date = datetime.datetime.utcnow()

    out = open("sitemap.xml", 'w')
    out.write("<!--\n")
    out.write("\tSitemap generator by Ben Morgan - www.benrmorgan.com\n")
    out.write("-->\n")
    out.write(
        "<urlset xsi:schemaLocation=\"http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd\">\n")

    sorted_links = dict(sorted(links.items(), key=lambda item: item[1], reverse=True))

    ordered = []
    level = 0
    old_num = sorted_links[list(sorted_links.keys())[0]]
    for l in sorted_links.keys():
        if sorted_links[l] != old_num:
            level += 1
            old_num = sorted_links[l]

        link = l
        if link[0] == '/':
            link = prefix + domain + link
        ordered.append((link, str(float(str(round(pow(0.8, level), 2))))))

    for l in ordered:
        out.write("\t<url>\n")
        out.write("\t\t<loc>" + l[0] + "</loc>\n")
        out.write("\t\t<lastmod>" + date.strftime("%Y-%m-%dT%H:%M:%S+00:00") + "</lastmod>\n")
        out.write("\t\t<priority>" + str(l[1]) + "</priority>\n")
        out.write("\t</url>\n")

    out.write("</urlset>\n")
    out.close()


main()
