import os,re
from urllib.parse import urlparse
from xml.dom import minidom
import xml.etree.ElementTree as ET

class XMLCreator(object):
    def __init__(self):
        self.root = ET.Element("FDB")

    def save_xml(self,outputfile):
        try:
            if not outputfile.endswith('.xml'):
                outputfile += ".xml"
            tree_string =  ET.tostring(self.root)
            reparsed = minidom.parseString(tree_string).toprettyxml(indent="    ")
            with open(outputfile,'w') as output:
                output.write(reparsed)
        except Exception as ex:
            raise ex

    def parse(self,output_directory):
        urlRE = re.compile('^#\s+url:\s+(?P<url>http.*/)$',re.M)
        startRE = re.compile('^#\s+start:\s+(?P<start_time>.*)$',re.M)
        stopRE = re.compile('^#\s+stop:\s+(?P<stop_time>.*)$',re.M)
        wordlistRE = re.compile('^#\s+wordlist:\s+(?P<wordlist>.*)$',re.M)
        extRE = re.compile('^#\s+extensions:\s+{(?P<extensions>.*)}$',re.M)

        responseRE = re.compile('^(?P<status>\d{3}),(?P<path>.*),(?P<size>\d+)$',re.M)

        for dirpath,directories,files in os.walk(output_directory):
            for filename in [f for f in files if f.endswith('.txt')]:
                try:
                    data = open(os.path.join(dirpath,filename)).read()
                    root_url = urlRE.findall(data)[0]
                    urlp = urlparse(root_url)
                    if urlp.netloc.count(':'):
                        host,port = urlp.netloc.split(':')
                    else:
                        host = urlp.netloc
                        port = "80" if urlp.scheme == 'http' else "443"
                    start =startRE.findall(data)[0]
                    stop = stopRE.findall(data)[0]
                    wordlist = wordlistRE.findall(data)[0]
                    extensions = extRE.findall(data)[0]

                    results = set()

                    for status,url,size in responseRE.findall(data):
                        results.add( (status,url,size) )

                    scan_ele = ET.SubElement(self.root,"scan")
                    info_ele = ET.SubElement(scan_ele,"info")
                    ET.SubElement(info_ele,"host").text = host
                    ET.SubElement(info_ele,"port").text = port
                    ET.SubElement(info_ele,"url").text = root_url
                    ET.SubElement(info_ele,"start").text = start
                    ET.SubElement(info_ele,"stop").text = stop
                    ET.SubElement(info_ele,"wordlist").text = wordlist
                    ET.SubElement(info_ele,"extensions").text = extensions
                    ET.SubElement(info_ele,"source").text = filename
                    result_ele = ET.SubElement(scan_ele,"results")
                    for status,url,size in results:
                            response_ele = ET.SubElement(result_ele,"item")
                            ET.SubElement(response_ele,"status").text = status
                            ET.SubElement(response_ele,"url").text = url
                            ET.SubElement(response_ele,"size").text = size

                except Exception as ex:
                    raise ex
