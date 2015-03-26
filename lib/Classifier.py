import asyncio 
import aiohttp
import ssl
import re
import OpenSSL
from urllib.parse import urljoin,urlparse
from .Webby import Webby
from .DNSResolver import DNSResolver
from .CustomTCPConnector import CustomTCPConnector
from .Common import *


class Classifier(object):
    def __init__(self,scope,webbies,verbosity,ua,loop=None,resolvers=[],bing_key="",limit=1):
        self.ALTNAME_EXTENSION = 2

        self.scope = scope
        self.loop = loop if loop else asyncio.get_event_loop()

        self.webbies_new = asyncio.Queue(loop=self.loop)
        self.webbies_history = set()
        for webby in webbies:
            self.webbies_new.put_nowait(webby)

        self.webbies_resolved = asyncio.Queue(loop=self.loop)
        self.webbies_completed = set()

        self.bing_key = bing_key
        self.bing_vname_history = set()
        self.bing_ip_history = set()

        self.resolvers = resolvers
        self.verbosity = verbosity
        self.limit = limit
        self.resolver = DNSResolver(nameservers=resolvers)

        self.ua = ua

        self.sslc = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.sslc.check_hostname = False
        self.sslc.verify_mode = ssl.CERT_NONE

        self.conn = CustomTCPConnector(
                    ssl_context=self.sslc,
                    loop=self.loop
                    )
        self.conn.set_resolver(self.resolver)

    def close(self):
        self.conn.close()

    def queue_new_webby(self,ip,hostname,port):
        for ssl in [True,False]:
            new_webby = Webby(ip=ip,hostname=hostname,port=port,ssl=ssl)
            if new_webby not in self.webbies_history:
                self.webbies_resolved.put_nowait(new_webby)

    @asyncio.coroutine
    def enum_webbies(self):
        while True:
            webby = yield from self.webbies_new.get()
            if self.verbosity:
                print_success("Attempting to enumerate webby: {i}({h}:{p})".format(p=webby.port,i=webby.ip,h=webby.hostname))
            if webby not in self.webbies_history:
                self.webbies_history.add(webby)
                if webby.hostname and not webby.ip:
                    ips = yield from self.resolver.query_name(webby.hostname)
                    for ip in ips:
                        if self.scope.in_scope(ip):
                            self.queue_new_webby(ip,webby.hostname,webby.port)
                        else:
                            print_warning("Excluding {ip}({hostname})'; Not in scope.".format(ip=ip,hostname=webby.hostname))

                elif webby.ip and not webby.hostname:
                    if self.scope.in_scope(webby.ip):
                        hostnames =  yield from self.resolver.query_ip(webby.ip)
                        for hostname in hostnames:
                            self.queue_new_webby(webby.ip,hostname,webby.port)
                    else:
                        print_warning("Excluding '{ip}'; Not in scope.".format(ip=webby.ip))
                else:
                    if self.scope.in_scope(webby.ip):
                        self.webbies_resolved.put_nowait(webby)
                    else:
                        print_warning("Excluding '{ip}({hostname})'; Not in scope.".format(ip=webby.ip,hostname=webby.hostname))

            if self.bing_key:
                try:
                    xbing = Bing(self.bing_key) #note: cascades at this point. azure might not like it
                    if webby.hostname and webby.hostname not in self.bing_vname_history:
                        if self.verbosity:
                            print_info("searching bing for hostname '{vname}'".format(vname=webby.hostname))
                        yield xbing.search_domain(webby.hostname)
                        self.bing_vname_history.add(webby.hostname)
                    if webby.ip and webby.ip not in self.bing_ip_history:
                        if self.verbosity:
                            print_info("searching bing for ip '{ip}'".format(ip=webby.ip))
                        self.bing_ip_history.add(webby.ip)
                        yield xbing.search_ip(webby.ip)

                    for host_port_combo in xbing.uniq_hosts:
                        hostid,port = host_port_combo.split(':')
                        ip = hostname= ""
                        if re.search('^[0-9]{1,3}(\.[0-9]{1,3}){3}$',hostid):
                            ip = hostid
                            hostname = ""
                        else:
                            hostname = hostid
                            ip = ""
                        self.queue_new_webby(ip,hostname,port)

                except Exception as ex:
                    print_error("Bing search failed:{etype} {msg}".format(etype=type(ex),msg=str(ex)))


    @asyncio.coroutine
    def gather_webbies(self):
        while True:
            webby = yield from self.webbies_resolved.get()
            paths = set('/')
            response = None
            while len(paths):
                path = paths.pop()
                try:
                    if self.verbosity:
                        print_success("attempting to gather webby: {s}".format(s=webby.base_url()))
                    webby.url = urljoin(webby.base_url(),path)
                    response = yield from aiohttp.request('GET',
                                                        webby.url,
                                                        allow_redirects=False,
                                                        connector=self.conn,
                                                        loop = self.loop,
                                                       )
                    if webby.ssl:
                        cert_der = response.connection._transport.get_extra_info('socket').getpeercert(True)
                        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1,cert_der)
                        x509_sub = x509.get_subject()
                        cn = x509_sub.__getattr__('commonName')
                        if not cn.count('*'):
                            self.queue_new_webby(ip="",hostname=cn,port=webby.port)
                        alt_names = filter(lambda x: x.count('DNS:'),str(x509.get_extension(self.ALTNAME_EXTENSION)).split(','))
                        alt_names = map(lambda x: str(x).split(':',1)[1],alt_names)
                        for vname in alt_names:
                            self.queue_new_webby(ip="",hostname=vname,port=webby.port)

                    if response.status in (300, 301, 302, 303, 307):
                        urlp = urlparse(response.headers['LOCATION'])
                        if urlp.netloc:
                            port = 0
                            host = ""
                            if urlp.netloc.count(':'):
                                host,port = urlp.netloc.split(':',1)
                            else:
                                host = urlp.netloc
                                port = 443 if urlp.scheme == "https" else 80

                            if port == webby.port and ( host == webby.hostname or host == webby.ip):
                                paths.add(urlp.path)
                            else:
                                webby.redirect_url = response.headers['LOCATION']
                                if re.search('[A-Za-z]',host):
                                    new_webby = Webby(ip="",hostname=host,port=port)
                                else:
                                    new_webby = Webby(ip=host,hostname="",port=port)
                                yield from self.webbies_new.put(new_webby)

                            yield from self.process_response(webby,response)
                        else:
                            paths.add(urlp.path)
                    else:
                        yield from self.process_response(webby,response)

                except aiohttp.ClientError as client_error:
                    webby.success = False
                    webby.error_msg = "{etype}:{emsg}".format(etype=type(client_error),emsg=str(client_error))
                    self.webbies_completed.add(webby)

    @asyncio.coroutine
    def process_response(self,webby,response):
        webby.code = response.status
        body = yield from response.text(encoding='ascii')
        webby.last_response = body
        title_RE = re.compile(r'< *title *>(?P<title>.*?)< */title *>',re.I)

        if 'server' in response.headers:
            webby.banner = response.headers['server'] 
        if re.search('< *FORM',body,re.I):
            webby.forms = True
        if re.search('input.*type\s*=\s*(?:\'|"| *)password',body,re.I):
            webby.login = True
        try:
            webby.title = re.search(r'< *title *>(?P<title>.*?)< */title *>',
                                body.replace('\n',' '),
                                re.I).group('title').strip()
        except:
            webby.title = "NO_TITLE"

        webby.success = True
        self.webbies_completed.add(webby)

    @asyncio.coroutine
    def monitor(self):
        yield from asyncio.sleep(2) # wait for things to start up
        while True:
            if self.webbies_resolved.empty() and self.webbies_new.empty():
                self.loop.stop()
                return
            yield from asyncio.sleep(3)

    def run(self):
        coros = []
        for _ in range(self.limit):
            coros.append(asyncio.Task(self.enum_webbies(),loop=self.loop))
            coros.append(asyncio.Task(self.gather_webbies(),loop=self.loop))

        background = asyncio.Task(self.monitor(),loop=self.loop)
        self.loop.run_forever()
        for w in coros:
            w.cancel()
        background.cancel()
        self.close()
