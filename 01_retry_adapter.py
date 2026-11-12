"""Automatic retries in requests with urllib3's Retry and exponential backoff.

    python 01_retry_adapter.py
"""
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# urllib3 logs every retry at DEBUG level; show them
logging.basicConfig(format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("urllib3.util.retry").setLevel(logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)

retry = Retry(
    total=3,                                     # at most 3 retries (4 attempts)
    backoff_factor=0.5,                          # urllib3 2: retry at once, then wait 1 s, then 2 s
    status_forcelist=[429, 500, 502, 503, 504],  # retry these HTTP statuses
    allowed_methods=["HEAD", "GET", "OPTIONS"],  # never retry POST blindly
    respect_retry_after_header=True,             # wait as long as the server asks
    raise_on_status=False,                       # return the last response instead of raising
)

session = requests.Session()
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)

start = time.time()
r = session.get("https://httpbin.org/status/503", timeout=15)
print(f"final status {r.status_code} after {time.time() - start:.1f} s")

r = session.get("https://httpbin.org/status/200", timeout=15)
print(f"healthy URL: status {r.status_code}, no retries needed")
