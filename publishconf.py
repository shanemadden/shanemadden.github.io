#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

import os
import sys
sys.path.append(os.curdir)
from pelicanconf import *

SITEURL = 'http://shanemadden.net'
FEED_DOMAIN = SITEURL
RELATIVE_URLS = False

FEED_ALL_ATOM = 'feeds/all.atom.xml'

DELETE_OUTPUT_DIRECTORY = True
DISQUS_SITENAME = 'shanemaddennet'