import asyncio
import aiohttp
import ssl
import re
import OpenSSL
import aiodns
import os
import sys
from urllib.parse import urljoin,urlparse
from .Bing import Bing
from .Webby import Webby
from .DNSResolver import DNSResolver
from .CustomTCPConnector import CustomTCPConnector
from .Common import *


class Classifier(object):
    def __init__(self,scope,webbies,verbosity,ua,loop=None,resolvers=[],bing_key="",limit=10,timeout=10):
        self.ALTNAME_EXTENSION = 2
        self.MAX_REDIRECTS = 5
        self.TIMEOUT = timeout

        self.scope = scope
        self.loop = loop if loop else asyncio.get_event_loop()

        self.webbies_to_enumerate = set()
        self.webbies_to_gather = set()

        self.webbies_history = set()
        self.webbies_completed = set()

        self.bing_key = bing_key
        self.bing_vname_history = set()
        self.bing_ip_history = set()

        self.resolvers = resolvers
        self.verbosity = verbosity
        self.limit = limit
        self.control = asyncio.Semaphore(limit)
        self.resolver = DNSResolver(nameservers=resolvers)

        self.ua = ua
        self.headers = {
                'User-Agent': self.ua
            }

        self.sslc = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.sslc.check_hostname = False
        self.sslc.verify_mode = ssl.CERT_NONE

        #self.conn = CustomTCPConnector(
        #            ssl_context=self.sslc,
        #            loop=self.loop
        #            )
        #self.conn.set_resolver(self.resolver)

        self.conn = aiohttp.TCPConnector(
                        ssl_context=self.sslc,
                        loop=self.loop
                    )

        for ip,host,port in webbies:
            self.queue_new_webby(ip,host,port)

    def close(self):
        self.conn.close()

    def queue_new_webby(self,ip,hostname,port):
        for ssl in [True,False]:
            new_webby = Webby(ip=ip,hostname=hostname,port=port,ssl=ssl)
            if new_webby not in self.webbies_history:
                self.webbies_to_enumerate.add(new_webby)

    @asyncio.coroutine
    def enum_webby(self,webby):
        with (yield from self.control):
            if webby not in self.webbies_history:
                if self.verbosity:
                    print_success("Attempting to enumerate webby: {i}({h}:{p})".format(p=webby.port,i=webby.ip,h=webby.hostname))
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

                if self.bing_key:
                    try:
                        xbing = Bing(self.bing_key) #note: cascades at this point. azure might not like it
                        if webby.hostname and webby.hostname not in self.bing_vname_history:
                            if self.verbosity:
                                print_info("searching bing for hostname '{vname}'".format(vname=webby.hostname))
                            yield from xbing.search_domain(webby.hostname)
                            self.bing_vname_history.add(webby.hostname)
                        if webby.ip and webby.ip not in self.bing_ip_history:
                            if self.verbosity:
                                print_info("searching bing for ip '{ip}'".format(ip=webby.ip))
                            self.bing_ip_history.add(webby.ip)
                            yield from xbing.search_ip(webby.ip)

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

            if webby.ip:
                if self.scope.in_scope(webby.ip):
                    self.webbies_to_gather.add(webby)
                else:
                    print_warning("Excluding '{ip}({hostname})'; Not in scope.".format(ip=webby.ip,hostname=webby.hostname))

    @asyncio.coroutine
    def gather_webby(self,webby):
        with (yield from self.control):
            paths = set('/')
            response = None
            redirects = 0
            while len(paths):
                path = paths.pop()
                try:
                    if self.verbosity:
                        print_success("attempting to gather webby: {s} ({ip})".format(s=webby.base_url(),ip=webby.ip))
                    webby.url = urljoin(webby.base_url(),path)
                    task = aiohttp.request('GET',
                                            webby.url,
                                            allow_redirects=False,
                                            connector=self.conn,
                                            loop = self.loop,
                                            headers=self.headers
                                           )
                    #aiohttp doesn't have a timeout
                    #asycnio.wait_for raises an exception but does not kill the task
                    #hack_solution
                    done,pending = yield from asyncio.wait([task],timeout=self.TIMEOUT)
                    if pending:
                        for task in pending:
                            task.cancel()
                    else:
                        response = yield from done.pop()
                        if webby.ssl:
                            try:
                                cert_der = response.connection._transport.get_extra_info('socket').getpeercert(True)
                                x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1,cert_der)
                                x509_sub = x509.get_subject()
                                cn = x509_sub.__getattr__('commonName')
                                if not cn.count('*'):
                                    self.queue_new_webby(ip="",hostname=cn,port=webby.port)
                                try:
                                    alt_names = filter(lambda x: x.count('DNS:'),str(x509.get_extension(self.ALTNAME_EXTENSION)).split(','))
                                    alt_names = map(lambda x: str(x).split(':',1)[1],alt_names)
                                    for vname in alt_names:
                                        self.queue_new_webby(ip="",hostname=vname,port=webby.port)
                                except IndexError as ex:
                                    if self.verbosity > 1:
                                        print_warning("Failed alt name extraction: {ip}({hostname}):{port} {ex}".format(
                                                                        ip = webby.ip,
                                                                        hostname = webby.hostname,
                                                                        port = webby.port,
                                                                        ex = ex
                                                                    )
                                                     )
                            except Exception as ex:
                                if self.verbosity:
                                    print_warning("Failed to extract ssl information: {ip}({hostname}):{port} {etype}:{ex}".format(
                                                                        ip = webby.ip,
                                                                        hostname = webby.hostname,
                                                                        port = webby.port,
                                                                        etype= type(ex),
                                                                        ex = ex
                                                                    )
                                                     )

                        if response.status in (300, 301, 302, 303, 307):
                            redirects +=1

                            if redirects > self.MAX_REDIRECTS:
                                yield from self.process_response(webby,response)
                                break

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
                                        self.queue_new_webby(ip="",hostname=host,port=port)
                                    else:
                                        self.queue_new_webby(ip=host,hostname="",port=port)

                                yield from self.process_response(webby,response)
                            else:
                                paths.add(urlp.path)
                        else:
                            yield from self.process_response(webby,response)

                except Exception as e:
                    exec_type, exec_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    webby.success = False
                    webby.error_msg = "{etype} {fname}:{lineno} {emsg}".format(
                                                etype=exec_type,
                                                fname= fname,
                                                lineno = exc_tb.tb_lineno,
                                                emsg=str(e)
                                            )
                    self.webbies_completed.add(webby)

    @asyncio.coroutine
    def process_response(self,webby,response):
        webby.code = response.status
        if self.verbosity > 2:
            print('processing: {url}: http {code}'.format(url=webby.url,code=webby.code))
        try:
            body = yield from response.text(encoding='ascii')
        except UnicodeDecodeError:
            try:
                body = yield from response.text()
                body = body.encode('ascii','replace').decode()
            except:
                body = yield from response.read()
                body = repr(body)

        webby.last_response = body
        title_RE = re.compile(r'< *title *>(?P<title>.*?)< */title *>',re.I)

        if 'server' in response.headers:
            webby.banner = response.headers['server'].replace(',','')
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

    def run(self):
        while len(self.webbies_to_enumerate) or len(self.webbies_to_gather):
            coros = []
            while len(self.webbies_to_enumerate):
                webby = self.webbies_to_enumerate.pop()
                coros.append(asyncio.Task(self.enum_webby(webby),loop=self.loop))

            self.loop.run_until_complete(asyncio.gather(*coros))

            coros = []
            while len(self.webbies_to_gather):
                webby = self.webbies_to_gather.pop()
                coros.append(asyncio.Task(self.gather_webby(webby),loop=self.loop))

            self.loop.run_until_complete(asyncio.gather(*coros))

        self.close()
