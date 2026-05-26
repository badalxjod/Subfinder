"""
bot/scanner/sources.py — All 16 OSINT subdomain sources.

Each public function takes a domain string and returns set[str].
Low-level HTTP helpers (_get_json / _get_text) create a fresh aiohttp
session per request so they can safely run inside asyncio.gather().
"""

import re
import asyncio

import aiohttp

from bot.config        import SOURCE_TIMEOUT
from bot.helpers       import clean_subdomain
from bot.logger        import log

# ── HTTP helpers ────────────────────────────────────────────────
_HEADERS = {"User-Agent": "Mozilla/5.0 SubHunterBot/5.0"}
_TIMEOUT  = aiohttp.ClientTimeout(total=SOURCE_TIMEOUT)


async def _get_json(url: str, source: str, domain: str):
    try:
        async with aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT) as s:
            async with s.get(url) as r:
                log.debug(f"[{source}] {domain} HTTP {r.status}")
                if r.status == 200:
                    return await r.json(content_type=None)
                log.warning(f"[{source}] {domain} non-200: {r.status}")
    except asyncio.TimeoutError:
        log.warning(f"[{source}] {domain} TIMEOUT ({SOURCE_TIMEOUT}s)")
    except aiohttp.ClientError as exc:
        log.warning(f"[{source}] {domain} ClientError: {exc}")
    except Exception as exc:
        log.error(f"[{source}] {domain} {type(exc).__name__}: {exc}")
    return None


async def _get_text(url: str, source: str, domain: str) -> str | None:
    try:
        async with aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT) as s:
            async with s.get(url) as r:
                log.debug(f"[{source}] {domain} HTTP {r.status}")
                if r.status == 200:
                    return await r.text()
                log.warning(f"[{source}] {domain} non-200: {r.status}")
    except asyncio.TimeoutError:
        log.warning(f"[{source}] {domain} TIMEOUT ({SOURCE_TIMEOUT}s)")
    except aiohttp.ClientError as exc:
        log.warning(f"[{source}] {domain} ClientError: {exc}")
    except Exception as exc:
        log.error(f"[{source}] {domain} {type(exc).__name__}: {exc}")
    return None


# ── Source functions ────────────────────────────────────────────

async def src_devxdark(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://newsubfinder-bydevxdark.vercel.app/api/subdomains/{domain}",
        "DEVxDARK", domain,
    )
    if data:
        for sub in data.get("subdomains", []):
            s = clean_subdomain(sub, domain)
            if s: res.add(s)
    log.info(f"[DEVxDARK] {domain} -> {len(res)}")
    return res


async def src_crtsh(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://crt.sh/?q=%.{domain}&output=json", "crt.sh", domain
    )
    if data:
        for entry in data:
            for name in entry.get("name_value", "").split("\n"):
                s = clean_subdomain(name, domain)
                if s: res.add(s)
    log.info(f"[crt.sh] {domain} -> {len(res)}")
    return res


async def src_hackertarget(domain: str) -> set:
    res  = set()
    text = await _get_text(
        f"https://api.hackertarget.com/hostsearch/?q={domain}",
        "HackerTarget", domain,
    )
    if text and "error" not in text[:30].lower():
        for line in text.strip().split("\n"):
            s = clean_subdomain(line.split(",")[0], domain)
            if s: res.add(s)
    log.info(f"[HackerTarget] {domain} -> {len(res)}")
    return res


async def src_alienvault(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns",
        "AlienVault", domain,
    )
    if data:
        for entry in data.get("passive_dns", []):
            s = clean_subdomain(entry.get("hostname", ""), domain)
            if s: res.add(s)
    log.info(f"[AlienVault] {domain} -> {len(res)}")
    return res


async def src_rapiddns(domain: str) -> set:
    res  = set()
    text = await _get_text(
        f"https://rapiddns.io/subdomain/{domain}?full=1", "RapidDNS", domain
    )
    if text:
        pattern = r'<td>([a-z0-9._-]+\.' + re.escape(domain) + r')</td>'
        for m in re.findall(pattern, text):
            s = clean_subdomain(m, domain)
            if s: res.add(s)
    log.info(f"[RapidDNS] {domain} -> {len(res)}")
    return res


async def src_anubis(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://jonlu.ca/anubis/subdomains/{domain}", "Anubis-DB", domain
    )
    if isinstance(data, list):
        for sub in data:
            s = clean_subdomain(sub, domain)
            if s: res.add(s)
    log.info(f"[Anubis-DB] {domain} -> {len(res)}")
    return res


async def src_urlscan(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://urlscan.io/api/v1/search/?q=domain:{domain}&size=200",
        "URLScan", domain,
    )
    if data:
        for entry in data.get("results", []):
            s = clean_subdomain(entry.get("page", {}).get("domain", ""), domain)
            if s: res.add(s)
    log.info(f"[URLScan] {domain} -> {len(res)}")
    return res


