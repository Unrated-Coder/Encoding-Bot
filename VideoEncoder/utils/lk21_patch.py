import urllib.parse
import re
import sys
import types

# Patch re.sre_parse for lk21/exrex compatibility on Python 3.12+
if not hasattr(re, "sre_parse"):
    import re._parser
    re.sre_parse = re._parser

# Mock pkg_resources if missing (removed in Python 3.12+ / setuptools >= 70)
if 'pkg_resources' not in sys.modules:
    try:
        import pkg_resources
    except ModuleNotFoundError:
        m = types.ModuleType('pkg_resources')
        try:
            from packaging.version import parse as parse_version
            m.parse_version = parse_version
        except ImportError:
            m.parse_version = lambda v: v
        sys.modules['pkg_resources'] = m

_orig_urlparse = urllib.parse.urlparse

def safe_urlparse(url, scheme='', allow_fragments=True):
    try:
        return _orig_urlparse(url, scheme=scheme, allow_fragments=allow_fragments)
    except Exception:
        return _orig_urlparse("http://invalid", scheme=scheme, allow_fragments=allow_fragments)

urllib.parse.urlparse = safe_urlparse

# Now import lk21 AFTER monkey patch
try:
    import lk21
except ImportError:
    lk21 = None

# Apply hydrogram save_file patch
from . import hydrogram_patch
