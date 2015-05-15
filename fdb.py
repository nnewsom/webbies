#!/usr/bin/env python3
from lib.FDB import FDB
from lib.Common import *
from lib.FDBController import FDBController

from urllib.parse import urlparse
from blessed import Terminal
import asyncio,argparse,sys,os

if __name__== "__main__":
    parser = argparse.ArgumentParser(prog='FDB.py',description='single headless db. for testing and single targets')
    parser.add_argument("-b","--base_dir",help="base directory to be appended to root url",default="")
    parser.add_argument("-e","--extensions",help="extensions to test. commma delimited",required=True)
    parser.add_argument("-H","--host",help="protocol://host:port/")
    parser.add_argument("-iL","--input_list",help="list of hosts to dirbust. <scheme>://<host>:<port>")
    parser.add_argument("-oD","--output_directory",help="Output directory",default="fdb_output")
    parser.add_argument("-L","--limit",help="semaphore control per FDB",type=int,default=5)
    parser.add_argument("-T","--threads",help="number of FDBs to run simultaneously against given list.",type=int,default=5)
    parser.add_argument("-l","--wordlist",help="wordlist to run",required=True)
    parser.add_argument("-v","--verbosity",help="verbose level; v,vv",action="count",default=0)
    parser.add_argument("-R","--resolvers",help="comma delimited hosts to use as dns resolvers",default="")

    if len(sys.argv) < 2:
            parser.print_help()
            sys.exit(0)

    args = parser.parse_args()

    if args.threads:
        control = asyncio.Semaphore(args.threads)

    try:
        if not os.path.exists(args.output_directory):
            os.makedirs(args.output_directory)
    except Exception as ex:
        print_error("Failed to create output directory: {msg}".format(msg=ex))
        sys.exit(1)

    hosts = []
    if args.input_list:
        lines = open(args.input_list).read().split('\n')
        hosts += list(filter(None,lines))
    elif args.host:
        hosts.append(args.host)

    queue = []
    t = Terminal()
    print(t.clear)
    try:
        fdbc = FDBController(terminal=t,wordlist=args.wordlist,extensions=args.extensions)
    except Exception as ex:
        print("Failed to set up controller: {etype}:{emsg}".format(etype=type(ex),emesg=ex))
        sys.exit(-1)

    for host in hosts:
        if urlparse(host).netloc:
            if args.base_dir:
                host+=args.base_dir
            fdb = FDB(
                host = host,
                wordlist=args.wordlist,
                extensions= args.extensions,
                limit=args.limit,
                verbosity=args.verbosity,
                output_directory=args.output_directory,
                terminal=t,
                resolvers=args.resolvers.split(',') if args.resolvers else None,
                max_word_length=fdbc.max_word_length
                )
            queue.append(fdb)
        else:
            print_warning("Malformed host {host} line".format(host=host))

    fdbc.run(queue)
    with t.location(0,args.threads+5):
        print(t.center(t.black_on_green("All FDBs completed.")))
    with t.cbreak():
        t.inkey()
    print(t.clear)
