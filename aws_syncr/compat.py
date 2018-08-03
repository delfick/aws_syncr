import sys

PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str,
    input = input
    from urllib.parse import urlparse
else:
    string_types = basestring,
    input = raw_input
    from urlparse import urlparse
