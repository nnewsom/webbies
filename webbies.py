#!/usr/bin/env python3

import sys,argparse,os,asyncio
from random import choice
from lib.Harvester import Harvester
from lib.Classifier import Classifier
from lib.Analyzer import Analyzer
from lib.Webby import Webby
from lib.Scope import Scope
from lib.Common import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='classify.webbies.py',description='enumerate and display detailed information about web listeners')
    parser.add_argument("-A","--analyze",help="analyze web listeners responses and group according similarity",action='store_true')
    parser.add_argument("-b","--bing_key",help="bing API key",default="")
    parser.add_argument("-g","--gnmap",help="gnmap input file")
    parser.add_argument("-G","--gnmapdir",help="Directory containing gnmap input files")
    parser.add_argument("-i","--inputList",help="input file with hosts listed http(s)://ip:port/ or ip:port per line")
    parser.add_argument("-n","--nessus",help="nessus input file")
    parser.add_argument("-N","--nessusdir",help="Directory containing nessus files")
    parser.add_argument("-o","--output",help="Output file. Supported types are csv. default is lastrun.csv",default="lastrun.csv")
    parser.add_argument("-R","--nameservers",help="Specify custom nameservers to resolve IP/hostname. Comma delimited",default=[])
    parser.add_argument("-s","--scope",help="Scope file with IP Networks in CIDR format",default="")
    #parser.add_argument("-S","--screenshots",help="enables and specifies screenshot dir. REQUIRES PHANTOMJS",default=None)
    parser.add_argument("-T","--threads",type=int,help="Set the max number of threads.",default=5)
    parser.add_argument("-u","--useragents",help="specifies file of user-agents to randomly use.",default=None)
    parser.add_argument("-v","--verbosity",help="-v for regular output, -vv for debug level",action="count",default=0)
    parser.add_argument("-V","--version",action='version',version='%(prog)s 1.0')

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    webbies = set()

    if args.useragents:
        useragents = filter(None,open(args.useragents).read().split('\n'))

    restore = False
    myClassifier = None

    myHarvester = Harvester(args.verbosity)
    if args.nessus:
        myHarvester.harvest_nessus(args.nessus)
    if args.nessusdir:
        myHarvester.harvest_nessus_dir(args.nessusdir)
    if args.gnmap:
        myHarvester.harvest_gnmap(args.gnmap)
    if args.gnmapdir:
        myHarvester.harvest_gnmap_dir(args.gnmapdir)
    if args.inputList:
        myHarvester.harvest_IL(args.inputList)

    webbies = myHarvester.webbies
    del(myHarvester)

    myScope=None
    if args.scope:
        try:
            iprange = filter(None,open(args.scope).read().split('\n'))
            myScope = Scope(iprange,verbosity=args.verbosity)
            if not myScope.nets:
                print_error("Scope not set. Aborting")
                sys.exit(1)
            if args.verbosity:
                print_info("Scope set to networks listed in '%s'" % args.scope)
        except Exception as ex:
            print_error("Failed reading scope argument. %s" % ex)
            sys.exit(0)
    else:
        iprange = filter(None,map(lambda x: x[0],webbies)) #tuple (ip,hostname,port)
        myScope = Scope(iprange,verbosity=args.verbosity)

    myClassifier = Classifier(
            scope=myScope,
            webbies=webbies,
            ua=choice(useragents),
            verbosity = args.verbosity,
            resolvers = args.nameservers.split(',') if args.nameservers else [],
            bing_key = args.bing_key,
            limit = args.threads,
            )

    try:
        print_highlight("Starting classifier")
        myClassifier.run()
    except KeyboardInterrupt:
        print_highlight("Keyboard interupt detected exiting")
        sys.exit(0)

    if args.analyze:
        print_highlight("Analyzing webbies")
        myAnalyzer = Analyzer(verbosity=args.verbosity)
        myAnalyzer.analyze(myClassifier.webbies_completed)

    if args.output:
        try:
            if not args.output.endswith('.csv'):
                args.output = args.output+'.csv'
            with open(args.output,'w') as fp:
                fp.write("#ip,hostname,port,protocol,service,banner,notes,priority\n")
                for webby in filter(lambda x: x.success, myClassifier.webbies_completed):
                    fp.write(str(webby)+'\n')

            with open(args.output.replace('.csv','_error_log.csv'),'w') as fp:
                fp.write("#ip,hostname,port,protocol,service,banner,notes,priority\n")
                for webby in filter(lambda x: not x.success, myClassifier.webbies_completed):
                    fp.write(str(webby)+'\n')

            print_highlight("successfully saved to '{fname}'".format(fname=args.output))
        except Exception as ex:
            print_error("error saving output file. {etype}:{emsg}".format(etype=type(ex),emsg=ex))
