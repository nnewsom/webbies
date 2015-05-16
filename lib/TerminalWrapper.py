from blessed import Terminal
from datetime import datetime
from .Common import Color

class TerminalWrapper:
    def __init__(self, pterminal = None, prefix="Controller",lineno=0):
        self.terminal = Terminal() if not pterminal else pterminal
        self.prefix = prefix

        self.lineno = lineno
        self.last_print_n = 0

    def _print(self,msg):
        msg += ' '*(self.last_print_n - len(msg))
        self.last_print_n = len(msg)

        with self.terminal.location(0,self.lineno):
            print(msg)

    def print(self,msg):
        self._print(msg)

    def clear(self):
        print(self.terminal.clear)

    def print_error(self,msg):
        _msg = "{prefix}:{color}[!]{endc} {timestamp} {msg}".format(
                color=Color.RED,
                endc=Color.ENDC,
                timestamp=datetime.now().strftime("%H:%M:%S.%f"),
                msg=msg,
                prefix=self.prefix
                )
        self._print(_msg)

    def print_warning(self,msg):
        _msg= "{prefix}:{color}[W]{endc} {timestamp} {msg}".format(
                color=Color.YELO,
                endc=Color.ENDC,
                timestamp=datetime.now().strftime("%H:%M:%S.%f"),
                msg=msg,
                prefix=self.prefix
                )
        self._print(_msg)

    def print_info(self,msg):
        _msg = "{prefix}:{color}[I]{endc} {timestamp} {msg}".format(
                color=Color.BLUE,
                endc=Color.ENDC,
                timestamp=datetime.now().strftime("%H:%M:%S.%f"),
                msg=msg,
                prefix=self.prefix
                )
        self._print(_msg)

    def print_success(self,msg):
        _msg = "{prefix}:{color}[*]{endc} {timestamp} {msg}".format(
                color=Color.GREEN,
                endc=Color.ENDC,
                timestamp=datetime.now().strftime("%H:%M:%S.%f"),
                msg=msg,
                prefix=self.prefix
                )
        self._print(_msg)

    def print_highlight(self,msg):
        _msg= "{prefix}:{color}[*]{endc} {timestamp} {hi}{msg}{endc}".format(
                color=Color.GREEN,
                endc=Color.ENDC,
                hi=Color.OPTIMUM,
                timestamp=datetime.now().strftime("%H:%M:%S.%f"),
                msg=msg,
                prefix=self.prefix
                )
        self._print(_msg)

