#!/usr/bin/env python3
"""Exercise Xray and sing-box against real v41 assets with loopback-only fixtures.

Run inside an isolated Linux network namespace with only loopback enabled.
The fake SOCKS listeners report which route was selected and never dial targets.
"""
import argparse
from contextlib import contextmanager
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
from socketserver import StreamRequestHandler, ThreadingTCPServer, ThreadingUDPServer, BaseRequestHandler
import struct
import sys
import subprocess
from tempfile import TemporaryDirectory
from threading import Lock, Thread
import time

LOCAL = "127.0.0.1"
OVERLAP = "overlap.fixture.test"
WHITELIST = "white.fixture.test"
ANSWERS = {
    OVERLAP: "77.88.8.8",
    WHITELIST: "8.8.8.8",
    "ru4.fixture.test": "77.88.8.8",
    "foreign4.fixture.test": "8.8.8.8",
    "private4.fixture.test": "192.168.50.50",
    "telegram4.fixture.test": "149.154.167.50",
    "ru6.fixture.test": "2a02:6b8::feed:ff",
    "foreign6.fixture.test": "2001:4860:4860::8888",
    "private6.fixture.test": "fd00::10",
    "telegram6.fixture.test": "2001:67c:4e8::10",
}
CASES = [
    ("proxy-domain-before-whitelist-and-dns", OVERLAP, "proxy", False),
    ("whitelist-domain-before-foreign-dns", WHITELIST, "direct", False),
    ("dns-ru-v4", "ru4.fixture.test", "direct", True),
    ("dns-foreign-v4", "foreign4.fixture.test", "proxy", True),
    ("dns-private-v4", "private4.fixture.test", "direct", True),
    ("dns-telegram-v4", "telegram4.fixture.test", "proxy", True),
    ("resolved-ru-v6", "ru6.fixture.test", "direct", True),
    ("resolved-foreign-v6", "foreign6.fixture.test", "proxy", True),
    ("resolved-private-v6", "private6.fixture.test", "direct", True),
    ("resolved-telegram-v6", "telegram6.fixture.test", "proxy", True),
    ("literal-ru-v4", ANSWERS["ru4.fixture.test"], "direct", False),
    ("literal-foreign-v4", ANSWERS["foreign4.fixture.test"], "proxy", False),
    ("literal-private-v4", ANSWERS["private4.fixture.test"], "direct", False),
    ("literal-telegram-v4", ANSWERS["telegram4.fixture.test"], "proxy", False),
    ("literal-ru-v6", ANSWERS["ru6.fixture.test"], "direct", False),
    ("literal-foreign-v6", ANSWERS["foreign6.fixture.test"], "proxy", False),
    ("literal-private-v6", ANSWERS["private6.fixture.test"], "direct", False),
    ("literal-telegram-v6", ANSWERS["telegram6.fixture.test"], "proxy", False),
]
PONG = b"fixture-ok\n"
DST_PORT = 443
LOCK = Lock()


def read_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        data = sock.recv(n - len(buf))
        if not data:
            raise EOFError("SOCKS connection closed")
        buf.extend(data)
    return bytes(buf)


def decode_addr(sock, typ):
    if typ == 3:
        return read_exact(sock, read_exact(sock, 1)[0]).decode("ascii")
    return str(ipaddress.ip_address(read_exact(sock, {1: 4, 4: 16}[typ])))


class SocksListener(StreamRequestHandler):
    def handle(self):
        s = self.request
        s.settimeout(4)
        try:
            version, methods = read_exact(s, 2)
            if version != 5 or 0 not in read_exact(s, methods):
                raise ValueError("expected SOCKS5/no-auth")
            s.sendall(b"\x05\x00")
            version, cmd, reserved, typ = read_exact(s, 4)
            if (version, cmd, reserved) != (5, 1, 0):
                raise ValueError("expected SOCKS5 CONNECT")
            dest = decode_addr(s, typ)
            port, = struct.unpack("!H", read_exact(s, 2))
            with LOCK:
                self.server.deliveries.append({"lane": self.server.lane, "destination": dest, "port": port})
            s.sendall(b"\x05\x00\x00\x01" + bytes(6))
            if read_exact(s, 1) == b"!":
                s.sendall(PONG)
        except (EOFError, OSError):
            return


