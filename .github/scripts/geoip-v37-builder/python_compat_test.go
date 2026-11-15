package main

import (
	"encoding/json"
	"net/netip"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/proto"
)

// Optional retained-artifact replay. Ordinary CI always runs the synthetic
// compatibility case below; a replay supplies the directory with DAT and
// decompiled RU.json/PRIVATE.json produced by the pinned sing-box binary.
func TestSnapshotDATMatchesDecompiledSRS(t *testing.T) {
	directory := os.Getenv("V41_COMPAT_DIRECTORY")
	if directory == "" {
		t.Skip("retained-artifact replay directory not supplied")
	}
	payload, err := os.ReadFile(filepath.Join(directory, "geoip_RU.dat"))
	if err != nil {
		t.Fatal(err)
	}
	var decoded router.GeoIPList
	if err := proto.Unmarshal(payload, &decoded); err != nil {
		t.Fatal(err)
	}
	if len(decoded.Entry) != 2 {
		t.Fatal("expected RU and PRIVATE")
	}
	seen := map[string]bool{}
	for _, entry := range decoded.Entry {
		if seen[entry.CountryCode] || (entry.CountryCode != "RU" && entry.CountryCode != "PRIVATE") || entry.InverseMatch {
			t.Fatal("invalid category")
		}
		seen[entry.CountryCode] = true
		raw, err := os.ReadFile(filepath.Join(directory, entry.CountryCode+".json"))
		if err != nil {
			t.Fatal(err)
		}
		var document struct {
			Version int `json:"version"`
			Rules   []struct {
				CIDRs []string `json:"ip_cidr"`
			} `json:"rules"`
		}
		if err := json.Unmarshal(raw, &document); err != nil {
			t.Fatal(err)
		}
		if document.Version != 1 || len(document.Rules) != 1 {
			t.Fatal("invalid SRS structure")
		}
		want := map[netip.Prefix]bool{}
		for _, text := range document.Rules[0].CIDRs {
			p, err := netip.ParsePrefix(text)
			if err != nil || p != p.Masked() || want[p] {
				t.Fatalf("invalid SRS CIDR: %s", text)
			}
			want[p] = true
		}
		if len(want) != len(entry.Cidr) {
			t.Fatal("DAT/SRS CIDR count differs")
		}
		for _, cidr := range entry.Cidr {
			addr, ok := netip.AddrFromSlice(cidr.Ip)
			p := netip.PrefixFrom(addr, int(cidr.Prefix))
			if !ok || !p.IsValid() || p != p.Masked() || !want[p] {
				t.Fatalf("DAT/SRS mismatch: %v", p)
			}
			delete(want, p)
		}
		if len(want) != 0 {
			t.Fatal("unmatched SRS CIDRs")
		}
	}
}

// Use v2fly's generated types from the go.mod/go.sum lock to check the Python
// encoder's actual wire fields, including IPv4 /32 and IPv6 /128 hosts.
func TestPythonEncoderUpstreamProtobufCompatibility(t *testing.T) {
	cmd := exec.Command("python3", "-c", `import sys, ipaddress
sys.path.insert(0, "..")
from build_v41_overlay import encode_geoip
sys.stdout.buffer.write(encode_geoip({
"RU": {ipaddress.ip_network("192.0.2.1/32"), ipaddress.ip_network("2001:db8::1/128")},
"PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")}}))`)
	payload, err := cmd.Output()
	if err != nil {
		t.Fatal(err)
	}
	var decoded router.GeoIPList
	if err := proto.Unmarshal(payload, &decoded); err != nil {
		t.Fatal(err)
	}
	expected := map[string]map[string]bool{
		"RU":      {"192.0.2.1/32": true, "2001:db8::1/128": true},
		"PRIVATE": {"10.0.0.0/8": true, "fc00::/7": true},
	}
	if len(decoded.Entry) != len(expected) {
		t.Fatalf("wrong category count: %d", len(decoded.Entry))
	}
	for _, entry := range decoded.Entry {
		want, exists := expected[entry.CountryCode]
		if !exists || entry.InverseMatch || len(entry.Cidr) != len(want) {
			t.Fatalf("unexpected category: %v", entry)
		}
		for _, cidr := range entry.Cidr {
			addr, ok := netip.AddrFromSlice(cidr.Ip)
			if !ok {
				t.Fatalf("invalid IP bytes: %x", cidr.Ip)
			}
			key := netip.PrefixFrom(addr, int(cidr.Prefix)).String()
			if !want[key] {
				t.Fatalf("unexpected or duplicate prefix: %s", key)
			}
			delete(want, key)
		}
		delete(expected, entry.CountryCode)
	}
}