async def src_virustotal(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://www.virustotal.com/ui/domains/{domain}/subdomains?limit=40",
        "VirusTotal", domain,
    )
    if data:
        for item in data.get("data", []):
            s = clean_subdomain(item.get("id", ""), domain)
            if s: res.add(s)
    log.info(f"[VirusTotal] {domain} -> {len(res)}")
    return res


async def src_wayback(domain: str) -> set:
    res  = set()
    url  = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url=*.{domain}&output=json&fl=original&collapse=urlkey&limit=500"
    )
    data = await _get_json(url, "Wayback", domain)
    if data:
        for row in data[1:]:
            m = re.match(r'https?://([^/]+)', row[0])
            if m:
                s = clean_subdomain(m.group(1), domain)
                if s: res.add(s)
    log.info(f"[Wayback] {domain} -> {len(res)}")
    return res


async def src_certspotter(domain: str) -> set:
    res  = set()
    url  = (
        f"https://api.certspotter.com/v1/issuances"
        f"?domain={domain}&include_subdomains=true&expand=dns_names"
    )
    data = await _get_json(url, "CertSpotter", domain)
    if isinstance(data, list):
        for entry in data:
            for name in entry.get("dns_names", []):
                s = clean_subdomain(name, domain)
                if s: res.add(s)
    log.info(f"[CertSpotter] {domain} -> {len(res)}")
    return res


async def src_merklemap(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://www.merklemap.com/api/search?query={domain}&page=0",
        "MerkleMap", domain,
    )
    if data:
        for item in data.get("results", []):
            sub_part = item.get("subdomain", "").strip()
            if sub_part:
                s = clean_subdomain(f"{sub_part}.{domain}", domain)
                if s: res.add(s)
    log.info(f"[MerkleMap] {domain} -> {len(res)}")
    return res


async def src_columbus(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://columbus.elmasy.com/api/lookup/{domain}", "Columbus", domain
    )
    if isinstance(data, list):
        for sub in data:
            if isinstance(sub, str) and sub:
                full = sub if sub.endswith(f".{domain}") else f"{sub}.{domain}"
                s    = clean_subdomain(full, domain)
                if s: res.add(s)
    log.info(f"[Columbus] {domain} -> {len(res)}")
    return res


async def src_subdomain_center(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://api.subdomain.center/?domain={domain}",
        "SubdomainCenter", domain,
    )
    if isinstance(data, list):
        for sub in data:
            s = clean_subdomain(sub, domain)
            if s: res.add(s)
    log.info(f"[SubdomainCenter] {domain} -> {len(res)}")
    return res


async def src_jldc(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://jldc.me/anubis/subdomains/{domain}", "JLDC", domain
    )
    if isinstance(data, list):
        for sub in data:
            s = clean_subdomain(sub, domain)
            if s: res.add(s)
    log.info(f"[JLDC] {domain} -> {len(res)}")
    return res


async def src_leakix(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://leakix.net/api/subdomains/{domain}", "LeakIX", domain
    )
    if isinstance(data, list):
        for entry in data:
            s = clean_subdomain(entry.get("subdomain", ""), domain)
            if s: res.add(s)
    log.info(f"[LeakIX] {domain} -> {len(res)}")
    return res


async def src_threatminer(domain: str) -> set:
    res  = set()
    data = await _get_json(
        f"https://api.threatminer.org/v2/domain.php?q={domain}&rt=5",
        "ThreatMiner", domain,
    )
    if data:
        for sub in data.get("results", []):
            s = clean_subdomain(sub, domain)
            if s: res.add(s)
    log.info(f"[ThreatMiner] {domain} -> {len(res)}")
    return res


# ── Registry ────────────────────────────────────────────────────
# Maps name → (async_function, emoji)
ALL_SOURCES: dict = {
    "DEVxDARK":        (src_devxdark,         "🔥"),
    "crt.sh":          (src_crtsh,            "📜"),
    "HackerTarget":    (src_hackertarget,     "🎯"),
    "AlienVault":      (src_alienvault,       "👾"),
    "RapidDNS":        (src_rapiddns,         "⚡"),
    "Anubis-DB":       (src_anubis,           "🐉"),
    "URLScan":         (src_urlscan,          "🔍"),
    "VirusTotal":      (src_virustotal,       "🦠"),
    "Wayback":         (src_wayback,          "🕰️"),
    "CertSpotter":     (src_certspotter,      "🔐"),
    "MerkleMap":       (src_merklemap,        "🌳"),
    "Columbus":        (src_columbus,         "🗺️"),
    "SubdomainCenter": (src_subdomain_center, "🎪"),
    "JLDC":            (src_jldc,            "🔮"),
    "LeakIX":          (src_leakix,          "💧"),
    "ThreatMiner":     (src_threatminer,     "⚔️"),
}
