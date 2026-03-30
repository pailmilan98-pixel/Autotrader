"""Shared yfinance-compatible session with SSL verification disabled.
Needed for corporate networks that use HTTPS inspection proxies.
"""
import logging
import warnings

logger = logging.getLogger(__name__)

def get_yf_session():
    """Return a curl_cffi session with verify=False for yfinance."""
    try:
        from curl_cffi import requests as crequests
        session = crequests.Session(verify=False)
        logger.debug("Using curl_cffi session (verify=False)")
        return session
    except ImportError:
        pass
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session = requests.Session()
        session.verify = False
        logger.debug("Using requests session (verify=False)")
        return session
    except ImportError:
        return None
