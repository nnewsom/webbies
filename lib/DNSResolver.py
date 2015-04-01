import aiodns
import pycares
import asyncio
import re

class DNSResolver(object):
    def __init__(self,nameservers=[],timeout=2,loop=None):
        self.resolver = aiodns.DNSResolver()
        self.loop = loop if loop else asyncio.get_event_loop()
        self.lookup_history = {}
        self.rlookup_history = {}
        if nameservers:
            self.resolver.nameservers = nameservers

    @asyncio.coroutine
    def query_name(self,hostname):
        if hostname not in self.lookup_history:
            try:
                ips = yield from self.resolver.query(hostname,'A')
            except aiodns.error.DNSError:
                ips = []
            self.lookup_history[hostname] = ips
        return self.lookup_history[hostname]

    @asyncio.coroutine
    def query_ip(self,ip):
        if ip not in self.rlookup_history:
            try:
                hostnames = yield from self.resolver.query(pycares.reverse_address(ip),"PTR")
            except aiodns.error.DNSError:
                hostnames = []
            self.rlookup_history[ip] = hostnames
        return self.rlookup_history[ip]

    @asyncio.coroutine
    def query(self,host):
        if re.search('[A-Za-z]',self.host):
            r = yield from self.query_name(host)
        else:
            r = yield from self.query_ip(host)
        return r
