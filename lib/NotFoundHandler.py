from .Probe import Probe
from urllib.parse import urlparse
from difflib import SequenceMatcher
from hashlib import md5
from .Common import *
import re,asyncio

class NotFoundHandler:
    def __init__(self,max_word=20,threshold=0.9):
        self.threshold= threshold
        self.history = set()
        self.bhash_history = set()
        self.shash_history = set()
        self.avg_length = 0
        self.MAX_WORD = max_word
        self.tstruct_re = re.compile('\</?(?P<tag>[a-zA-Z]+ ?)>?')

    @asyncio.coroutine
    def add(self,xprobe):
        self.history.add(xprobe)
        l = 0
        for b in [x.body for x in self.history]:
           l += len(b)

        self.avg_length = l/len(self.history)
        if self.avg_length < 50:
            self.threshold = 1.0

        # body hash with possible mirrored uri
        self.bhash_history.add(
                md5(
                    xprobe.body.encode('ascii')
                ).hexdigest()
            )
        uri = urlparse(xprobe.url).path
        # body hash without possible mirrored uri. if dup, set removes
        self.bhash_history.add(
                md5(
                    xprobe.body.replace(uri,'').encode('ascii')
                ).hexdigest()
            )

        # hash of tag structure for testing if similiar to 404 and needs
        # more careful/expensive analysis
        try:
            t_struct = "".join(
                    self.tstruct_re.findall(
                        xprobe.body
                    )
                )
            self.shash_history.add(
                md5(
                    t_struct.encode('ascii','ignore')
                ).hexdigest()
            )
        except Exception as ex:
            print_error("404 probe structure hash creation failed due to {etype}:{emsg}".format(etype=type(ex),emsg=ex))

    def in_length_window(self,l):
        return (l > (self.avg_length - self.MAX_WORD)) and \
                (l < (self.avg_length + self.MAX_WORD))

    def detected_code(self,code):
        return code in [n.code for n in self.history]

    @asyncio.coroutine
    def is_not_found(self,xprobe):
        x_bhash = md5(xprobe.body.encode('ascii')).hexdigest()
        try:
            x_shash = md5(
                        "".join(self.tstruct_re.findall(xprobe.body)).encode('ascii')
                      ).hexdigest()
        except Exception as e:
            print_error("Structure hash creation failed. {url} - {etype}:{e}".format(url=xprobe.url,etype=type(e),e=e))
            x_shash = ""

        # easy/cheap check if 404
        if x_bhash in self.bhash_history:
            return True

        # if similiar structure
        if (x_shash in self.shash_history or self.in_length_window(xprobe.length)) and self.detected_code(xprobe.code):
            s = SequenceMatcher(isjunk=lambda x: x in " \t",autojunk=False)
            s.set_seq2(xprobe.body)
            for body in [ n.body for n in filter(lambda y: y.code ==xprobe.code,self.history)]:
                s.set_seq1(body)
                if s.quick_ratio() > self.threshold:
                    return True
        return False
