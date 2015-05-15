import gzip,datetime,ssl
import asyncio,aiohttp,re,os
from urllib.parse import urljoin,urlparse
from random import choice
from blessed import Terminal
from .CustomTCPConnector import CustomTCPConnector
from .DNSResolver import DNSResolver
from .NotFoundHandler import NotFoundHandler
from .Common import *
from .ProgressBar import ProgressBar
from .Probe import Probe

class FDB(object):
    def __init__(self,host,wordlist,extensions,limit,resolvers=[],output_directory="",verbosity=0,loop=None,terminal=None,lineno=0,max_word_length=20):
        self.NOT_FOUND_ATTEMPTS = 4
        self.ERROR_COUNT = 0
        self.MAX_ERROR = 25

        self.loop = loop if loop else asyncio.get_event_loop()
        self.extensions = extensions
        self.limit = limit
        self.control = asyncio.Semaphore(limit)
        self.results = []
        self.nfh = NotFoundHandler(max_word=max_word_length)
        self.verbosity = verbosity
        self.max_word_length = 0

        self.start_time = None
        self.stop_time = None

        self.error_log = set()

        self.wordlist = wordlist
        self.queue = set()

        self.headers = {
                'User-Agent': choice(useragents)
            }

        self.resolver = DNSResolver(nameservers=resolvers)
        self.sslc = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.sslc.check_hostname = False
        self.sslc.verify_mode = ssl.CERT_NONE

        self.conn = CustomTCPConnector(
                    ssl_context=self.sslc,
                    loop=self.loop
                    )
        self.conn.set_resolver(self.resolver)

        self.filename = "{host}_{timestamp}.txt".format(host=re.sub('[/:]+','_',host),timestamp=datetime.now().strftime("%H-%M-%S-%f"))
        self.output_path = os.path.join(output_directory,self.filename) if output_directory else os.path.join(os.getcwd(),self.filename)

        self.terminal = terminal if terminal else Terminal()
        if not terminal:
            print(self.terminal.clear)
        self.lineno = lineno

        self.pb = ProgressBar(
                terminal = self.terminal,
                lineno=lineno
                )

        if not host.endswith('/'):
            host = host+'/'
        try:
            self.host = urlparse(host)
        except Exception as ex:
            with self.terminal.location(0,self.lineno):
                print_error("Failure setting host: {msg}".format(msg=ex))

        try:
            extensions  = list(filter(None,extensions.split(',')))
            self.extensions = set(map(lambda x: '.{ext}'.format(ext=x),extensions)) | set(['/',''])
        except Exception as ex:
            with self.terminal.location(0,self.lineno):
                print_error("Failure setting extensions: {msg}".format(msg=ex))

    def update_terminal_lineno(self,lineno):
        self.lineno = lineno
        self.pb.lineno = lineno

    def end(self):
        with self.terminal.location(0,self.lineno):
            print_success("Saved to output file: {f}{clear}".format(
                            f=self.output_path,
                            clear=self.terminal.clear_eol)
                        )
        self.conn.close()

    def save_output(self):
        try:
            output = open(self.output_path,'w')
            output.write("# {host}\n".format(host=self.host.geturl()))
            output.write("# start: {timestamp}\n".format(timestamp=self.start_time.strftime("%m-%d-%y_%H:%M:%S.%f")))
            output.write("# wordlist: {wordlist}\n".format(wordlist=self.wordlist))
            output.write("# extensions: {exts}\n".format(exts=self.extensions))
            for x in filter(lambda x: x.code != 404,self.results):
                output.write("{code},{url},{length}\n".format(url=x.url,code=x.code,length=x.length))
            for e in self.error_log:
                output.write("# {msg}\n".format(msg=e))
            output.write("# stop: {timestamp}\n".format(timestamp=datetime.now().strftime("%m-%d-%y_%H:%M:%S.%f")))
            output.close()

        except Exception as ex:
            with self.terminal.location(0,self.lineno):
                print_error("Failed creating output file {filename}: {msg}".format(filename=output_file,msg=ex))
            sys.exit(2)

    def __log_error(self,msg):
        etime = datetime.now().strftime("%H-%M-%S-%f")
        self.error_log.add("{etime}::{msg}".format(etime=etime,msg=msg))

    @asyncio.coroutine
    def fetch(self,word):
        p = None
        with (yield from self.control):
            try:
                url = urljoin(self.host.geturl(),word)
                response = yield from aiohttp.request(
                                                'GET',
                                                url,
                                                allow_redirects=False,
                                                connector=self.conn,
                                                headers=self.headers,
                                            )

                body = yield from response.text(encoding='ascii')
                p = Probe(url,response.status,body)

            except aiohttp.ClientError as client_error:
                self.__log_error(client_error)
                self.ERROR_COUNT +=1
            finally:
                return p

    @asyncio.coroutine
    def not_found_probe(self,word):
        success =False
        p = yield from self.fetch(word)
        if p:
            yield from self.nfh.add(p)
            success = True
        return success

    @asyncio.coroutine
    def probe(self,word):
        if self.ERROR_COUNT > self.MAX_ERROR:
            return
        else:
            p =yield from self.fetch(word)
            if p:
                is404 = yield from self.nfh.is_not_found(p)
                if (is404):
                    p.code = 404
                del(p.body)
                self.results.append(p)

    @asyncio.coroutine
    def run(self,queue):
        self.start_time = datetime.now()
        for _ in range(self.NOT_FOUND_ATTEMPTS):
            for ext in self.extensions:
                uri = (random_nstring(20)+ext).strip()
                success = yield from self.not_found_probe(uri)
                if not success:
                    with self.terminal.location(0,self.lineno):
                        print_error("404 detection failed")
                        return -1
        count = 0
        total = len(queue)
        for subset in grouper(10000,queue):
            if subset:
                coros = []
                for x in subset:
                    if x:
                        coros.append(asyncio.Task(self.probe(x),loop=self.loop))

                for f in self.pb.tqdm(asyncio.as_completed(coros),start=count,total=total,desc=self.host.geturl(),miniters=10):
                    yield from f
                count += len(coros)
        self.save_output()
        self.end()
