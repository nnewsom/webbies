from difflib import SequenceMatcher
import os,sys
from .Common import *

class Analyzer(object):
    def __init__(self,threshold = 0.85,verbosity=0):
        self.threshold = threshold
        self.verbosity = verbosity

    def analyze(self,webbies):
        lookup_table= {}
        groups = {}
        groupNo = 0
        if self.verbosity:
            print_info("Generating Lookup Table")
        s = SequenceMatcher(isjunk=lambda x: x in " \t",autojunk=False)
        for webby in filter(lambda w: w.success, webbies):
            s.set_seq2(webby.last_response)
            for xwebby in filter(lambda w: w.success, webbies):
                if webby not in lookup_table:
                    lookup_table[webby] = {}
                if xwebby not in lookup_table[webby]:
                    s.set_seq1(xwebby.last_response)
                    match = s.quick_ratio()
                    lookup_table[webby][xwebby] = match
                    if xwebby not in lookup_table:
                        lookup_table[xwebby] = {}
                    lookup_table[xwebby][webby] = match

        if self.verbosity:
            print_info("Creating Groups")
        for webby in filter(lambda w: w.success, webbies):
            if webby.code and not webby.group:
                for groupNo,webbies in groups.items():
                    matched = 0
                    for xwebby in filter(lambda w: w.success, webbies):
                        if lookup_table[webby][xwebby] > self.threshold and xwebby.code == webby.code:
                            matched+=1
                    if matched == len(webbies):
                        webby.group = groupNo
                        webbies.append(webby)
                        break
                else:
                    groupNo+=1
                    groups[groupNo] = [webby]
                    webby.group = groupNo
                    for xwebby in filter(lambda w: w.success,webbies):
                        if xwebby.code == webby.code and xwebby != webby:
                            if lookup_table[webby][xwebby] > self.threshold:
                                xwebby.group = webby.group
                                groups[groupNo].append(xwebby)
