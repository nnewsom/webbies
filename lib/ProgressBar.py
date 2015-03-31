from blessed import Terminal
import time

class ProgressBar(object):
    def __init__(self,terminal = None, lineno = 0):
        self.N_BARS = 10

        self.terminal = terminal if terminal else Terminal()
        if not terminal:
            print(self.terminal.clear)
        self.lineno = lineno if lineno else 0

    def format_time_interval(self,t):
        mins,s = divmod(int(t),60)
        h,m = divmod(mins,60)
        return "{h:d}h:{m:d}m:{s:d}s".format(h=h,m=m,s=s)

    def format_meter(self,n, total, elapsed):
        # n - number of finished iterations
        # total - total number of iterations, or None
        # elapsed - number of seconds passed since start
        if n > total:
            total = None

        time_elapsed = self.format_time_interval(elapsed)
        rate = "{r:5.2f}".format(r= (n / elapsed)) if elapsed else '?'

        if total:
            frac = float(n) / total

            bar_length = int(frac*self.N_BARS)

            bar = '#'*bar_length
            bar += '-'*(self.N_BARS-bar_length)

            percentage = '{p:3.0f}%'.format(p=frac * 100)
            time_left = self.format_time_interval(elapsed / n * (total-n)) if n else '?'

            return '|{bar}| {n:d}/{total:d} {percent} [elapsed: {e} left: {l}, {rate} iters/sec]'.format(
                        bar=bar,
                        n=n,
                        total=total,
                        percent=percentage,
                        e=time_elapsed,
                        l=time_left,
                        rate=rate
                    )
        else:
            return '{n:d} [elapsed: {e}, {r} iters/sec'.format(n=n,e=elapsed_str,r=rate)

    # modified tqdm module and wrapped in this class to control terminal printing
    # credit to author noamraph
    # tqdm source: https://github.com/noamraph/tqdm
    def tqdm(self,iterable, total=None,desc='', mininterval=0.5, miniters=1):
        """
        Get an iterable object, and return an iterator which acts exactly like the
        iterable, but prints a progress meter and updates it every time a value is
        requested.
        'desc' can contain a short string, describing the progress, that is added
        in the beginning of the line.
        'total' can give the number of expected iterations. If not given,
        len(iterable) is used if it is defined.
        If less than mininterval seconds or miniters iterations have passed since
        the last progress meter update, it is not updated again.
        """
        if total is None:
            try:
                total = len(iterable)
            except TypeError:
                total = None
        
        prefix = desc+': ' if desc else ''
        
        with self.terminal.location(0,self.lineno):
            print(prefix + self.format_meter(0, total, 0))
        
        start_t = last_print_t = time.time()
        last_print_n = 0
        n = 0
        for obj in iterable:
            yield obj
            # Now the object was created and processed, so we can print the meter.
            n += 1
            if n - last_print_n >= miniters:
                # We check the counter first, to reduce the overhead of time.time()
                cur_t = time.time()
                if cur_t - last_print_t >= mininterval:
                    with self.terminal.location(0,self.lineno):
                        print(prefix + self.format_meter(n, total, cur_t-start_t))
                    last_print_n = n
                    last_print_t = cur_t
        else:
            if last_print_n < n:
                cur_t = time.time()
                with self.terminal.location(0,self.lineno):
                    print(prefix + self.format_meter(n, total, cur_t-start_t))
