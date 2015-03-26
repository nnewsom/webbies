from netaddr import IPNetwork,IPAddress
from .Common import *

class Scope(object):
    def __init__(self,scope,verbosity=0):
        self.nets = None
        self.verbosity = verbosity
        try:
            self.nets = list(map(lambda x: IPNetwork(x),scope)) # need list to interate through object mulitple times
        except Exception as ex:
            print_error("Error setting scope object: '%s'" % ex)

    def in_scope(self,host):
        for network in self.nets:
            if IPAddress(host) in network:
                return True
        return False
