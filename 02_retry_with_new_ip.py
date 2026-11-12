"""Retry with a new IP after a block (403/429) or a dropped connection.

Retrying from the same IP rarely helps after a block. With a rotating residential
gateway, a new session ID in the username means a new IP for the next attempt.

    export FUSION_USER=... FUSION_PASS=...
    python 02_retry_with_new_ip.py
"""
import os
import random
import time

import requests

USER, PASS = os.environ["FUSION_USER"], os.environ["FUSION_PASS"]
COUNTRY = os.environ.get("FUSION_COUNTRY", "us")
BLOCKED = {403, 429}


def new_session() -> requests.Session:
    """A session with its own sticky residential IP for 10 minutes."""
    sid = random.randint(1000000, 9999999)
    proxy = f"http://{USER}-country-{COUNTRY}-sessid-{sid}-sessTime-600s:{PASS}@resi.fusionproxy.net:12286"
    s = requests.Session()
    s.proxies.update({"http": proxy, "https": proxy})
    return s


def fetch(url: str, attempts: int = 4) -> requests.Response:
    session = new_session()
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=30)
            if r.status_code not in BLOCKED and r.status_code < 500:
                return r
            reason = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            reason = type(e).__name__
        if attempt == attempts:
            raise RuntimeError(f"giving up after {attempts} attempts ({reason})")
        pause = min(2 ** attempt, 20) + random.uniform(0, 1)  # exponential backoff with jitter
        print(f"attempt {attempt}: {reason}, new IP in {pause:.1f} s")
        session.close()
        session = new_session()
        time.sleep(pause)


r = fetch("https://ipinfo.io/json")
print("ok:", r.json()["ip"], r.json()["country"])

try:
    fetch("https://httpbin.org/status/429", attempts=3)  # always 429: shows the rotation, then gives up
except RuntimeError as e:
    print(e)
