# webbies
## Description
A python3 asynchronous web recon and enumeration tool set. Given a list of host,port combinations, this tool will enumerate the service to determine if it is https or http, the title and banner information, and the presence of login forms. Additionally, it will perform asynchronous DNS lookups with a given resolver during both enumeration and retrieval. The tool will respect a given scope list that can be either by IP or in CIDR format. Upon completion, it will analyze the webbies and group the similar sites in order to allow the user to find the more interesting and unique sites faster. Last, a bing API key can be provided to attempt to find other ips or hostnames the target service may be running under. 

## Features
* Respects scope (including redirects)
* uses same DNS resolver for enumeration and retrieval by patching aiohttp TCPConnector
* cached DNS requests by wrapping aiodns
* SSLContext can be modified for specific SSL versions
* outputs a simple csv for easy grep-fu of results
* asynchronous http(s) and dns
* specialized bingapi search on ip and hostname given bing key

## TODO
* Add state saving feature
* Add screenshot feature
