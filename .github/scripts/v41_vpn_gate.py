#!/usr/bin/env python3
"""Review-only v41 exact RU VPN runner. No publication or routing writes."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib import parse, request

from v41_vpn_exact_probe import bind_snapshot, load_exact_targets, measure_exact, observation, public_ipv4

REPO = "SpeedeMiner/Geoip-ru-server"
VPNOBRATNO = "https://vpnobratno.info/russia_server_list.html"
VPNGATE = "https://www.vpngate.net/api/iphone/"
PROFILE_PATH = re.compile(r"/servers/(?P<host>vpn[0-9]+\.opengw\.net)/(?P=host)_(ip|ddns)_(udp|tcp)\.ovpn")
PROFILE_LIMIT = 64000
CONTROL = "https://example.com/"
METADATA = ("https://ipwho.is/", "https://ipapi.co/json/", "https://ipinfo.io/json")
FILES = {"geoip_RU_v41_release_manifest.json": 16384, "geoip_RU.dat": 8 << 20, "geoip_RU.dat.sha256sum": 256}
CIPHERS = {"AES-128-CBC", "AES-192-CBC", "AES-256-CBC", "AES-128-GCM", "AES-256-GCM"}
DIGESTS = {"SHA1", "SHA256", "SHA384", "SHA512"}
TUN = "tun0"
TAP = "tap0"
OPENVPN_MARK = 65


class ProbeError(RuntimeError):
    pass


class AbortRun(BaseException):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url, cap=8192, *, timeout=8, method="GET"):
    # No environment proxy, redirect or TLS downgrade.
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    req = request.Request(url, method=method, headers={"User-Agent": "GeoIP-v41-exact-probe"})
    with opener.open(req, timeout=timeout) as stream:
        if stream.status != 200:
            raise ProbeError("non-200 HTTPS response")
        body = stream.read(cap + 1) if method != "HEAD" else b""
    if len(body) > cap:
        raise ProbeError("HTTPS resource exceeds byte limit")
    return body


def hex_pin(value, length):
    if not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        raise ValueError("expected a full lowercase hexadecimal pin")
    return value


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and isinstance(v, str))


def profile_links(html):
    parser = Links()
    parser.feed(html)
    by_host = {}
    for href in parser.links:
        try:
            url = parse.urlsplit(parse.urljoin(VPNOBRATNO, href))
        except ValueError:
            continue
        match = PROFILE_PATH.fullmatch(url.path)
        if url.scheme != "https" or url.netloc != "vpnobratno.info" or url.query or url.fragment or not match:
            continue
        host, mode, protocol = match.groups()
        by_host.setdefault(host, {})[mode, protocol] = url.geturl()
    priority = (("ip", "udp"), ("ddns", "udp"), ("ip", "tcp"), ("ddns", "tcp"))
    ordered = [sorted(variants, key=priority.index) for variants in by_host.values()]
    hosts = list(by_host)
    return [(host, *ordered[i][j], by_host[host][ordered[i][j]])
            for j in range(4) for i, host in enumerate(hosts) if j < len(ordered[i])][:24]


def parse_profile(config, *, listing_ip=None, hostname=None, mode=None, transport=None, resolved_ddns=None):
    if not isinstance(config, str) or not 0 < len(config.encode()) <= PROFILE_LIMIT:
        raise ValueError("profile exceeds byte limit")
    options, blocks = {}, {}
    inline = None
    for line in config.splitlines():
        line = line.strip()
        if inline:
            if line.lower() == f"</{inline}>":
                inline = None
            elif line.startswith("<"):
                raise ValueError("unexpected nested inline tag")
            elif inline in blocks:
                blocks[inline].append(line)
            continue
        tag = re.fullmatch(r"<([a-z0-9-]+)>", line.lower())
        if tag:
            inline = tag[1]
            if inline in {"ca", "tls-auth", "tls-crypt"}:
                if inline in blocks:
                    raise ValueError("duplicate inline material")
                blocks[inline] = []
        elif line and not line.startswith(("#", ";")):
            fields = shlex.split(line, comments=True)
            if not fields:
                continue
            key = fields[0].lower()
            if key in {"remote", "proto", "cipher", "auth", "key-direction", "verify-x509-name",
                       "tls-auth", "tls-crypt", "tls-crypt-v2"}:
                if key in options:
                    raise ValueError("duplicate supported profile directive")
                options[key] = fields[1:]
    if inline:
        raise ValueError("unterminated inline material")
    remote, protocol = options.get("remote", []), options.get("proto", [])
    if len(remote) != 2 or len(protocol) != 1:
        raise ValueError("expected one remote host/port and protocol")
    if not re.fullmatch(r"[0-9]{1,5}", remote[1]) or not 1 <= int(remote[1]) <= 65535:
        raise ValueError("invalid OpenVPN port")
    proto = {"udp": "udp", "udp4": "udp", "tcp": "tcp", "tcp4": "tcp",
             "tcp-client": "tcp", "tcp4-client": "tcp"}.get(protocol[0].lower())
    if not proto or (transport is not None and proto != transport):
        raise ValueError("unsupported or mismatched OpenVPN protocol")
    if listing_ip is not None:
        # The official CSV binds the connection to its public server IP.
        address = public_ipv4(listing_ip)
    elif mode == "ip":
        address = public_ipv4(remote[0])
    elif mode == "ddns" and hostname == remote[0].rstrip(".").lower():
        if resolved_ddns is not None:
            address = public_ipv4(resolved_ddns)
        else:
            addresses = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
            public = []
            for item in addresses:
                try:
                    public.append(public_ipv4(item[4][0]))
                except ValueError:
                    continue
            if not public:
                raise ValueError("no public DDNS answer")
            address = min(public)
    else:
        raise ValueError("OpenVPN hostname does not match listing")
    if "ca" not in blocks:
        raise ValueError("missing inline CA")
    ca = "\n".join(blocks["ca"]).strip()
    cert = r"-----BEGIN CERTIFICATE-----\n(?:[A-Za-z0-9+/=]{1,76}\n)+-----END CERTIFICATE-----"
    if not re.fullmatch(rf"{cert}(?:\n+{cert})*", ca):
        raise ValueError("invalid inline CA syntax")
    for pem in re.findall(cert, ca):
        # Syntax and bounded decoded data before OpenVPN ever sees this PEM.
        der = base64.b64decode("".join(pem.splitlines()[1:-1]), validate=True)
        if not der or der[0] != 0x30:
            raise ValueError("invalid certificate encoding")
    if "tls-crypt-v2" in options or set(blocks) >= {"tls-auth", "tls-crypt"}:
        raise ValueError("unsupported inline key setup")
    for key in ("tls-auth", "tls-crypt"):
        if key in options and (key not in blocks or options[key] not in (["[inline]"], ["[inline]", "1"], ["[inline]", "0"])):
            raise ValueError("external TLS key is not allowed")
        if key in blocks:
            lines = blocks[key]
            if (len(lines) < 3 or lines[0] != "-----BEGIN OpenVPN Static key V1-----"
                    or lines[-1] != "-----END OpenVPN Static key V1-----"
                    or not re.fullmatch(r"[0-9a-fA-F]{512}", "".join(lines[1:-1]))):
                raise ValueError("invalid inline OpenVPN static key")
    name = options.get("verify-x509-name", [])
    if name and (len(name) not in (1, 2) or not re.fullmatch(r"[A-Za-z0-9_.:,=/+ -]{1,200}", name[0])
                 or (len(name) == 2 and name[1] not in {"name", "subject"})):
        raise ValueError("invalid certificate identity")
    cipher = options.get("cipher", ["AES-128-CBC"])
    auth = options.get("auth", ["SHA1"])
    direction = options.get("key-direction", options.get("tls-auth", ["[inline]", "1"])[1:] or ["1"])
    if len(cipher) != 1 or cipher[0] not in CIPHERS or len(auth) != 1 or auth[0] not in DIGESTS:
        raise ValueError("unsupported OpenVPN cipher or digest")
    if direction not in (["0"], ["1"]):
        raise ValueError("invalid OpenVPN key direction")
    lines = ["client", f"dev {TUN}", f"proto {'tcp4-client' if proto == 'tcp' else 'udp4'}",
             f"remote {address} {remote[1]}", "nobind", "auth-user-pass auth.txt", "auth-nocache",
             "remote-cert-tls server", "tls-version-min 1.2", "allow-compression no",
             "route-nopull", "redirect-gateway def1", "disable-dco", f"mark {OPENVPN_MARK}",
             "connect-retry-max 1", "verb 3",
             "data-ciphers AES-256-GCM:AES-128-GCM:AES-128-CBC",
             f"data-ciphers-fallback {cipher[0]}", f"auth {auth[0]}", "<ca>", ca, "</ca>"]
    if name:
        lines.append(f'verify-x509-name "{name[0]}"' + (f" {name[1]}" if len(name) == 2 else ""))
    for key in ("tls-auth", "tls-crypt"):
        if key in blocks:
            if key == "tls-auth":
                lines.append(f"key-direction {direction[0]}")
            lines.extend((f"<{key}>", *blocks[key], f"</{key}>"))
    return str(address), int(remote[1]), proto, "\n".join(lines) + "\n"


def discover(source, maximum):
    if source == "vpnobratno":
        links = profile_links(fetch(VPNOBRATNO, 2_000_000).decode("utf-8", "strict"))
        for host, mode, transport, url in links:
            try:
                candidate = {"profile": fetch(url, PROFILE_LIMIT).decode("utf-8"),
                             "hostname": host, "mode": mode, "transport": transport}
                address, _, _, _ = parse_profile(candidate["profile"], hostname=host, mode=mode, transport=transport)
                if mode == "ddns":
                    candidate["resolved_ddns"] = address
            except (OSError, ValueError, ProbeError):
                continue
            yield candidate
            maximum -= 1
            if not maximum:
                return
    else:
        raw = fetch(VPNGATE, 8_000_000).decode("utf-8", "strict")
        header = next((ix for ix, line in enumerate(raw.splitlines()) if line.startswith("#HostName,")), None)
        if header is None:
            raise ProbeError("invalid VPN Gate CSV")
        records = raw.splitlines()[header:]
        records[0] = records[0][1:]
        seen = set()
        for row in csv.DictReader(records):
            address = row.get("IP")
            if row.get("CountryShort") != "RU" or address in seen:
                continue
            try:
                public_ipv4(address)
                encoded = row.get("OpenVPN_ConfigData_Base64") or ""
                if not 0 < len(encoded) <= 86000:
                    continue
                config = base64.b64decode(encoded, validate=True).decode("utf-8")
                parse_profile(config, listing_ip=address)
            except (ValueError, OSError):
                continue
            seen.add(address)
            yield {"profile": config, "listing_ip": address}
            maximum -= 1
            if not maximum:
                return


def atomic_json(path, payload):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def current_release():
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    row = subprocess.run(
        ["git", "ls-remote", "--exit-code", f"https://github.com/{REPO}.git", "refs/heads/release"],
        env=env, text=True, check=True, capture_output=True, timeout=20,
    ).stdout.strip().split("\t")
    if len(row) != 2 or row[1] != "refs/heads/release":
        raise ProbeError("could not verify current release commit")
    return hex_pin(row[0], 40)


def prepare(args):
    args.report.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(args.report, {"schema": 1, "status": "NOT_TESTED", "targets": [], "attempts": []})
    path = Path(args.work)
    sha = hex_pin(os.environ["V41_RELEASE_COMMIT"], 40)
    checksum = hex_pin(os.environ["V41_MANIFEST_SHA256"], 64)
    raw = os.environ["V41_TARGETS_JSON"].encode("utf-8")
    if not 0 < len(raw) <= 8192:
        raise ValueError("exact target JSON size must be 1–8192 bytes")
    source = os.environ["V41_PROFILE_SOURCE"]
    count = os.environ["V41_MAX_ATTEMPTS"]
    if source not in {"vpnobratno", "vpngate"} or not re.fullmatch(r"[1-6]", count):
        raise ValueError("unsupported provider or maximum connections outside 1–6")
    (path / "targets.json").write_bytes(raw)
    targets = load_exact_targets(path / "targets.json")
    if current_release() != sha:
        raise ProbeError("provided pin is not the current release")
    for name, cap in FILES.items():
        url = f"https://raw.githubusercontent.com/{REPO}/{sha}/{name}"
        (path / name).write_bytes(fetch(url, cap, timeout=15))
    pin, memberships = bind_snapshot(path, sha, checksum, targets)
    atomic_json(args.report, {"schema": 1, "snapshot": pin, "provider": source, "status": "NOT_TESTED",
                              "attempts": [], "targets": [observation({**t, **m}) for t, m in zip(targets, memberships)]})
    # Keep plain profiles only in the private runner work directory, never in artifacts.
    profiles = list(discover(source, int(count)))
    atomic_json(path / "measure.json", {"release_commit": sha, "manifest_sha256": checksum,
                                      "provider": source, "profiles": profiles})
    if not profiles:
        raise ProbeError("no supported public VPN profiles")


def command(*args, data=None):
    return subprocess.run(args, input=data, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=6).stdout


def assert_isolated():
    if os.geteuid() != 0:
        raise ProbeError("network setup requires privilege inside the isolated namespace")
    name = os.environ.get("V41_ISOLATED_NAMESPACE", "")
    if not re.fullmatch(r"v41-vpn-[A-Za-z0-9]{8}", name):
        raise ProbeError("run only through the network namespace wrapper")
    current = os.stat("/proc/self/ns/net")
    named = os.stat(f"/run/netns/{name}")
    if not os.path.samestat(current, named) or os.path.samestat(current, os.stat("/proc/1/ns/net")):
        raise ProbeError("refusing to modify the host network namespace")


@contextmanager
def firewall(relay, port, proto, *, run=command):
    """All rules are installed in a throwaway namespace, with restoration on every exit."""
    before4 = run("iptables-save", "-t", "filter")
    before6 = run("ip6tables-save", "-t", "filter")
    drop6 = b"*filter\n:INPUT DROP [0:0]\n:FORWARD DROP [0:0]\n:OUTPUT DROP [0:0]\nCOMMIT\n"
    rules = (
        "*filter\n:INPUT DROP [0:0]\n:FORWARD DROP [0:0]\n:OUTPUT DROP [0:0]\n"
        "-A INPUT -i lo -j ACCEPT\n-A OUTPUT -o lo -j ACCEPT\n"
        f"-A INPUT -i {TUN} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT\n"
        f"-A OUTPUT -o {TUN} -j ACCEPT\n"
        f"-A INPUT -i {TAP} -s {relay} -p {proto} --sport {port} -m conntrack --ctstate ESTABLISHED -j ACCEPT\n"
        f"-A OUTPUT -o {TAP} -d {relay} -p {proto} --dport {port} -m mark --mark {OPENVPN_MARK} -j ACCEPT\nCOMMIT\n"
    ).encode("ascii")
    try:
        run("ip6tables-restore", data=drop6)
        run("iptables-restore", data=rules)
        yield
    finally:
        failures = []
        # Keep direct egress blocked until the OpenVPN process has stopped.
        for tool, snapshot in (("iptables-restore", before4), ("ip6tables-restore", before6)):
            try:
                run(tool, data=snapshot if snapshot else b"*filter\n:INPUT ACCEPT [0:0]\n:FORWARD ACCEPT [0:0]\n:OUTPUT ACCEPT [0:0]\nCOMMIT\n")
            except (OSError, subprocess.SubprocessError):
                failures.append(tool)
        if failures:
            # Outer wrapper must discard the namespace rather than try another profile.
            raise AbortRun("namespace firewall restoration failed")


def route_uses_tun(address):
    route = json.loads(command("ip", "-4", "-j", "route", "get", address))
    return len(route) == 1 and route[0].get("dev") == TUN


def metadata_identity(payload):
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise ValueError("invalid metadata")
    address = str(public_ipv4(payload.get("ip")))
    country = payload.get("country_code") or payload.get("country")
    connection = payload.get("connection")
    if not isinstance(connection, dict):
        connection = {}
    raw = connection.get("asn") or payload.get("asn") or payload.get("org")
    match = re.fullmatch(r"(?:AS)?([1-9][0-9]{0,9})(?: .*)?", str(raw))
    asn = int(match[1]) if match else 0
    if not isinstance(country, str) or not re.fullmatch("[A-Z]{2}", country) or not 0 < asn <= 0xffffffff:
        raise ValueError("missing country or ASN")
    return address, asn, country


def verify_exit(*, transfer=fetch):
    votes = Counter()
    for endpoint in METADATA:
        try:
            identity = metadata_identity(json.loads(transfer(endpoint)))
        except (OSError, ValueError, ProbeError):
            continue
        votes[identity] += 1
        address, asn, country = identity
        if votes[identity] == 2 and country == "RU":
            transfer(CONTROL, cap=0, method="HEAD")
            return {"ipv4": address, "asn": asn, "country": country, "https_status": 200, "agreeing_sources": 2}
    raise ProbeError("no independent agreement on RU IPv4 and ASN")


def same_exit(before, after):
    for value in (before, after):
        try:
            public_ipv4(value.get("ipv4"))
        except (AttributeError, ValueError):
            return False
        if type(value.get("asn")) is not int or not 0 < value["asn"] <= 0xffffffff:
            return False
    return (isinstance(before, dict) and isinstance(after, dict)
            and before.get("country") == after.get("country") == "RU"
            and before.get("https_status") == after.get("https_status") == 200
            and before.get("ipv4") == after.get("ipv4") and before.get("asn") == after.get("asn")
            and before.get("agreeing_sources") == after.get("agreeing_sources") == 2)


def sanitize_openvpn(raw):
    """Preserve only fixed diagnostic categories, never a log line or remote identifier."""
    markers = {
        b"Initialization Sequence Completed": "TUN_INITIALIZED",
        b"VERIFY ERROR": "CERTIFICATE_REJECTED",
        b"AUTH_FAILED": "AUTH_REJECTED",
        b"TLS Error": "TLS_ERROR",
        b"Connection reset": "TRANSPORT_RESET",
        b"SIGTERM": "TERMINATED",
    }
    return sorted({v for k, v in markers.items() if k in raw[-65536:]})


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_series(targets, report, *, save, control=verify_exit, measure=measure_exact, via_tun=route_uses_tun):
    before = control()
    report.update(preflight=before, postflight=None, status="POSTFLIGHT_INCONCLUSIVE")
    save(report)
    series_complete = False
    verified = False
    try:
        for i, target in enumerate(targets):
            if via_tun(target["ip"]):
                row = measure(target, 5)
            else:
                row = observation(target)
                row["tcp"] = "PROBE_ERROR"
                row["errors"]["tcp"] = "ROUTE_NOT_TUNNEL"
            report["targets"][i] = row
            save(report)
        series_complete = True
    finally:
        # The last persisted state is inconclusive even on cancellation or a forced stop.
        report["status"] = "POSTFLIGHT_INCONCLUSIVE"
        try:
            after = control()
            report["postflight"] = after
            verified = series_complete and same_exit(before, after)
            if not verified:
                report["postflight_error"] = "EXIT_CHANGED_OR_SERIES_INCOMPLETE"
        except (OSError, ValueError, ProbeError):
            report["postflight_error"] = "CONTROL_OR_EXIT_UNVERIFIED"
        finally:
            save(report)
    return verified


def measure(args):
    assert_isolated()
    path = Path(args.work)
    prepared = json.loads((path / "measure.json").read_text())
    targets = load_exact_targets(path / "targets.json")
    pin, memberships = bind_snapshot(path, prepared["release_commit"], prepared["manifest_sha256"], targets)
    targets = [{**t, **m} for t, m in zip(targets, memberships)]
    profiles = prepared["profiles"]
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 6:
        raise ValueError("invalid bounded profile list")
    report = {"schema": 1, "snapshot": pin, "provider": prepared["provider"], "status": "NOT_TESTED",
              "started_at": datetime.now(timezone.utc).isoformat(), "attempts": [],
              "targets": [observation(t) for t in targets]}
    save = lambda payload: atomic_json(args.report, payload)
    save(report)
    for number, profile in enumerate(profiles, 1):
        attempt = {"attempt": number, "status": "PROBE_ERROR", "openvpn": []}
        report["attempts"].append(attempt)
        save(report)
        process = None
        with tempfile.TemporaryDirectory(prefix="v41-openvpn-", dir=path) as temp, tempfile.TemporaryFile() as raw:
            try:
                address, port, proto, conf = parse_profile(**{
                    "config": profile["profile"],
                    **{k: profile[k] for k in ("listing_ip", "hostname", "mode", "transport", "resolved_ddns") if k in profile},
                })
                root = Path(temp)
                (root / "client.ovpn").write_text(conf, encoding="utf-8")
                (root / "auth.txt").write_text("vpn\nvpn\n", encoding="utf-8")
                os.chmod(root / "auth.txt", 0o600)
                with firewall(address, port, proto):
                    try:
                        process = subprocess.Popen(["openvpn", "--config", "client.ovpn"], cwd=root,
                                                   stdin=subprocess.DEVNULL, stdout=raw, stderr=subprocess.STDOUT)
                        deadline = time.monotonic() + 12
                        while not route_uses_tun("1.1.1.1"):
                            if process.poll() is not None or time.monotonic() >= deadline:
                                raise ProbeError("tunnel not ready")
                            time.sleep(0.25)
                        verified = run_series(targets, report, save=save)
                    finally:
                        if process:
                            stop(process)
                if verified:
                    report["status"] = "VERIFIED"
                attempt["status"] = report["status"]
                # Never mix a partial series with observations from another exit.
                return 0 if verified else 2
            except (OSError, ValueError, ProbeError, subprocess.SubprocessError) as exc:
                attempt["error"] = type(exc).__name__
                if report.get("preflight"):
                    report["status"] = "POSTFLIGHT_INCONCLUSIVE"
                    return 2
            finally:
                raw.seek(max(0, raw.seek(0, os.SEEK_END) - 65536))
                attempt["openvpn"] = sanitize_openvpn(raw.read(65536))
                save(report)
    report["status"] = "PROBE_ERROR"
    save(report)
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "measure"))
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077 if args.stage == "prepare" else 0o022)
    def abort(signum, _frame):
        raise AbortRun("terminated by watchdog")
    signal.signal(signal.SIGTERM, abort)
    signal.signal(signal.SIGINT, abort)
    try:
        return (prepare if args.stage == "prepare" else measure)(args) or 0
    except (OSError, ProbeError, ValueError, KeyError, subprocess.SubprocessError, AbortRun) as exc:
        # Do not show exception text derived from profile contents or network responses.
        if args.stage == "prepare" and args.report.is_file():
            data = json.loads(args.report.read_text())
            data.update(status="PROBE_ERROR", prepare_error=type(exc).__name__)
            atomic_json(args.report, data)
        print(f"v41 exact VPN {args.stage}: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
