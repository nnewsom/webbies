import asyncio
from blessed import Terminal
from .FDB import FDB
from .ProgressBar import ProgressBar

class FDBController(object):
    def __init__(self,limit=5,loop=None,terminal = None, lineno = 0):
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
            yield from fdb.run()
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
