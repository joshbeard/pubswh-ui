'''
Created on Oct 15, 2014

@author: ayan
'''
import sys

DEBUG = True
SECRET_KEY = ''
VERIFY_CERT = True
COLLECT_STATIC_ROOT = 'static/'
COLLECT_STORAGE = 'flask.ext.collect.storage.file'
PUB_URL = ''
LOOKUP_URL = ''
SUPERSEDES_URL = ''
BROWSE_URL = ''
BASE_SEARCH_URL = ''

try:
    from local_settings import *
except ImportError:
    pass

# variables used for testing purposes
testing = sys.argv[0].endswith('nosetests')
if testing:
    BASE_SEARCH_URL = 'https://pubs-fake.er.usgs.gov/pubs-services/publication/'