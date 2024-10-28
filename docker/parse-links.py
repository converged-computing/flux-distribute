#!/usr/bin/env python3

# We can't know in advance what the eth name will be inside the node
# so we parse dynamically.

import subprocess
import argparse
import os
import sys

# usage
# python3 parse-links.py

links = subprocess.check_output(['ip', 'link']).decode('utf-8')
lines = [x for x in links.split('\n') if x.strip()]
lines = [x for x in lines if 'eth' in x and "UP" in x]
lines = lines[0]
linkname = [x for x in lines.split(' ') if 'eth' in x][0].replace(':','')
print(linkname)