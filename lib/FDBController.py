import asyncio,gzip
from blessed import Terminal
from .FDB import FDB
from .ProgressBar import ProgressBar
from .Common import print_error

class FDBController(object):
    def __init__(self,limit=5,loop=None,terminal = None, lineno = 0,wordlist=None,extensions=None):
        self.extensions = []
        self.queue = set()
        self.max_word_length= 0

        self.loop = loop if loop else asyncio.get_event_loop()
        self.limit = asyncio.Semaphore(limit)
        self.control = asyncio.Semaphore(1)
        self.coros = []

        self.terminal = terminal if terminal else Terminal()
        if not terminal:
            print(self.terminal.clear)

        self.pb= ProgressBar(
                terminal = self.terminal,
                lineno=lineno
                )

        self.lines_free = { _:True for _ in range(lineno+1,limit+1)}


        try:
            extensions  = list(filter(None,extensions.split(',')))
            self.extensions = set(map(lambda x: '.{ext}'.format(ext=x),extensions)) | set(['/',''])
        except Exception as ex:
            with self.terminal.location(0,self.lineno):
                print_error("Failure setting extensions: {msg}".format(msg=ex))

        words = set()
        try:
            if wordlist.endswith('.gz'):
                words = set(map(lambda x: x.replace('\r',''),filter(None,gzip.open(wordlist,'rb').read().decode().split('\n'))))
            else:
                words = set(filter(None,open(wordlist).read().split('\n')))
            self.max_word_length = len(max(words)) + len(max(self.extensions)) + 1 # 1 is for the dot. ie: .html
        except Exception as ex:
            with self.terminal.location(0,self.lineno):
                print_error("Failure loading wordlist {wordlist}:{msg}".format(wordlist=wordlist,msg=ex))

        for word in words:
            for ext in self.extensions:
                self.queue.add(word+ext)

    @asyncio.coroutine
    def controlled_run(self,fdb):
        with(yield from self.limit):
            line = 0
            while not line:
                with(yield from self.control):
                    for k,v in self.lines_free.items():
                        if v:
                            line = k
                            self.lines_free[line] = False
                            break
                if not line:
                   yield from asyncio.sleep(1)

            fdb.update_terminal_lineno(line)
            yield from fdb.run(queue=self.queue)
            with(yield from self.control):
                self.lines_free[line] = True

    @asyncio.coroutine
    def controlled_run_all(self):
        for f in self.pb.tqdm(asyncio.as_completed(self.coros),total=len(self.coros),desc='Total'):
            yield from f

    def run(self,queue):
        self.coros = []
        for fdb in queue:
            self.coros.append(asyncio.Task(self.controlled_run(fdb),loop=self.loop))

        self.loop.run_until_complete(self.controlled_run_all())
