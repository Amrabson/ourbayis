"""ob_linkinfo - fetch a store product page and extract name/price/image.

A couple pastes a product link; the server fetches that page once and
prefills the gift. Because the URL is user-supplied, SSRF protection is the
priority: scheme/host validation, every resolved address must be globally
routable, the socket is pinned to a validated IP (DNS-rebinding safe),
redirects are followed manually and re-validated, and size/time are capped.

Public API: lookup(), parse_html(), check_url(), LinkError.
Standard library only. No global mutable state; thread-safe.
"""
import codecs
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import zlib
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from urllib.parse import (parse_qsl, urlencode, urljoin, urlsplit,
                          urlunsplit)

__all__ = ["lookup", "parse_html", "check_url", "LinkError"]

MAX_URL_LEN = 2000
MAX_REDIRECTS = 4
MAX_BODY = 1_500_000          # decompressed bytes we will look at
MAX_RAW = 1_500_000           # raw (possibly compressed) bytes we will read
MAX_PRICE = Decimal(10_000_000)
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home",
                    ".test", ".invalid")
TRACKING_PARAMS = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid",
                   "igshid", "srsltid"}
HTML_TYPES = ("text/html", "application/xhtml+xml")
REDIRECT_CODES = (301, 302, 303, 307, 308)

_HOST_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
_NUMERIC_LABEL_RE = re.compile(r"^(?:0x[0-9a-f]*|[0-9]+)$")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏ -‮﻿]")
_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]*>")
_WS_RE = re.compile(r"\s+")


class LinkError(Exception):
    """code in {'bad_url','blocked_host','fetch_failed','not_html','too_big'}"""

    def __init__(self, code, message=""):
        super().__init__(message or code)
        self.code = code


# --------------------------------------------------------------------------
# URL / address validation
# --------------------------------------------------------------------------

def _ip_is_public(ip):
    """True only for globally routable addresses (unwraps v6 embeddings)."""
    if isinstance(ip, str):
        ip = ipaddress.ip_address(ip.split("%", 1)[0])
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return _ip_is_public(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            if not _ip_is_public(ip.sixtofour):
                return False
        if ip.teredo is not None:
            return False
        if ip in ipaddress.ip_network("64:ff9b::/96"):
            return _ip_is_public(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        if ip in ipaddress.ip_network("::/96"):      # IPv4-compatible
            return False
        if ip.is_site_local:
            return False
    if ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"):
        return False
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified):
        return False
    return bool(ip.is_global)


def _default_resolver(host):
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    out = []
    for info in infos:
        ip = info[4][0]
        if ip not in out:
            out.append(ip)
    return out


def check_url(url, *, resolver=None):
    """Validate url; return (normalised_url, [validated ips]). Raises LinkError."""
    if not isinstance(url, str):
        raise LinkError("bad_url")
    url = url.strip()
    if not url or len(url) > MAX_URL_LEN:
        raise LinkError("bad_url", "empty or too long")
    if any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in url):
        raise LinkError("bad_url", "illegal characters")
    try:
        parts = urlsplit(url)
        port = parts.port
        raw_host = parts.hostname
    except ValueError:
        raise LinkError("bad_url", "unparseable")
    if parts.scheme.lower() not in ("http", "https"):
        raise LinkError("bad_url", "scheme")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise LinkError("bad_url", "userinfo")
    if port not in (None, 80, 443):
        raise LinkError("bad_url", "port")
    if not raw_host:
        raise LinkError("bad_url", "no host")

    host = raw_host.lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise LinkError("bad_url", "bad hostname")

    # IP literals in any notation
    try:
        ipaddress.ip_address(host)
        raise LinkError("blocked_host", "ip literal")
    except ValueError:
        pass
    if ":" in host or "." not in host:
        raise LinkError("blocked_host", "not a public hostname")
    if host == "localhost" or host.endswith(BLOCKED_SUFFIXES):
        raise LinkError("blocked_host", "local hostname")
    labels = host.split(".")
    if any(_NUMERIC_LABEL_RE.match(lbl) for lbl in labels[-1:]) or \
            all(_NUMERIC_LABEL_RE.match(lbl) for lbl in labels):
        raise LinkError("blocked_host", "numeric host")
    if not _HOST_RE.match(host) or len(host) > 253:
        raise LinkError("bad_url", "bad hostname")

    resolve = resolver or _default_resolver
    try:
        addrs = list(resolve(host))
    except (OSError, UnicodeError):
        raise LinkError("fetch_failed", "dns")
    ips = []
    for a in addrs:
        a = str(a).split("%", 1)[0]
        try:
            ok = _ip_is_public(a)
        except ValueError:
            raise LinkError("blocked_host", "bad address")
        if not ok:
            raise LinkError("blocked_host", "non-public address")
        if a not in ips:
            ips.append(a)
    if not ips:
        raise LinkError("fetch_failed", "no address")

    netloc = host if port is None else "%s:%d" % (host, port)
    norm = urlunsplit((parts.scheme.lower(), netloc, parts.path or "/",
                       parts.query, ""))
    return norm, ips


