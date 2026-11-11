#!/usr/bin/env python3
"""Build a side-by-side, review-only GeoIP protobuf from VPN split-routing feeds."""
from __future__ import annotations
import argparse, csv, hashlib, ipaddress, json, time, urllib.request
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

BASELINE_COMMIT = "ac2e9a4322c0b7efe293983c88cf5b304771e4c5"
BASELINE_URL = "https://raw.githubusercontent.com/SpeedeMiner/Geoip-ru-server/" + BASELINE_COMMIT + "/geoip_RU.dat"
BASELINE_RIR_URL = "https://raw.githubusercontent.com/SpeedeMiner/Geoip-ru-server/" + BASELINE_COMMIT + "/geoip_RU_rir_registered_prefixes.txt"
BASELINE_BLOCKED_URL = "https://raw.githubusercontent.com/SpeedeMiner/Geoip-ru-server/" + BASELINE_COMMIT + "/geoip_RU_blocked_ip_exclusions.txt"

SOURCES = [
    dict(id="kyoresuas-lite", label="Kyoresuas lite", kind="cidr", group="kyoresuas-service-catalog", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-lite.ipv4.txt",
               "https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-lite.ipv6.txt"]),
    dict(id="kyoresuas-standard", label="Kyoresuas standard", kind="cidr", group="kyoresuas-service-catalog", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-standard.ipv4.txt",
               "https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-standard.ipv6.txt"]),
    dict(id="kyoresuas-full", label="Kyoresuas full", kind="cidr", group="ipdeny-plus-service-composite", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-full.ipv4.txt",
               "https://raw.githubusercontent.com/kyoresuas/ru-direct/0781793a159f9a53c5e68da2f46b0a64855f8cb6/ru-full.ipv6.txt"]),
    dict(id="w1zardz-direct", label="W1ZARDZ RU direct", kind="cidr", group="w1zardz-service-catalog", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/w1zardz/amnezia-vpn-russia-split-tunneling/6157cdfb55f1748c98cab121cde008b5f69d325d/dist/ru-direct-ipv4.txt"]),
    dict(id="hxehex-cidr", label="HXEHEX mobile whitelist CIDR", kind="cidr", group="mobile-operator-whitelist", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/hxehex/russia-mobile-internet-whitelist/fad3653ebd4b212643774a4d10af3eb33838e4ff/cidrwhitelist.txt"]),
    dict(id="hxehex-ip", label="HXEHEX mobile whitelist host IPs", kind="cidr", group="mobile-operator-whitelist", license="MIT", export=True, required=False,
         urls=["https://raw.githubusercontent.com/hxehex/russia-mobile-internet-whitelist/fad3653ebd4b212643774a4d10af3eb33838e4ff/ipwhitelist.txt"]),
    dict(id="escapingworm-operator", label="Escapingworm operator whitelist", kind="cidr", group="mobile-operator-whitelist", license="MIT", export=True, required=True,
         urls=["https://raw.githubusercontent.com/escapingworm/russia-whitelist/2bb6c0788f21986b7928d986ea2577c6ebc11b36/ru-whitelist-cidr.txt"]),
    dict(id="whisper-country", label="Whisper ipdeny-derived RU country reference", kind="cidr", group="ipdeny-country-zone", license="UNDECLARED", export=False, required=False,
         urls=["https://raw.githubusercontent.com/WhisperOfTheSteppe/ru-rules-dat/a420bb61ee79b7698145c16098b2a589c60aaad0/ru-ip.txt"]),
    dict(id="lib4u-amnezia", label="lib4u Amnezia service-IP observations", kind="amnezia", group="service-domain-resolution", license="UNDECLARED", export=False, required=False,
         urls=["https://raw.githubusercontent.com/lib4u/amnezia-tunneling-ru/0d10135f04fc57846b44e3dc2523e6253a91dfdc/amnezia.json"]),
    dict(id="jirnobruh-amnezia", label="Jirnobruh Amnezia service-IP observations", kind="amnezia", group="service-domain-resolution", license="UNDECLARED", export=False, required=False,
         urls=["https://raw.githubusercontent.com/jirnobruh/Split-Tunneling-Amnezia-for-Russia/c76daf8cd0ed4daacd1f3010ef16a716949c31ea/amnezia_split_ru_full.json"]),
    dict(id="pvd-dog-service", label="PVD Dog service-IP observations", kind="amnezia", group="service-domain-resolution", license="UNDECLARED", export=False, required=False,
         urls=["https://raw.githubusercontent.com/pvd-dog/russia-no-vpn-list/5f344d993f882f91449e03e98c25cb64ddc0251e/russia-no-vpn-list_by_%40pvd_dog.json"]),
]

def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Geoip-ru-server-vpn-route-audit/1.0"})
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError("HTTP " + str(response.status))
                data = response.read()
                if not data:
                    raise RuntimeError("empty response")
                return data
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError("fetch failed: " + url + ": " + str(error))

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def parse_net(value):
    if not isinstance(value, str):
        return None, "invalid"
    value = value.strip().strip('"').strip("'").strip(",")
    if not value:
        return None, "invalid"
    try:
        if "/" in value:
            net = ipaddress.ip_network(value, strict=False)
        else:
            addr = ipaddress.ip_address(value)
            net = ipaddress.ip_network((addr, addr.max_prefixlen), strict=False)
    except ValueError:
        return None, "invalid"
    if not net.is_global:
        return None, "non_global"
    return net, "ok"

def parse_text(data: bytes):
    nets, raw, invalid, non_global = set(), 0, 0, 0
    for line in data.decode("utf-8-sig", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.upper().startswith(("IP-CIDR,", "IP-CIDR6,")):
            line = line.split(",", 1)[-1]
        for token in line.replace(",", " ").split():
            raw += 1
            net, status = parse_net(token)
            if net is not None: nets.add(net)
            elif status == "non_global": non_global += 1
            else: invalid += 1
    return nets, {"raw_tokens": raw, "invalid_tokens": invalid, "non_global_tokens": non_global}

def parse_amnezia(data: bytes):
    obj = json.loads(data.decode("utf-8-sig"))
    if isinstance(obj, dict):
        for key in ("routes", "items", "list", "rules"):
            if isinstance(obj.get(key), list):
                obj = obj[key]
                break
    if not isinstance(obj, list):
        raise ValueError("not an Amnezia list")
    nets, raw, invalid, non_global = set(), 0, 0, 0
    for row in obj:
        if not isinstance(row, dict):
            continue
        values = [row.get("ip")]
        if isinstance(row.get("ips"), list):
            values += row["ips"]
        for value in values:
            if not value:
                continue
            raw += 1
            net, status = parse_net(value)
            if net is not None: nets.add(net)
            elif status == "non_global": non_global += 1
            elif status == "invalid": invalid += 1
    return nets, {"raw_tokens": raw, "invalid_tokens": invalid, "non_global_tokens": non_global, "records": len(obj)}

def varint(data: bytes, offset: int):
    value, shift = 0, 0
    while True:
        if offset >= len(data) or shift >= 70:
            raise ValueError("malformed protobuf varint")
        b = data[offset]; offset += 1
        value |= (b & 127) << shift
        if b < 128: return value, offset
        shift += 7

def fields(data: bytes):
    offset = 0
    while offset < len(data):
        key, offset = varint(data, offset)
        number, wire = key >> 3, key & 7
        if number == 0: raise ValueError("protobuf field zero")
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire == 1:
            value = data[offset:offset+8]; offset += 8
        elif wire == 2:
            length, offset = varint(data, offset)
            value = data[offset:offset+length]; offset += length
        elif wire == 5:
            value = data[offset:offset+4]; offset += 4
        else: raise ValueError("unsupported protobuf wire")
        if wire in (1,2,5) and len(value) == 0: raise ValueError("truncated protobuf value")
        yield number, wire, value

def parse_geoip(data: bytes):
    result = {}
    for no, wire, entry in fields(data):
        if no != 1 or wire != 2: continue
        name, nets = None, set()
        for eno, ew, evalue in fields(entry):
            if eno == 1 and ew == 2:
                name = evalue.decode("ascii").upper()
            elif eno == 2 and ew == 2:
                addr, prefix = None, None
                for cno, cw, cv in fields(evalue):
                    if cno == 1 and cw == 2: addr = cv
                    elif cno == 2 and cw == 0: prefix = cv
                if addr is not None and prefix is not None:
                    nets.add(ipaddress.ip_network((ipaddress.ip_address(addr), int(prefix)), strict=False))
        if name: result.setdefault(name, set()).update(nets)
    if not result: raise ValueError("no GeoIP protobuf categories")
    return result

def encvar(value: int):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128); value >>= 7
    out.append(value)
    return bytes(out)

def fvar(no: int, value: int):
    return encvar(no << 3) + encvar(value)

def fbytes(no: int, value: bytes):
    return encvar((no << 3) | 2) + encvar(len(value)) + value

def compact(nets):
    result = []
    for version in (4, 6):
        result += list(ipaddress.collapse_addresses(n for n in nets if n.version == version))
    return sorted(result, key=lambda n: (n.version, int(n.network_address), n.prefixlen))

def encode(entries):
    out = bytearray()
    for name, networks in sorted(entries.items()):
        entry = bytearray(fbytes(1, name.encode("ascii")))
        for net in compact(networks):
            cidr = fbytes(1, net.network_address.packed) + fvar(2, net.prefixlen)
            entry += fbytes(2, cidr)
        out += fbytes(1, bytes(entry))
    return bytes(out)

def intervals(nets, version):
    pairs = sorted((int(n.network_address), int(n.broadcast_address)) for n in nets if n.version == version)
    merged = []
    for start, end in pairs:
        if not merged or start > merged[-1][1] + 1: merged.append([start, end])
        else: merged[-1][1] = max(merged[-1][1], end)
    return [(x[0], x[1]) for x in merged]

def size(iv):
    return sum(b-a+1 for a,b in iv)

def overlap_size(start, end, iv, starts):
    if not iv:
        return 0
    pos = max(0, bisect_right(starts, start) - 1)
    total = 0
    while pos < len(iv) and iv[pos][0] <= end:
        lo, hi = iv[pos]
        total += max(0, min(end, hi) - max(start, lo) + 1)
        pos += 1
    return total

def intersect(a, b):
    out=[]; i=j=0
    while i<len(a) and j<len(b):
        lo=max(a[i][0],b[j][0]); hi=min(a[i][1],b[j][1])
        if lo<=hi: out.append((lo,hi))
        if a[i][1]<b[j][1]: i+=1
        else: j+=1
    return out

def subtract(a, b):
    out=[]; j=0
    for lo,hi in a:
        cur=lo
        while j<len(b) and b[j][1]<cur: j+=1
        k=j
        while k<len(b) and b[k][0]<=hi:
            x,y=b[k]
            if x>cur: out.append((cur,min(hi,x-1)))
            cur=max(cur,y+1)
            if cur>hi: break
            k+=1
        if cur<=hi: out.append((cur,hi))
    return out

def interval_networks(iv, version):
    addr = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
    out=[]
    for lo,hi in iv: out += list(ipaddress.summarize_address_range(addr(lo),addr(hi)))
    return out

def address_counts(nets):
    return {f"ipv{v}": size(intervals(nets,v)) for v in (4,6)}

def metrics(nets, baseline_iv, baseline_exact, policy_iv=None):
    row={"unique_cidrs":len(nets),"compacted_cidrs":len(compact(nets)),"exact_baseline_matches":len({str(n) for n in nets}&baseline_exact)}
    for v in (4,6):
        src=intervals(nets,v); base=baseline_iv[v]; overlap=intersect(src,base); new=subtract(src,base)
        row[f"ipv{v}_cidrs"]=sum(1 for n in nets if n.version==v)
        row[f"ipv{v}_addresses"]=size(src)
        row[f"ipv{v}_covered_by_v37"]=size(overlap)
        row[f"ipv{v}_new_vs_v37"]=size(new)
        if policy_iv is not None:
            row[f"ipv{v}_new_after_private_blocked"]=size(subtract(src,policy_iv[v]))
    return row

def read_source(spec):
    nets=set(); raw_files=[]; totals={"raw_tokens":0,"invalid_tokens":0,"non_global_tokens":0}; errors=[]
    for url in spec["urls"]:
        try:
            payload=fetch(url)
            parsed, stats = parse_amnezia(payload) if spec["kind"]=="amnezia" else parse_text(payload)
            nets.update(parsed)
            for key in totals: totals[key] += stats.get(key,0)
            raw_files.append({"url":url,"bytes":len(payload),"sha256":sha(payload)})
        except Exception as exc:
            errors.append({"url":url,"error":str(exc)})
            if spec["required"]: raise RuntimeError(spec["id"] + " failed: " + str(exc))
    return nets, {
        "id":spec["id"],"label":spec["label"],"group":spec["group"],"license":spec["license"],
        "exported":spec["export"],"status":"ok" if not errors else ("partial" if raw_files else "unavailable"),
        "raw_files":raw_files,"errors":errors,**totals
    }

def write_tsv(path, headers, rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=headers,delimiter="\t",lineterminator="\n")
        w.writeheader(); w.writerows(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",default="artifacts/vpn-route-candidates")
    args=parser.parse_args()
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    baseline_bytes=fetch(BASELINE_URL); baseline=parse_geoip(baseline_bytes)
    baseline_ru=baseline.get("RU")
    if not baseline_ru: raise RuntimeError("pinned v37 baseline has no RU category")
    baseline_iv={v:intervals(baseline_ru,v) for v in (4,6)}
    baseline_private=baseline.get("PRIVATE",set())
    rir_bytes=fetch(BASELINE_RIR_URL)
    rir_nets,rir_parse_stats=parse_text(rir_bytes)
    blocked_bytes=fetch(BASELINE_BLOCKED_URL)
    blocked_nets,blocked_parse_stats=parse_text(blocked_bytes)
    policy_nets=baseline_ru | baseline_private | blocked_nets
    policy_iv={v:intervals(policy_nets,v) for v in (4,6)}
    baseline_exact={str(n) for n in baseline_ru}

    # Preserve exact RIR resource prefixes while measuring the portions not
    # already covered by RU output, PRIVATE or approved BLOCKED carve-outs.
    rir_residual_rows=[]
    rir_residual_intervals={}
    for version in (4,6):
        residual_parts=[]
        for net in rir_nets:
            if net.version != version:
                continue
            remainder=subtract([(int(net.network_address),int(net.broadcast_address))],policy_iv[version])
            if remainder:
                residual_parts.extend(remainder)
                rir_residual_rows.append({
                    "prefix":str(net),
                    "family":"IPv"+str(version),
                    "version":version,
                    "uncovered_intervals":remainder,
                    "uncovered_addresses":size(remainder),
                })
        rir_residual_intervals[version]=intervals(interval_networks(residual_parts,version),version)

    loaded={}; source_rows=[]
    for spec in SOURCES:
        nets, info=read_source(spec); loaded[spec["id"]]=nets
        info.update(metrics(nets,baseline_iv,baseline_exact,policy_iv)); source_rows.append(info)
    export_specs=[s for s in SOURCES if s["export"]]
    union=set().union(*(loaded[s["id"]] for s in export_specs))
    new=[]
    for v in (4,6): new += interval_networks(subtract(intervals(union,v),baseline_iv[v]),v)
    new=compact(new)
    new_after_policy=[]
    for v in (4,6):
        new_after_policy += interval_networks(subtract(intervals(union,v),policy_iv[v]),v)
    new_after_policy=compact(new_after_policy)
    categories={
        "ru_vpn_kyoresuas_lite":loaded["kyoresuas-lite"],
        "ru_vpn_kyoresuas_standard":loaded["kyoresuas-standard"],
        "ru_vpn_kyoresuas_full":loaded["kyoresuas-full"],
        "ru_vpn_w1zardz_direct":loaded["w1zardz-direct"],
        "ru_vpn_hxehex_cidr":loaded["hxehex-cidr"],
        "ru_vpn_hxehex_ip":loaded["hxehex-ip"],
        "ru_vpn_operator_whitelist":loaded["escapingworm-operator"],
        "ru_vpn_export_union":union,
        "ru_vpn_new_vs_v37":set(new),
        "ru_vpn_new_after_private_blocked":set(new_after_policy),
    }
    candidate=encode(categories)
    roundtrip=parse_geoip(candidate)
    for name,nets in categories.items():
        if roundtrip.get(name.upper(),set()) != set(compact(nets)):
            raise RuntimeError("protobuf roundtrip mismatch: "+name)
    (out/"geoip_RU_vpn_candidates.dat").write_bytes(candidate)
    prefix_rows=[]
    baseline_starts={v:[item[0] for item in baseline_iv[v]] for v in (4,6)}
    for spec in export_specs:
        for net in sorted(loaded[spec["id"]],key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            v=net.version
            covered=overlap_size(int(net.network_address),int(net.broadcast_address),baseline_iv[v],baseline_starts[v])
            status="covered" if covered==net.num_addresses else ("partial" if covered else "new")
            prefix_rows.append({"source_id":spec["id"],"cidr":str(net),"family":"IPv"+str(v),"v37_address_coverage":status})
    write_tsv(out/"candidate_source_prefixes.tsv",["source_id","cidr","family","v37_address_coverage"],prefix_rows)
    metric_rows=[]
    for info in source_rows:
        metric_rows.append({k:info.get(k,"") for k in [
            "id","label","group","license","status","exported","unique_cidrs","compacted_cidrs",
            "ipv4_cidrs","ipv4_addresses","ipv4_covered_by_v37","ipv4_new_vs_v37","ipv4_new_after_private_blocked",
            "ipv6_cidrs","ipv6_addresses","ipv6_covered_by_v37","ipv6_new_vs_v37","ipv6_new_after_private_blocked",
            "exact_baseline_matches","raw_tokens","invalid_tokens","non_global_tokens"]})
    write_tsv(out/"candidate_source_metrics.tsv",list(metric_rows[0].keys()),metric_rows)
    with (out/"candidate_new_vs_v37.txt").open("w",encoding="utf-8") as f:
        f.write("# REVIEW ONLY. These addresses appear in the VPN candidate union and are outside v37 RU.\n")
        f.writelines(str(n)+"\n" for n in new)
    union_stats=metrics(union,baseline_iv,baseline_exact,policy_iv)
    base_stats={"cidrs":len(baseline_ru),"ipv4_addresses":size(baseline_iv[4]),"ipv6_addresses":size(baseline_iv[6])}

    # Source-specific coverage of exact RIR resource prefixes that still have
    # address space outside the v37 RU + PRIVATE + approved BLOCKED union.
    residual_summary=[]
    residual_prefix_rows=[]
    for spec in SOURCES:
        source_id=spec["id"]
        source_nets=loaded[source_id]
        source_exact={str(n) for n in source_nets}
        source_iv={v:intervals(source_nets,v) for v in (4,6)}
        source_starts={v:[item[0] for item in source_iv[v]] for v in (4,6)}
        row={"source_id":source_id,"label":spec["label"],"license":spec["license"],"exported":str(bool(spec["export"])).lower()}
        for v in (4,6):
            relevant=[r for r in rir_residual_rows if r["version"]==v]
            any_rows=full_rows=exact_rows=0
            for residual in relevant:
                covered=sum(overlap_size(lo,hi,source_iv[v],source_starts[v]) for lo,hi in residual["uncovered_intervals"])
                if covered: any_rows += 1
                if covered == residual["uncovered_addresses"]: full_rows += 1
                if residual["prefix"] in source_exact: exact_rows += 1
                if spec["export"]:
                    residual_prefix_rows.append({
                        "source_id":source_id,
                        "prefix":residual["prefix"],
                        "family":residual["family"],
                        "policy_uncovered_addresses":residual["uncovered_addresses"],
                        "candidate_overlap_addresses":covered,
                        "fully_covered":str(covered==residual["uncovered_addresses"]).lower(),
                        "exact_cidr_match":str(residual["prefix"] in source_exact).lower(),
                    })
            unique_residual=size(rir_residual_intervals[v])
            unique_covered=size(intersect(source_iv[v],rir_residual_intervals[v]))
            row[f"ipv{v}_rir_residual_prefix_rows"]=len(relevant)
            row[f"ipv{v}_rir_residual_rows_with_overlap"]=any_rows
            row[f"ipv{v}_rir_residual_rows_fully_covered"]=full_rows
            row[f"ipv{v}_rir_residual_exact_cidr_matches"]=exact_rows
            row[f"ipv{v}_rir_residual_unique_addresses"]=unique_residual
            row[f"ipv{v}_rir_residual_addresses_covered"]=unique_covered
            row[f"ipv{v}_rir_residual_coverage_pct"]=round(100*unique_covered/unique_residual,6) if unique_residual else 0.0
        residual_summary.append(row)

    write_tsv(
        out/"candidate_rir_ru_residual_coverage.tsv",
        ["source_id","label","license","exported",
         "ipv4_rir_residual_prefix_rows","ipv4_rir_residual_rows_with_overlap","ipv4_rir_residual_rows_fully_covered","ipv4_rir_residual_exact_cidr_matches","ipv4_rir_residual_unique_addresses","ipv4_rir_residual_addresses_covered","ipv4_rir_residual_coverage_pct",
         "ipv6_rir_residual_prefix_rows","ipv6_rir_residual_rows_with_overlap","ipv6_rir_residual_rows_fully_covered","ipv6_rir_residual_exact_cidr_matches","ipv6_rir_residual_unique_addresses","ipv6_rir_residual_addresses_covered","ipv6_rir_residual_coverage_pct"],
        residual_summary,
    )
    write_tsv(
        out/"candidate_rir_ru_residual_prefix_coverage.tsv",
        ["source_id","prefix","family","policy_uncovered_addresses","candidate_overlap_addresses","fully_covered","exact_cidr_match"],
        residual_prefix_rows,
    )
    (out/"candidate_new_after_private_blocked.txt").write_text(
        "# REVIEW ONLY. Candidate address space outside v37 RU, PRIVATE and approved blocked exclusions.\n"
        + "".join(str(n)+"\n" for n in new_after_policy),
        encoding="utf-8",
    )
    manifest={
        "schema":1,"generated_at":datetime.now(timezone.utc).isoformat(),
        "baseline":{"commit":BASELINE_COMMIT,"url":BASELINE_URL,"sha256":sha(baseline_bytes),**base_stats},
        "candidate_union":union_stats,
        "new_vs_v37":{"cidrs":len(new),"ipv4_addresses":sum(n.num_addresses for n in new if n.version==4),"ipv6_addresses":sum(n.num_addresses for n in new if n.version==6)},
        "new_after_private_blocked":{"cidrs":len(new_after_policy),"ipv4_addresses":sum(n.num_addresses for n in new_after_policy if n.version==4),"ipv6_addresses":sum(n.num_addresses for n in new_after_policy if n.version==6)},
        "baseline_policy_evidence":{
            "rir_snapshot_url":BASELINE_RIR_URL,"rir_snapshot_bytes":len(rir_bytes),"rir_snapshot_sha256":sha(rir_bytes),
            "rir_parsed_cidrs":len(rir_nets),"rir_parse_stats":rir_parse_stats,
            "approved_blocked_url":BASELINE_BLOCKED_URL,"approved_blocked_bytes":len(blocked_bytes),"approved_blocked_sha256":sha(blocked_bytes),
            "approved_blocked_parsed_cidrs":len(blocked_nets),"blocked_parse_stats":blocked_parse_stats,
            "rir_residual_prefix_rows":len(rir_residual_rows),
            "rir_residual_ipv4_unique_addresses":size(rir_residual_intervals[4]),
            "rir_residual_ipv6_unique_addresses":size(rir_residual_intervals[6]),
        },
        "rir_residual_source_coverage":residual_summary,
        "sources":source_rows,
        "candidate_dat":{"file":"geoip_RU_vpn_candidates.dat","bytes":len(candidate),"sha256":sha(candidate),"categories":{k:{"cidrs":len(compact(v)),**address_counts(v)} for k,v in categories.items()}},
        "safety":{"production_geoip_RU_dat_modified":False,"production_builder_modified":False,"production_sources_modified":False,"main_or_release_updated":False,"unlicensed_sources_in_dat":False,"unlicensed_prefixes_redistributed":False,"all_new_vs_v37_rows_review_only":True}
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "# VPN route candidate build",
        "",
        "Generated: "+manifest["generated_at"],
        "Baseline commit: "+BASELINE_COMMIT,
        "Baseline SHA-256: "+sha(baseline_bytes),
        "",
        "This is a separate review-only protobuf. It does not replace the production RU category.",
        "Sources with no declared license contribute aggregate coverage metrics only; their CIDRs are not exported.",
        "",
        "| Source | Group | License | Status | CIDRs | IPv4 | New IPv4 | IPv6 | New IPv6 | Export |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|"
    ]
    for x in metric_rows:
        lines.append("| {label} | {group} | {license} | {status} | {unique_cidrs} | {ipv4_addresses} | {ipv4_new_vs_v37} | {ipv6_addresses} | {ipv6_new_vs_v37} | {exported} |".format(**x))
    lines += [
        "",
        "## Union",
        "",
        "Unique candidate CIDRs: "+str(union_stats["unique_cidrs"]),
        "IPv4 candidate addresses: "+str(union_stats["ipv4_addresses"]),
        "IPv4 address space new vs v37: "+str(union_stats["ipv4_new_vs_v37"]),
        "IPv6 candidate addresses: "+str(union_stats["ipv6_addresses"]),
        "IPv6 address space new vs v37: "+str(union_stats["ipv6_new_vs_v37"]),
        "Candidate protobuf SHA-256: "+sha(candidate),
        "",
        "## RIR residual coverage after existing policy",
        "",
        "RIR RU residual exact-prefix rows after RU + PRIVATE + approved BLOCKED carve-outs: "+str(len(rir_residual_rows)),
        "Unique residual IPv4 addresses: "+str(size(rir_residual_intervals[4])),
        "Unique residual IPv6 addresses: "+str(size(rir_residual_intervals[6])),
        "Candidate addresses outside all three existing policy sets: IPv4 "+str(sum(n.num_addresses for n in new_after_policy if n.version==4))+", IPv6 "+str(sum(n.num_addresses for n in new_after_policy if n.version==6)),
        "",
        "| Source | IPv4 rows fully covered | IPv4 exact RIR CIDR matches | IPv4 address coverage | IPv6 rows fully covered | IPv6 exact RIR CIDR matches | IPv6 address coverage |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *["| {label} | {ipv4_rir_residual_rows_fully_covered}/{ipv4_rir_residual_prefix_rows} | {ipv4_rir_residual_exact_cidr_matches} | {ipv4_rir_residual_coverage_pct}% | {ipv6_rir_residual_rows_fully_covered}/{ipv6_rir_residual_prefix_rows} | {ipv6_rir_residual_exact_cidr_matches} | {ipv6_rir_residual_coverage_pct}% |".format(**r) for r in residual_summary],
        "",
        "Prefix detail: candidate_rir_ru_residual_prefix_coverage.tsv. Exact RIR prefix rows may overlap; address coverage uses unique merged intervals.",
        "",
        "## Decision limits",
        "",
        "- New vs v37 means address-space difference only; it is not proof of Russian ownership, current BGP reachability or DIRECT approval.",
        "- Kyoresuas lite/standard/full are tiers from one publisher, not independent votes. Full is a composite country-zone plus service list.",
        "- HXEHEX and Escapingworm are one mobile/operator-whitelist evidence group.",
        "- W1ZARDZ and HXEHEX already exist as candidate-only inputs in v37; this build tests fresh pinned revisions and the additional IP-only file.",
        "- Whisper is ipdeny-derived and has no declared repository license in the inspected metadata; metrics only.",
        "- Service CIDRs may be shared CDN, hosting or operator space. Exact BGP origin, holder, IRR and RPKI review is needed before any production change.",
        "- The GeoIP protobuf categories are namespaced ru_vpn_* and do not modify geoip:ru."
    ]
    (out/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("baseline RU CIDRs:",len(baseline_ru))
    print("VPN source inputs:",len(source_rows))
    print("candidate union CIDRs:",union_stats["unique_cidrs"])
    print("new IPv4 addresses:",union_stats["ipv4_new_vs_v37"])
    print("new IPv6 addresses:",union_stats["ipv6_new_vs_v37"])
    print("candidate dat bytes:",len(candidate),"sha256:",sha(candidate))

if __name__=="__main__":
    main()
