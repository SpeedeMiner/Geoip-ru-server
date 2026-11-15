"""Explicit provenance contract for unavailable v41 review-only inputs."""
from pathlib import Path
import re

STATUS = "diagnostic-unavailable"
HXEHEX_REPO = "hxehex/russia-mobile-internet-whitelist"
HXEHEX_FILES = {"hxehex-cidrwhitelist.txt": "cidrwhitelist.txt",
                "hxehex-ipwhitelist.txt": "ipwhitelist.txt"}
IPSUM = "antifilter-ipsum.lst"
IPSUM_LABEL = "ANTIFILTER IPSUM IPV4 /24 SUMMARY"
IPSUM_URL = "https://antifilter.download/list/ipsum.lst"


def placeholder(url):
    return f"# Optional source unavailable during this build: {url}\n".encode("ascii")


def unavailable_metadata(name, source, url, digest, size):
    if name == IPSUM:
        allowed = source == IPSUM_LABEL and url == IPSUM_URL
    elif name in HXEHEX_FILES and url:
        repo = re.escape(HXEHEX_REPO)
        path = re.escape(HXEHEX_FILES[name])
        allowed = source == f"ROLLING {name}" and (
            re.fullmatch(rf"https://api\.github\.com/repos/{repo}/(?:branches/main|git/trees/[0-9a-f]{{40}})", url)
            or re.fullmatch(rf"https://raw\.githubusercontent\.com/{repo}/[0-9a-f]{{40}}/{path}", url))
    else:
        allowed = False
    if not allowed or digest != "-" or size != "0":
        raise ValueError(f"unexpected unavailable diagnostic input: {name}")
    return placeholder(url)


def verify_unavailable_file(name, source, url, digest, size):
    expected = unavailable_metadata(name, source, url, digest, size)
    with Path(name).open("rb") as stream:
        if stream.read(len(expected) + 1) != expected:
            raise ValueError(f"diagnostic placeholder mismatch: {name}")
