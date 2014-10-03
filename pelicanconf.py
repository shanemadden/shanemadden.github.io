#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = u'Shane Madden'
SITENAME = u'shanemadden.net'
SITEURL = ''

PATH = 'content'
THEME = 'pelican-bootstrap3'

TIMEZONE = 'UTC'

DEFAULT_LANG = u'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
DISPLAY_CATEGORIES_ON_MENU = False
DISPLAY_BREADCRUMBS = True
DISPLAY_CATEGORY_IN_BREADCRUMBS = True
DISPLAY_TAGS_ON_SIDEBAR = False
DEFAULT_PAGINATION = 25

DELETE_OUTPUT_DIRECTORY = True

SOCIAL = (('twitter', 'http://twitter.com/shanemadden'),
          ('github', 'http://github.com/shanemadden'),)

GITHUB_USER = 'shanemadden'
GITHUB_REPO_COUNT = 5
GITHUB_SKIP_FORK = True
GITHUB_SHOW_USER_LINK = True

USE_OPEN_GRAPH = True
TWITTER_CARDS = True
TWITTER_USERNAME = 'shanemadden'

BOOTSTRAP_THEME = 'flatly'
PYGMENTS_STYLE = 'zenburn'

GOOGLE_ANALYTICS_UNIVERSAL = 'UA-53885012-1'
GOOGLE_ANALYTICS_UNIVERSAL_PROPERTY = 'auto'
