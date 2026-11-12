<p align="center">
  <a href="https://fusionproxy.net/?utm_source=github&utm_medium=python-requests-retry">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-dark.png">
      <img src="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-light.png" alt="Fusion Proxy" height="52">
    </picture>
  </a>
</p>

# How to retry failed requests in Python requests

`requests` does not retry anything by default: one timeout, one `503`, and your script stops. This guide shows how to add automatic retries with exponential backoff using urllib3's `Retry`, which status codes and methods to retry, how to honour `Retry-After`, and how to retry **from a new IP** after a `403` or `429` block. Both scripts run as is.

```bash
pip install -r requirements.txt
python 01_retry_adapter.py
```

## Contents

1. [Retries with HTTPAdapter and Retry](#1-retries-with-httpadapter-and-retry)
2. [How long the backoff waits](#2-how-long-the-backoff-waits)
3. [What to retry and what not](#3-what-to-retry-and-what-not)
4. [Retry from a new IP after a block](#4-retry-from-a-new-ip-after-a-block)
5. [Common mistakes](#5-common-mistakes)

## 1. Retries with HTTPAdapter and Retry

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(
    total=3,                                     # at most 3 retries (4 attempts)
    backoff_factor=0.5,                          # wait longer after each failure
    status_forcelist=[429, 500, 502, 503, 504],  # retry these HTTP statuses
    allowed_methods=["HEAD", "GET", "OPTIONS"],  # never retry POST blindly
    respect_retry_after_header=True,             # wait as long as the server asks
)

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=retry))
session.mount("http://", HTTPAdapter(max_retries=retry))

r = session.get("https://example.com/api", timeout=15)
```

Every request made with `session` now retries on its own. Connection errors and read timeouts are retried too, as long as `total` allows. With `raise_on_status=False` you get the last response back instead of a `RetryError` when all attempts fail.

[`01_retry_adapter.py`](01_retry_adapter.py) requests a URL that always answers `503` and logs each retry:

```
16:58:10 Incremented Retry for (url='/status/503'): Retry(total=2 ...)
16:58:10 Incremented Retry for (url='/status/503'): Retry(total=1 ...)
16:58:11 Incremented Retry for (url='/status/503'): Retry(total=0 ...)
final status 503 after 4.0 s
```

## 2. How long the backoff waits

In urllib3 2.x the pause before retry *n* is `backoff_factor * 2 ** (n - 1)`, with no pause before the first retry, capped by `backoff_max` (120 s by default). With `backoff_factor=0.5`: retry at once, then after 1 s, then after 2 s. With `backoff_factor=1`: 0 s, 2 s, 4 s, 8 s.

`backoff_jitter=0.5` adds up to half a second of random delay, so many clients that failed together do not all retry at the same moment.

When the server sends `Retry-After` with a `429` or `503`, urllib3 waits that long instead, if `respect_retry_after_header=True` (the default).

## 3. What to retry and what not

| Retry | Don't retry |
|---|---|
| `429 Too Many Requests` (after a pause) | `400`, `401`, `404`: the same request will fail the same way |
| `500`, `502`, `503`, `504`: temporary server or gateway trouble | `403` from the same IP: a block does not lift in a second (see section 4) |
| Connection resets and timeouts | `POST` that may have reached the server: you could create an order twice |

urllib3 retries only idempotent methods by default (`GET`, `HEAD`, `PUT`, `DELETE`, `OPTIONS`, `TRACE`). Add `POST` to `allowed_methods` only for endpoints that are safe to repeat.

## 4. Retry from a new IP after a block

A `403` or `429` caused by your IP will not go away by retrying from the same IP. Change the IP, wait a little, then retry. With a rotating residential gateway, a new session ID in the username gives you a new IP:

```python
def new_session():
    sid = random.randint(1000000, 9999999)
    proxy = f"http://{USER}-country-us-sessid-{sid}-sessTime-600s:{PASS}@resi.fusionproxy.net:12286"
    s = requests.Session()
    s.proxies.update({"http": proxy, "https": proxy})
    return s

session = new_session()
for attempt in range(1, 5):
    try:
        r = session.get(url, timeout=30)
        if r.status_code not in (403, 429) and r.status_code < 500:
            break
    except requests.RequestException:
        pass
    session = new_session()                                      # new IP
    time.sleep(min(2 ** attempt, 20) + random.uniform(0, 1))     # backoff with jitter
```

```bash
export FUSION_USER="your_username"   # from the Fusion Proxy dashboard
export FUSION_PASS="your_password"
python 02_retry_with_new_ip.py
```

```
ok: 96.250.69.213 US
attempt 1: HTTP 429, new IP in 2.9 s
attempt 2: ReadTimeout, new IP in 4.6 s
giving up after 3 attempts (HTTP 429)
```

The second call targets a URL that answers `429` to everyone, so you can watch the rotation and the final give-up. The username options are explained in the [endpoint generator guide](https://fusionproxy.net/guides/endpoint-generator?utm_source=github&utm_medium=python-requests-retry).

## 5. Common mistakes

- **No timeout.** Retries never start if the first request hangs forever. Always pass `timeout=`.
- **Retrying instantly in a loop.** It looks like an attack and extends the block. Back off.
- **Retrying everything.** A `404` will be a `404` four times. Retry only temporary failures.
- **Hiding errors with `verify=False`.** A certificate error is not a temporary failure.
- **Mounting only `https://`.** Plain `http://` URLs then skip the retries.

## Related

- [python-requests-proxy](https://github.com/FusionProxies/python-requests-proxy): every way to use a proxy in requests
- [python-web-scraping](https://github.com/FusionProxies/python-web-scraping): a complete scraper that uses these retries
- [proxy-checker](https://github.com/FusionProxies/proxy-checker): check which proxies work before you use them

Getting blocked? [Fusion Proxy residential proxies](https://fusionproxy.net/proxies/residential?utm_source=github&utm_medium=python-requests-retry) give you real household IPs in the country, state or city you choose, with rotating or sticky sessions. [Free trial](https://fusionproxy.net/free-trial?utm_source=github&utm_medium=python-requests-retry).

## License

MIT, see [LICENSE](LICENSE).