# --------------------------------------------------------------------------
# Pinned HTTP(S) fetch
# --------------------------------------------------------------------------

class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._pinned_ip = ip

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, context=ssl.create_default_context(), **kw)
        self._pinned_ip = ip

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("deadline exceeded")
    return left


def _default_opener(url, host, ip, headers, deadline):
    """GET url with the socket pinned to ip. Returns (status, headers, body)."""
    parts = urlsplit(url)
    https = parts.scheme == "https"
    port = parts.port or (443 if https else 80)
    cls = _PinnedHTTPSConnection if https else _PinnedHTTPConnection
    conn = cls(host, ip, port=port, timeout=_remaining(deadline))
    try:
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        conn.request("GET", path, headers=headers)
        if conn.sock is not None:
            conn.sock.settimeout(_remaining(deadline))
        resp = conn.getresponse()
        hdrs = {}
        for k, v in resp.getheaders():
            k = k.lower()
            hdrs[k] = (hdrs[k] + ", " + v) if k in hdrs else v
        chunks, total = [], 0
        while total < MAX_RAW:
            if conn.sock is not None:
                conn.sock.settimeout(_remaining(deadline))
            chunk = resp.read(min(65536, MAX_RAW - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return resp.status, hdrs, b"".join(chunks)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _decompress(body, encoding):
    encoding = (encoding or "").strip().lower()
    if encoding in ("", "identity"):
        return body[:MAX_BODY]
    if encoding in ("gzip", "x-gzip"):
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        d = zlib.decompressobj()
    else:
        raise LinkError("fetch_failed", "unsupported encoding")
    try:
        return d.decompress(body, MAX_BODY)
    except zlib.error:
        raise LinkError("fetch_failed", "bad compressed data")


_META_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)


def _decode(body, content_type):
    charset = None
    m = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9_.:-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    else:
        m2 = _META_CHARSET_RE.search(body[:2048])
        if m2:
            charset = m2.group(1).decode("ascii", "ignore")
    if charset:
        try:
            codecs.lookup(charset)
            return body.decode(charset, errors="replace")
        except (LookupError, ValueError):
            pass
    return body.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _strip_tracking(url):
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q), ""))


def _display_host(url):
    try:
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu", "or", "ne"}


def _registrable(host):
    labels = host.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _clean(s, limit=None):
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = unescape(s)
    s = _TAG_RE.sub(" ", s)
    s = _CTRL_RE.sub("", s.replace("\xa0", " "))
    s = _WS_RE.sub(" ", s).strip()
    if limit:
        s = s[:limit].strip()
    return s or None


_SEP_RE = re.compile(r"\s+[|\-–—]\s+")


def _clean_name(name, site_name, host):
    name = _clean(name)
    if not name:
        return None
    ms = list(_SEP_RE.finditer(name))
    if ms:
        m = ms[-1]
        head, tail = name[:m.start()].strip(), name[m.end():].strip()
        drop = False
        if head and tail:
            if site_name and tail.lower() == site_name.lower():
                drop = True
            elif len(tail) <= 25 and host:
                labels = _display_host("https://" + host).split(".")
                main = _registrable(".".join(labels)).split(".")[0]
                norm = re.sub(r"[\W_]+", "", tail.lower())
                if main and norm and (norm == main or main in norm):
                    drop = True
        if drop:
            name = head
    return name[:200].strip() or None


