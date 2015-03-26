import re,os
import xml.etree.ElementTree as ET
from .Webby import Webby
from .Common import *

class Harvester(object):
    def __init__(self,verbosity):
        self.webbies = set()
        self.verbosity = verbosity

    def harvest_nessus_dir(self,nessus_dir):
        for dirpath,directories,files in os.walk(nessusDir):
            for filename in [f for f in files if f.endswith('.nessus')]:
                self.harvest_nessus(os.path.join(dirpath,filename))

    def harvest_nessus(self,nessus_file):
        if self.verbosity:
            print_info("Harvesting Nessus file '{fname}'".format(fname=nessus_file))
        tree = ET.parse(nessus_file)
        root = tree.getroot()

        for host in root.iter('ReportHost'):
            try:
                hostname = host.find('./HostProperties/*[@name="host-fqdn"]').text
            except AttributeError:
                hostname = ""
            try:
                ip = host.find('./HostProperties/*[@name="host-ip"]').text
            except AttributeError:
                ip = host.attrib['name']

            for tcp_item in host.findall('./ReportItem[@pluginID="10335"]'):
                if re.search(r'(www|htt|web)',tcp_item.attrib['svc_name'],re.I):
                    self.webbies.add(Webby(ip,hostname,tcp_item.attrib['port']))
            svc_names = ['www','https?','http?','http_proxy','http','https']
            for svc_name in svc_names:
                for www in host.findall('./ReportItem[@svc_name="%s"]' % svc_name):
                    self.webbies.add(Webby(ip,hostname,www.attrib['port'],ssl=False))
                    self.webbies.add(Webby(ip,hostname,www.attrib['port'],ssl=True))

    def harvest_gnmap_dir(self,gnmap_dir):
        for dirpath,directories,files in os.walk(gnmap_dir):
            for filename in [f for f in files if f.endswith('.gnmap')]:
                self.harvest_gnmap(os.path.join(dirpath,filename))

    def harvest_gnmap(self,gnmap_file):
        if self.verbosity:
            print_info("Harvesting gnmap file {fname}".format(fname=gnmap_file))
        lineRE = re.compile(r'Host:\s+(?P<ip>([0-9]{1,3}\.?){4})\s+\((?P<host>[a-z0-9\._\-]*)\)\s+Ports:\s+(?P<ports>.*?)$',re.I)
        portsRE = re.compile(r'(?P<port>[0-9]+)/+open/+tcp/+[a-z\-0-9]*http[^/]*',re.I)

        for line in filter(None,open(gnmap_file).read().split('\n')):
            x = lineRE.search(line)
            if x:
                openPorts = portsRE.findall(x.group('ports'))
                host = x.group('host') if x.group('host') else ""
                ip= x.group('ip') if x.group('ip') else ""
                if len(openPorts) > 0 and (ip or host):
                    for port  in openPorts:
                            self.webbies.add(Webby(ip,host,port,ssl=False))
                            self.webbies.add(Webby(ip,host,port,ssl=True))
        return self.webbies

    def harvest_IL(self,IL_file):
        if self.verbosity:
            print_info("Harvesting generic input file {fname}".format(fname=IL_file))
        urlRE =re.compile(r'(?P<proto>.*?)://(?P<host>.*?):(?P<port>[0-9]+)')
        ipportRE = re.compile(r'(?P<host>.*?):(?P<port>[0-9]+)')
        for i,line in enumerate(filter(None,open(IL_file).read().split('\n'))):
            x = urlRE.search(line)
            host = ""
            port = ""
            if x:
                host = x.group('host')
                port = x.group('port')
            else:
                x = ipportRE.search(line)
                if x:
                    host = x.group('host')
                    port = x.group('port')

            if host and port:
                if re.search('[a-zA-Z]',host):
                    self.webbies.add(Webby(ip="",hostname=host,port=port,ssl=False))
                    self.webbies.add(Webby(ip="",hostname=host,port=port,ssl=True))
                else:
                    self.webbies.add(Webby(ip=host,hostname="",port=port,ssl=False))
                    self.webbies.add(Webby(ip=host,hostname="",port=port,ssl=True))
            else:
                print_error("Error reading host from line {0}".format(i))
