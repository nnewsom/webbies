import socket
import asyncio
import aiohttp
import re

class CustomTCPConnector(aiohttp.TCPConnector):
    def set_resolver(self,resolver):
        self.resolver = resolver
        self._resolve = True

    @asyncio.coroutine
    def _resolve_host(self, host, port):
        if self._resolve:
            key = (host, port)
            if self.resolver:
                hosts = []
                if re.search('[A-Za-z]',host):
                    ips = yield from self.resolver.query_name(host)
                    for ip in ips:
                        hosts.append(
                            {'hostname': host,
                            'host': ip, 'port': port,
                            'family': self._family, 'proto': 0,
                            'flags':0
                            }
                        )
                else:
                    hostnames = yield from self.resolver.query_ip(host)
                    for hostname in hostnames:
                        hosts.append(
                            {'hostname': hostname,
                            'host': host, 'port': port,
                            'family': self._family, 'proto': 0,
                            'flags':0
                            }
                        )

                return hosts
                
            else:
                if key not in self._resolved_hosts:
                    infos = yield from self._loop.getaddrinfo(
                        host, port, type=socket.SOCK_STREAM, family=self._family)

                    hosts = []
                    for family, _, proto, _, address in infos:
                        hosts.append(
                            {'hostname': host,
                             'host': address[0], 'port': address[1],
                             'family': family, 'proto': proto,
                             'flags': socket.AI_NUMERICHOST})
                    self._resolved_hosts[key] = hosts

                return list(self._resolved_hosts[key])
        else:
            return [{'hostname': host, 'host': host, 'port': port,
                     'family': self._family, 'proto': 0, 'flags': 0}]
