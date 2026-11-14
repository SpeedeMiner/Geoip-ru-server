#!/usr/bin/env python3
"""Reproduce the fixed CITIC routing audit without dialing any tested address."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from hashlib import sha256
from ipaddress import ip_address
import json
import os
from pathlib import Path
import queue
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time


DOCS = Path(__file__).resolve().parents[2] / "docs"
HASHES = {
    "xray": "64d46afb80adea1bf97a0d467e83f4a9ac1ebd0995891e84bca3f1a1d1affb1d",
    "fixed": "2735053560ebd598cbdcd71ccf858806d4b955a17e2eac512a7baf249d43653a",
    "shadow": "4517a9b8e4dce647d0c7e43deca49dfed87f687a1cc111a7e006e35fe417495f",
    "geosite": "75b79f1883e0ae7380621c41bdac89777dc1df660844d141ea98a400526728ec",
}
STRATEGIES = {"UseIPv4": {"A"}, "UseIPv6": {"AAAA"}, "UseIP": {"A", "AAAA"}}
FAMILY = {1: "A", 28: "AAAA"}
PORT = 443
PAYLOAD = b"local-route-fixture"


def fixture(name):
    return json.loads((DOCS / name).read_text())


def recv(sock, n):
    chunks = bytearray()
    while len(chunks) < n:
        part = sock.recv(n - len(chunks))
        if not part:
            raise EOFError("local SOCKS exchange ended early")
        chunks.extend(part)
    return bytes(chunks)


def read_host(sock, atyp):
    if atyp == 3:
        return recv(sock, recv(sock, 1)[0]).decode("ascii")
    return str(ip_address(recv(sock, {1: 4, 4: 16}[atyp])))


def write_host(host):
    try:
        ip = ip_address(host)
    except ValueError:
        encoded = host.encode("ascii")
        return b"\x03" + bytes([len(encoded)]) + encoded
    return bytes([{4: 1, 6: 4}[ip.version]]) + ip.packed


class SocksSink(socketserver.ThreadingTCPServer):
    daemon_threads = True


class SocksHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(5)
        version, n_methods = recv(sock, 2)
        if version != 5 or 0 not in recv(sock, n_methods):
            raise ValueError("expected unauthenticated SOCKS5")
        sock.sendall(b"\x05\x00")
        version, command, reserved, atyp = recv(sock, 4)
        if (version, command, reserved) != (5, 1, 0):
            raise ValueError("expected SOCKS5 CONNECT")
        host = read_host(sock, atyp)
        port, = struct.unpack("!H", recv(sock, 2))
        sock.sendall(b"\x05\x00\x00\x01" + bytes(6))
        if recv(sock, len(PAYLOAD)) != PAYLOAD:
            raise ValueError("unexpected SOCKS fixture payload")
        self.server.observed.put((self.server.route, host, port))
        sock.sendall(b"OK")


class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        if len(data) < 17 or data[4:6] != b"\x00\x01":
            return
        i = 12
        labels = []
        while i < len(data) and data[i]:
            size = data[i]
            if size > 63 or i + 1 + size >= len(data):
                return
            labels.append(data[i + 1:i + 1 + size].decode("ascii"))
            i += 1 + size
        i += 1
        if i + 4 > len(data):
            return
        qtype, qclass = struct.unpack_from("!HH", data, i)
        name = ".".join(labels).lower()
        family = FAMILY.get(qtype)
        self.server.observed.put((name, family))
        known = self.server.entries.get(name)
        ips = known.get(family, []) if known is not None and qclass == 1 else []
        answer = b"".join(
            b"\xc0\x0c" + struct.pack("!HHIH", qtype, 1, 60, len(ip.packed)) + ip.packed
            for ip in ips
        )
        flags = 0x8180 if known is not None else 0x8183
        head = data[:2] + struct.pack("!5H", flags, 1, len(ips), 0, 0)
        sock.sendto(head + data[12:i + 4] + answer, self.client_address)


def start_server(stack, server):
    stack.enter_context(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stack.callback(server.shutdown)
    return server


def exchange(inbound, target):
    with socket.create_connection(("127.0.0.1", inbound), timeout=5) as sock:
        sock.sendall(b"\x05\x01\x00")
        if recv(sock, 2) != b"\x05\x00":
            raise ValueError("Xray fixture rejected SOCKS5 auth negotiation")
        sock.sendall(b"\x05\x01\x00" + write_host(target) + struct.pack("!H", PORT))
        version, status, reserved, atyp = recv(sock, 4)
        if (version, status, reserved) != (5, 0, 0):
            raise ValueError(f"Xray fixture rejected {target}")
        read_host(sock, atyp)
        recv(sock, 2)
        sock.sendall(PAYLOAD)
        if recv(sock, 2) != b"OK":
            raise ValueError("fixture sink failed to acknowledge the test payload")


def take_all(observed):
    entries = []
    while True:
        try:
            entries.append(observed.get_nowait())
        except queue.Empty:
            return entries


def build_config(inbound, sinks, dns_port, strategy):
    rules = [
        {"type": "field", "domain": ["ext:geosite_RU.dat:RU"], "outboundTag": "DIRECT"},
        {"type": "field", "ip": ["ext:geoip_RU.dat:RU"], "outboundTag": "DIRECT"},
    ]
    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "fixture-in", "listen": "127.0.0.1", "port": inbound,
            "protocol": "socks", "settings": {"auth": "noauth"},
        }],
        "outbounds": [{
            "tag": sink.route, "protocol": "socks",
            "settings": {"servers": [{"address": "127.0.0.1", "port": sink.server_address[1]}]},
        } for sink in sinks],
        "routing": {"domainStrategy": "AsIs" if strategy is None else "IPOnDemand", "rules": rules},
    }
    if strategy is not None:
        cfg["dns"] = {
            "servers": [{"address": "127.0.0.1", "port": dns_port}],
            "queryStrategy": strategy, "tag": "fixture-dns", "disableCache": True,
        }
        cfg["outbounds"].extend([
            {"tag": "loopback-dns", "protocol": "freedom"},
            {"tag": "deny-dns", "protocol": "blackhole"},
        ])
        rules[:0] = [
            {"type": "field", "inboundTag": ["fixture-dns"], "ip": ["127.0.0.1/32"],
             "port": dns_port, "outboundTag": "loopback-dns"},
            {"type": "field", "inboundTag": ["fixture-dns"], "outboundTag": "deny-dns"},
        ]
    return cfg


def run_case(xray, assets, sinks, resolver, strategy, targets):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        inbound = reservation.getsockname()[1]
    cfg = build_config(inbound, sinks, resolver.server_address[1], strategy)
    cfg_path = assets / "fixture.json"
    cfg_path.write_text(json.dumps(cfg))
    env = {**os.environ, "XRAY_LOCATION_ASSET": str(assets)}
    command = [str(xray), "run", "-c", str(cfg_path)]
    result = subprocess.run(command + ["-test"], capture_output=True, text=True, env=env, timeout=15)
    if result.returncode:
        raise RuntimeError(f"Xray config test failed: {result.stdout}\n{result.stderr}")
    outcomes = {}
    log_path = assets / "fixture.log"
    with log_path.open("w+") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            for _ in range(80):
                try:
                    with socket.create_connection(("127.0.0.1", inbound), timeout=0.15):
                        break
                except OSError:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
            else:
                raise TimeoutError("Xray fixture listener did not start")
            if proc.poll() is not None:
                log.seek(0)
                raise RuntimeError(log.read())
            for target in targets:
                exchange(inbound, target)
                hits = [hit for sink in sinks for hit in take_all(sink.observed)]
                if len(hits) != 1 or hits[0][1:] != (target, PORT):
                    raise ValueError(f"unexpected outbound selections for {target}: {hits}")
                questions = take_all(resolver.observed)
                wanted = STRATEGIES.get(strategy, set())
                if any(name != target for name, _ in questions) or {t for _, t in questions} != wanted:
                    raise ValueError(f"unexpected DNS questions for {target}: {questions}")
                outcomes[target] = {"route": hits[0][0], "questions": sorted(t for _, t in questions)}
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in HASHES:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    files = {name: getattr(args, name).resolve() for name in HASHES}
    payloads = {name: path.read_bytes() for name, path in files.items()}
    for name, data in payloads.items():
        if sha256(data).hexdigest() != HASHES[name]:
            parser.error(f"{name} does not match the fixed fixture digest")
    as_is = fixture("v41-citic-xray-route-delta-20261114.json")["targets"]
    saved = fixture("v41-citic-xray-dns-strategies-20261114.json")["targets"]
    answers = fixture("v41-citic-loopback-dns-20261114.json")
    with ExitStack() as stack:
        temp = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="citic-xray-")))
        xray = temp / "xray"
        xray.write_bytes(payloads["xray"])
        xray.chmod(0o700)
        sinks = []
        for route in ("PROXY", "DIRECT"):
            sink = start_server(stack, SocksSink(("127.0.0.1", 0), SocksHandler))
            sink.route, sink.observed = route, queue.Queue()
            sinks.append(sink)
        resolver = start_server(stack, socketserver.UDPServer(("127.0.0.1", 0), DNSHandler))
        resolver.observed = queue.Queue()
        resolver.entries = {
            row["name"].lower().rstrip("."): {
                family: [ip_address(ip) for ip in row[family]["answers"]]
                for family in FAMILY.values()
            }
            for row in answers.values()
        }
        if len(as_is) != 71 or len(saved) != 11 or set(resolver.entries) != set(saved):
            raise ValueError("fixed test cohort mismatch")
        for label in ("fixed", "shadow"):
            assets = temp / label
            assets.mkdir()
            (assets / "geoip_RU.dat").write_bytes(payloads[label])
            (assets / "geosite_RU.dat").write_bytes(payloads["geosite"])
            found = run_case(xray, assets, sinks, resolver, None, as_is)
            if {n: a["route"] for n, a in found.items()} != {
                n: t[label + "_observed"] for n, t in as_is.items()
            }:
                raise ValueError(f"{label} AsIs results differ from archived observations")
            for strategy in STRATEGIES:
                found = run_case(xray, assets, sinks, resolver, strategy, resolver.entries)
                if found != {n: a[strategy][label] for n, a in saved.items()}:
                    raise ValueError(f"{label} {strategy} differs from archived observations")
    print("PASS: 142 AsIs and 66 IPOnDemand route observations reproduced locally.")


if __name__ == "__main__":
    main()