class DNSFixture(BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        if len(data) < 17:
            return
        end, labels = 12, []
        while end < len(data) and 0 < data[end] <= 63:
            size = data[end]
            if end + 1 + size >= len(data):
                return
            labels.append(data[end + 1:end + 1 + size].decode("ascii"))
            end += 1 + size
        if end + 5 > len(data) or data[end] != 0:
            return
        host = ".".join(labels).lower()
        typ, kind = struct.unpack_from("!HH", data, end + 1)
        question = data[12:end + 5]
        with LOCK:
            self.server.requests.append({"host": host, "type": typ})
        selected = ANSWERS.get(host)
        answer = b""
        if selected:
            ip = ipaddress.ip_address(selected)
            if (ip.version, typ, kind) in ((4, 1, 1), (6, 28, 1)):
                answer = b"\xc0\x0c" + struct.pack("!HHIH", typ, 1, 30, len(ip.packed)) + ip.packed
        flags = 0x8180 if selected else 0x8183
        response = data[:2] + struct.pack("!HHHHH", flags, 1, bool(answer), 0, 0) + question + answer
        sock.sendto(response, self.client_address)


@contextmanager
def server(kind, handler, **fields):
    with kind((LOCAL, 0), handler) as listener:
        for key, value in fields.items():
            setattr(listener, key, value)
        worker = Thread(target=listener.serve_forever, daemon=True)
        worker.start()
        try:
            yield listener.server_address[1]
        finally:
            listener.shutdown()
            worker.join()


def address_field(target):
    try:
        addr = ipaddress.ip_address(target)
    except ValueError:
        return bytes([3, len(target)]) + target.encode("ascii")
    return bytes([1 if addr.version == 4 else 4]) + addr.packed


def request(port, target):
    with socket.create_connection((LOCAL, port), timeout=5) as s:
        s.sendall(b"\x05\x01\x00")
        assert read_exact(s, 2) == b"\x05\x00"
        s.sendall(b"\x05\x01\x00" + address_field(target) + struct.pack("!H", DST_PORT))
        reply = read_exact(s, 4)
        if reply[:3] != b"\x05\x00\x00":
            raise ValueError(f"SOCKS listener returned {reply.hex()}")
        decode_addr(s, reply[3])
        read_exact(s, 2)
        s.sendall(b"!")
        assert read_exact(s, len(PONG)) == PONG


def xray_config(inbound, direct, proxy, dns):
    return {
        "log": {"loglevel": "debug"},
        "inbounds": [{"listen": LOCAL, "port": inbound, "protocol": "socks", "settings": {"auth": "noauth"}}],
        "outbounds": [
            {"protocol": "socks", "tag": lane, "settings": {"servers": [{"address": LOCAL, "port": port}]}}
            for lane, port in (("proxy", proxy), ("direct", direct))
        ] + [{"protocol": "freedom", "tag": "dns-loopback"}],
        "dns": {"servers": [{"address": LOCAL, "port": dns}], "queryStrategy": "UseIP",
                "tag": "fixture-dns", "disableFallback": True, "disableCache": True},
        "routing": {"domainStrategy": "IPOnDemand", "rules": [
            {"type": "field", "inboundTag": ["fixture-dns"], "outboundTag": "dns-loopback"},
            {"type": "field", "domain": ["full:" + OVERLAP], "outboundTag": "proxy"},
            {"type": "field", "domain": ["full:" + OVERLAP, "full:" + WHITELIST], "outboundTag": "direct"},
            {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
            {"type": "field", "ip": ["geoip:ru"], "outboundTag": "direct"},
        ]},
    }


def sing_box_config(inbound, direct, proxy, dns, assets):
    return {
        "log": {"level": "debug"},
        "inbounds": [{"type": "socks", "listen": LOCAL, "listen_port": inbound}],
        "outbounds": [
            {"type": "socks", "tag": lane, "server": LOCAL, "server_port": port, "version": "5"}
            for lane, port in (("proxy", proxy), ("direct", direct))
        ],
        "dns": {"servers": [{"type": "udp", "tag": "fixture-dns", "server": LOCAL,
                             "server_port": dns}], "final": "fixture-dns", "disable_cache": True},
        "route": {"final": "proxy", "rules": [
            {"domain": [OVERLAP], "action": "route", "outbound": "proxy"},
            {"domain": [OVERLAP, WHITELIST], "action": "route", "outbound": "direct"},
            {"action": "resolve", "server": "fixture-dns"},
            {"rule_set": ["private"], "action": "route", "outbound": "direct"},
            {"rule_set": ["ru"], "action": "route", "outbound": "direct"},
        ], "rule_set": [
            {"type": "local", "format": "binary", "tag": tag, "path": str(assets / name)}
            for tag, name in (("private", "geoip_PRIVATE.srs"), ("ru", "geoip_RU.srs"))
        ]},
    }


def await_listener(proc, port):
    until = time.monotonic() + 6
    while time.monotonic() < until and proc.poll() is None:
        try:
            with socket.create_connection((LOCAL, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("client did not start a loopback SOCKS listener")


def exercise(assets, client, out):
    deliveries, queries = [], []
    with (
        server(ThreadingTCPServer, SocksListener, lane="proxy", deliveries=deliveries) as proxy,
        server(ThreadingTCPServer, SocksListener, lane="direct", deliveries=deliveries) as direct,
        server(ThreadingUDPServer, DNSFixture, requests=queries) as dns,
        socket.socket() as port_reservation,
    ):
        port_reservation.bind((LOCAL, 0))
        port = port_reservation.getsockname()[1]
        port_reservation.close()
        cfg = (xray_config(port, direct, proxy, dns) if client == "xray"
               else sing_box_config(port, direct, proxy, dns, assets))
        config_path = out / f"{client}.json"
        config_path.write_text(json.dumps(cfg), encoding="utf-8")
        command = [str(assets / client), "run", "-c", str(config_path)]
        env = os.environ.copy()
        env["XRAY_LOCATION_ASSET"] = str(out)
        log_path = out / f"{client}.log"
        result = []
        router = None
        try:
            with log_path.open("wb") as log:
                router = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                await_listener(router, port)
                for label, target, expected, expect_dns in CASES:
                    i, j = len(deliveries), len(queries)
                    try:
                        request(port, target)
                    except (EOFError, OSError, ValueError) as exc:
                        raise RuntimeError(f"{client}/{label}: {exc}") from exc
                    with LOCK:
                        new = deliveries[i:]
                        dns_q = queries[j:]
                    if len(new) != 1 or new[0]["lane"] != expected or new[0]["port"] != DST_PORT:
                        raise RuntimeError(f"{client}/{label}: expected {expected}, got {new}")
                    required_type = 28 if label.endswith("-v6") else 1
                    if (expect_dns and not any(q == {"host": target, "type": required_type} for q in dns_q)) or (
                            not expect_dns and dns_q):
                        raise RuntimeError(f"{client}/{label}: unexpected DNS queries {dns_q}")
                    result.append({"case": label, "target": target, "rule": expected, "dns_types": sorted(
                        {q["type"] for q in dns_q}), "outbound_target": new[0]["destination"]})
            return result
        except Exception:
            print(log_path.read_text(encoding="utf-8", errors="replace")[-6500:], file=sys.stderr)
            raise
        finally:
            if router is not None and router.poll() is None:
                router.terminate()
                try:
                    router.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    router.kill()
                    router.wait(timeout=3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", type=Path, required=True, help="directory with xray, sing-box, DAT and both SRS")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if {name for _, name in socket.if_nameindex()} != {"lo"}:
        p.error("expected an isolated namespace with loopback as its only interface")
    assets = args.assets.resolve(strict=True)
    files = ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs", "xray", "sing-box")
    sources = {name: hashlib.sha256((assets / name).read_bytes()).hexdigest() for name in files}
    with TemporaryDirectory() as directory:
        out = Path(directory)
        shutil.copyfile(assets / "geoip_RU.dat", out / "geoip.dat")
        report = {"scope": "loopback-only synthetic DNS and SOCKS routing", "assets_sha256": sources,
                  "clients": {x: exercise(assets, x, out) for x in ("xray", "sing-box")}}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {sum(map(len, report['clients'].values()))} route choices across both clients.")


if __name__ == "__main__":
    main()
