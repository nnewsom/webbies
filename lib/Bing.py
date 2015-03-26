import argparse,sys
import asyncio
import aiohttp
from urllib.parse import urlparse
from base64 import b64encode

class Bing:
    def __init__(self,apikey,loop=None,conn=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self.key = ":{key}".format(key=apikey)
        self.headers = {
                        "Authorization": "Basic {ekey}".format(ekey=b64encode(self.key.encode()).decode()), #decode the byte string to string after encoding w/ byte string
                        "User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64; rv:22.0) Gecko/20100101 Firefox/22.0"
                        }
        self.parameters = {
                    "$format":"json",
                    "$top":50,
                    }
        self.uniq_hosts = set()
        self.uniq_urls = set()
        self.url = "https://api.datamarket.azure.com/Bing/Search/Web"
        self.conn = conn 

    @asyncio.coroutine
    def __process(self,request):
        for i in request['d']['results']:
            url = i['Url'].encode('ascii','ignore').decode()
            self.uniq_urls.add(url)
            up = urlparse(url)
            x = up.netloc
            if not x.count(':'):
                if up.scheme == "https":
                    x+=":443"
                else:
                    x+=":80"

            self.uniq_hosts.add(x)
        if len(request['d']['results']) < self.parameters['$top']:
            return False
        else:
            return True

    @asyncio.coroutine
    def search(self,query,page):
        params = {
            "Query":query,
            "$skip": self.parameters["$top"] * page
        }
        params.update(self.parameters)
        try:
            r = yield from aiohttp.request(
                    'get',
                    self.url,
                    params=params,
                    headers=self.headers
                    )
            results = yield from r.json()
            yield from self.__process(results)
        except aiohttp.ClientError as client_error:
            print("Error: {emsg}".format(emsg=client_error))

    @asyncio.coroutine
    def search_domain(self,domain,pages=3):
        query = "'domain:{domain}'".format(domain=domain)
        coros = []
        for _ in range(pages):
            coros.append(
                asyncio.Task(self.search(query,_),loop=self.loop)
            )
        yield from asyncio.gather(*coros)
        for w in coros:
            w.cancel()
        return

    @asyncio.coroutine
    def search_ip(self,ip,pages=3):
        query = "'ip:{ip}'".format(ip=ip)
        coros = []
        for _ in range(pages):
            coros.append(
                asyncio.Task(self.search(query,_),loop=self.loop)
            )
        yield from syncio.gather(*coros)
        for w in coros:
            w.cancel()
        return

    @asyncio.coroutine
    def main(self,ip,domain):
        if ip:
            yield from b.search_ip(ip)
        if domain:
            yield from b.search_domain(domain)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Bing.py',description='bing search')
    parser.add_argument("-k","--key",help="API key",required=True)
    parser.add_argument("-d","--domain",help="domain lookup")
    parser.add_argument("-i","--ip",help="ip lookup")

    if len(sys.argv) <2 :
        parser.print_help()
        sys.exit(0)

    args=parser.parse_args()

    loop = asyncio.get_event_loop()
    b = Bing(args.key,loop=loop)
    loop.run_until_complete(b.main(args.ip,args.domain))


    print("unique hosts")
    for x in b.uniq_hosts:
        print (x)
    print("")

    print("unique urls")
    for x in b.uniq_urls:
        print(x)