def _norm_price(v):
    """Return plain decimal string ('1861', '48.50') or None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        s = repr(v) if isinstance(v, float) else str(v)
        if "e" in s.lower():
            s = format(Decimal(s), "f")
    elif isinstance(v, str):
        if re.search(r"-\s*\d", v):
            return None
        s = re.sub(r"[^\d.,]", "", v)
        s = s.strip(".,")
        if not s:
            return None
        has_c, has_d = "," in s, "." in s
        if has_c and has_d:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif has_c:
            if s.count(",") > 1 or re.fullmatch(r"\d{1,3},\d{3}", s):
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
        elif has_d and s.count(".") > 1:
            s = s.replace(".", "")
    else:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite() or d <= 0 or d > MAX_PRICE:
        return None
    d = d.quantize(Decimal("0.01")) if d == d.quantize(Decimal("0.01")) else d
    txt = format(d, "f")
    if "." in txt:
        whole, frac = txt.split(".")
        frac = frac.rstrip("0")
        if not frac:
            return whole
        return "%s.%s" % (whole, frac.ljust(2, "0"))
    return txt


def _currency_code(v):
    if isinstance(v, str):
        v = v.strip()
        if re.fullmatch(r"[A-Za-z]{3}", v):
            return v.upper()
    return None


def _currency_from_text(s):
    """Map a symbol/word inside a price string to an ISO code."""
    if not isinstance(s, str):
        return None
    if "₪" in s or re.search(r"\bNIS\b", s, re.I) or \
            re.search(r"ש\"?ח|ש[״”]ח", s):
        return "ILS"
    if "£" in s:
        return "GBP"
    if "€" in s:
        return "EUR"
    if "$" in s:
        if re.search(r"[A-Za-z]\s*\$", s):      # CA$, A$, US$, MX$ ...
            return "USD" if re.search(r"\bUS\s*\$", s) else None
        return "USD"
    return None


def _safe_image(raw, base_url):
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw or raw.lower().startswith("data:"):
        return None
    try:
        absu = urljoin(base_url, raw)
        parts = urlsplit(absu)
        if parts.scheme == "http":
            parts = parts._replace(scheme="https")
        if parts.scheme != "https" or not parts.netloc or parts.username \
                or parts.password:
            return None
        absu = urlunsplit(parts._replace(fragment=""))
    except ValueError:
        return None
    if len(absu) > 1000 or any(ord(c) <= 32 for c in absu):
        return None
    return absu


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------

class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.itemprops = {}
        self.title = []
        self.in_title = False
        self.jsonld = []
        self._ld = None
        self.canonical = None
        self._pending = None
        self._pending_tag = None

    def _set_meta(self, d, key, val):
        key = key.strip().lower()
        if key and val is not None and key not in d:
            d[key] = val

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "title":
            self.in_title = True
        elif tag == "script":
            if "ld+json" in a.get("type", "").lower():
                self._ld = []
        elif tag == "meta":
            content = a.get("content")
            for k in ("property", "name"):
                if k in a:
                    self._set_meta(self.meta, a[k], content)
            if "itemprop" in a and content is not None:
                self._set_meta(self.itemprops, a["itemprop"], content)
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel and self.canonical is None and a.get("href"):
                self.canonical = a["href"]
        if tag != "meta" and "itemprop" in a:
            key = a["itemprop"].strip().lower()
            if key in ("price", "pricecurrency"):
                if "content" in a:
                    self._set_meta(self.itemprops, key, a["content"])
                elif key not in self.itemprops:
                    self._pending, self._pending_tag = key, tag

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self._ld is not None:
            self.jsonld.append("".join(self._ld))
            self._ld = None
        if self._pending and tag == self._pending_tag:
            self._pending = self._pending_tag = None

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
            return
        if self.in_title and len(self.title) < 50:
            self.title.append(data)
        if self._pending and data.strip():
            self._set_meta(self.itemprops, self._pending, data.strip())
            self._pending = self._pending_tag = None

    def close(self):
        super().close()
        if self._ld is not None:
            self.jsonld.append("".join(self._ld))
            self._ld = None


def _types(node):
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def _find_products(node, out, depth=0):
    if depth > 12 or len(out) >= 10:
        return
    if isinstance(node, list):
        for x in node:
            _find_products(x, out, depth + 1)
    elif isinstance(node, dict):
        if any(t.rsplit("/", 1)[-1] in ("Product", "ProductGroup", "IndividualProduct")
               for t in _types(node)):
            out.append(node)
        for k, v in node.items():
            if k != "@context" and isinstance(v, (dict, list)):
                _find_products(v, out, depth + 1)


def _offer_price(o, cur=None, depth=0):
    """-> (price_str, currency) or None; first offer that has a usable price."""
    if depth > 6:
        return None
    if isinstance(o, list):
        for x in o:
            r = _offer_price(x, cur, depth + 1)
            if r:
                return r
        return None
    if not isinstance(o, dict):
        return None
    c = _currency_code(o.get("priceCurrency")) or cur
    for key in ("price", "lowPrice"):
        if key in o:
            p = _norm_price(o[key])
            if p:
                return p, c or _currency_from_text(o[key] if isinstance(o[key], str) else None)
    spec = o.get("priceSpecification")
    if spec:
        r = _offer_price(spec, c, depth + 1)
        if r:
            return r
    if "offers" in o:
        return _offer_price(o["offers"], c, depth + 1)
    return None


def _json_image(v, base_url, depth=0):
    if depth > 4:
        return None
    if isinstance(v, str):
        return _safe_image(v, base_url)
    if isinstance(v, list):
        for x in v:
            r = _json_image(x, base_url, depth + 1)
            if r:
                return r
    elif isinstance(v, dict):
        for k in ("url", "contentUrl", "@id"):
            r = _json_image(v.get(k), base_url, depth + 1)
            if r:
                return r
    return None


def _json_name(v, depth=0):
    if isinstance(v, str):
        return _clean(v)
    if isinstance(v, dict) and depth < 3:
        return _json_name(v.get("name"), depth + 1)
    if isinstance(v, list) and depth < 3:
        for x in v:
            r = _json_name(x, depth + 1)
            if r:
                return r
    return None


def parse_html(html, base_url):
    """Extract product info from HTML. Pure; never raises on bad markup."""
    out = {"name": None, "price": None, "currency": None, "image": None,
           "brand": None, "site_name": None, "canonical": None}
    if not isinstance(html, str):
        return out
    base_url = base_url or ""
    col = _Collector()
    try:
        col.feed(html)
        col.close()
    except Exception:
        pass                      # keep whatever was collected so far
    meta, ip_ = col.meta, col.itemprops

    products = []
    for block in col.jsonld:
        try:
            data = json.loads(block.strip())
        except (ValueError, RecursionError):
            continue
        _find_products(data, products)

    out["site_name"] = _clean(meta.get("og:site_name"), 120)
    host = _display_host(base_url)

    # name
    raw_name = None
    for p in products:
        raw_name = _json_name(p.get("name"))
        if raw_name:
            break
    if not raw_name:
        raw_name = (_clean(meta.get("og:title")) or _clean(meta.get("twitter:title"))
                    or _clean("".join(col.title)))
    out["name"] = _clean_name(raw_name, out["site_name"], host)

    # price + currency
    price = cur = None
    for p in products:
        r = _offer_price(p.get("offers"))
        if r:
            price, cur = r
            break
    if not price:
        for pk, ck in (("product:price:amount", "product:price:currency"),
                       ("og:price:amount", "og:price:currency")):
            pr = _norm_price(meta.get(pk))
            if pr:
                price, cur = pr, _currency_code(meta.get(ck))
                break
    if not price:
        pr = _norm_price(ip_.get("price"))
        if pr:
            price, cur = pr, _currency_code(ip_.get("pricecurrency"))
            cur = cur or _currency_from_text(ip_.get("price"))
    if price:
        if not cur:
            for ck in ("product:price:currency", "og:price:currency"):
                cur = _currency_code(meta.get(ck))
                if cur:
                    break
        if not cur:
            cur = _currency_code(ip_.get("pricecurrency"))
        out["price"], out["currency"] = price, cur

    # image
    img = None
    for p in products:
        img = _json_image(p.get("image"), base_url)
        if img:
            break
    if not img:
        for k in ("og:image:secure_url", "og:image", "twitter:image",
                  "twitter:image:src"):
            img = _safe_image(meta.get(k), base_url)
            if img:
                break
    out["image"] = img

    # brand
    brand = None
    for p in products:
        brand = _json_name(p.get("brand"))
        if brand:
            break
    out["brand"] = _clean(brand or meta.get("product:brand"), 120)

    # canonical
    if col.canonical:
        try:
            c = urljoin(base_url, col.canonical.strip())
            cp = urlsplit(c)
            if cp.scheme in ("http", "https") and cp.hostname and len(c) <= MAX_URL_LEN \
                    and not any(ord(ch) <= 32 for ch in c):
                out["canonical"] = c
        except ValueError:
            pass
    return out


# --------------------------------------------------------------------------
# lookup
# --------------------------------------------------------------------------

def _result(ok=False, error=None, url="", host="", **kw):
    r = {"ok": ok, "error": error, "url": url, "host": host, "name": None,
         "price": None, "currency": None, "image": None, "brand": None,
         "site_name": None}
    r.update(kw)
    return r


def lookup(url, *, timeout=6.0, resolver=None, opener=None):
    """Fetch url and return product info. Never raises."""
    shown = url.strip() if isinstance(url, str) else ""
    cur_url = shown
    try:
        deadline = time.monotonic() + float(timeout)
        do_open = opener or _default_opener
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en,he;q=0.8",
            "Accept-Encoding": "gzip, identity",
        }
        target = shown
        redirects = 0
        while True:
            try:
                norm, ips = check_url(target, resolver=resolver)
            except LinkError as e:
                if redirects and e.code == "bad_url":
                    raise LinkError("fetch_failed", "bad redirect")
                raise
            cur_url = norm
            host = urlsplit(norm).hostname
            status = hdrs = body = None
            last = None
            for ip in ips[:3]:
                if time.monotonic() >= deadline:
                    raise LinkError("fetch_failed", "timeout")
                try:
                    status, hdrs, body = do_open(norm, host, ip, dict(headers), deadline)
                    break
                except OSError as e:     # includes timeouts, TLS errors
                    last = e
            if status is None:
                raise LinkError("fetch_failed", repr(last))
            hdrs = {str(k).lower(): str(v) for k, v in (hdrs or {}).items()}
            if status in REDIRECT_CODES:
                loc = hdrs.get("location")
                if not loc or redirects >= MAX_REDIRECTS:
                    raise LinkError("fetch_failed", "redirects")
                redirects += 1
                target = urljoin(norm, loc.strip())
                continue
            break

        if status >= 400 or status < 200:
            raise LinkError("fetch_failed", "status %s" % status)
        ctype = hdrs.get("content-type", "")
        if ctype.split(";")[0].strip().lower() not in HTML_TYPES:
            raise LinkError("not_html")
        text = _decode(_decompress(body or b"", hdrs.get("content-encoding")), ctype)

        info = parse_html(text, norm)
        final = _strip_tracking(norm)
        stored = final
        canon = info.pop("canonical", None)
        if canon:
            try:
                ch = (urlsplit(canon).hostname or "").lower().rstrip(".")
                fh = (urlsplit(final).hostname or "").lower().rstrip(".")
                if ch and _registrable(ch) == _registrable(fh):
                    stored = _strip_tracking(canon)
            except ValueError:
                pass
        res = _result(url=stored, host=_display_host(final),
                      **{k: info.get(k) for k in
                         ("name", "price", "currency", "image", "brand", "site_name")})
        if res["name"]:
            res["ok"] = True
        else:
            res["error"] = "no_data"
        return res
    except LinkError as e:
        code = e.code if e.code in ("bad_url", "blocked_host", "fetch_failed",
                                    "not_html", "too_big") else "fetch_failed"
        return _result(error=code, url=_safe_strip(cur_url), host=_display_host(cur_url))
    except Exception:
        return _result(error="fetch_failed", url=_safe_strip(cur_url),
                       host=_display_host(cur_url))


def _safe_strip(url):
    try:
        return _strip_tracking(url) if url else ""
    except Exception:
        return url or ""
