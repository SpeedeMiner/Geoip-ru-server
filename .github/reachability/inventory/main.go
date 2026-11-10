package main

import (
	"encoding/csv"
	"fmt"
	"math/big"
	"net/netip"
	"os"
	"sort"
	"strings"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/proto"
)

type inventoryRow struct {
	category string
	prefix   netip.Prefix
}

func cidrPrefix(c *router.CIDR) (netip.Prefix, error) {
	if c == nil {
		return netip.Prefix{}, fmt.Errorf("nil CIDR")
	}
	var addr netip.Addr
	switch len(c.Ip) {
	case 4:
		var raw [4]byte
		copy(raw[:], c.Ip)
		addr = netip.AddrFrom4(raw)
	case 16:
		var raw [16]byte
		copy(raw[:], c.Ip)
		addr = netip.AddrFrom16(raw)
	default:
		return netip.Prefix{}, fmt.Errorf("unsupported address length %d", len(c.Ip))
	}
	if !addr.IsValid() || c.Prefix == 0 || int(c.Prefix) > addr.BitLen() {
		return netip.Prefix{}, fmt.Errorf("invalid prefix length %d for %s", c.Prefix, addr)
	}
	p := netip.PrefixFrom(addr, int(c.Prefix))
	if p != p.Masked() {
		return netip.Prefix{}, fmt.Errorf("non-canonical prefix in protobuf: %s", p)
	}
	return p, nil
}

func overlaps(a, b netip.Prefix) bool {
	if a.Addr().Is4() != b.Addr().Is4() {
		return false
	}
	return a.Contains(b.Addr()) || b.Contains(a.Addr())
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: geoip-inventory <geoip_RU.dat> <output.tsv>")
		os.Exit(2)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fatal(err)
	}
	if len(data) == 0 {
		fatal(fmt.Errorf("empty GeoIP protobuf"))
	}
	list := new(router.GeoIPList)
	if err := proto.Unmarshal(data, list); err != nil {
		fatal(fmt.Errorf("decode GeoIP protobuf: %w", err))
	}

	seenCategories := map[string]bool{}
	seen := map[string]bool{}
	rows := make([]inventoryRow, 0)
	ru := make([]netip.Prefix, 0)
	private := make([]netip.Prefix, 0)
	for _, entry := range list.Entry {
		if entry == nil {
			fatal(fmt.Errorf("nil GeoIP category entry"))
		}
		category := strings.ToUpper(strings.TrimSpace(entry.CountryCode))
		if category != "RU" && category != "PRIVATE" {
			fatal(fmt.Errorf("unexpected protobuf category %q", entry.CountryCode))
		}
		if seenCategories[category] {
			fatal(fmt.Errorf("duplicate protobuf category %q", category))
		}
		seenCategories[category] = true
		for _, raw := range entry.Cidr {
			p, err := cidrPrefix(raw)
			if err != nil {
				fatal(fmt.Errorf("%s: %w", category, err))
			}
			key := category + "\t" + p.String()
			if seen[key] {
				fatal(fmt.Errorf("duplicate prefix %s in %s", p, category))
			}
			seen[key] = true
			rows = append(rows, inventoryRow{category: category, prefix: p})
			if category == "RU" {
				ru = append(ru, p)
			} else {
				private = append(private, p)
			}
		}
	}
	if !seenCategories["RU"] || !seenCategories["PRIVATE"] {
		fatal(fmt.Errorf("protobuf must contain both RU and PRIVATE categories"))
	}
	if len(ru) == 0 || len(private) == 0 {
		fatal(fmt.Errorf("empty RU or PRIVATE prefix set: RU=%d PRIVATE=%d", len(ru), len(private)))
	}
	for _, r := range ru {
		for _, p := range private {
			if overlaps(r, p) {
				fatal(fmt.Errorf("RU/PRIVATE overlap: RU=%s PRIVATE=%s", r, p))
			}
		}
	}

	sort.Slice(rows, func(i, j int) bool {
		if rows[i].category != rows[j].category {
			return rows[i].category < rows[j].category
		}
		if rows[i].prefix.Addr().Is4() != rows[j].prefix.Addr().Is4() {
			return rows[i].prefix.Addr().Is4()
		}
		if c := rows[i].prefix.Addr().Compare(rows[j].prefix.Addr()); c != 0 {
			return c < 0
		}
		return rows[i].prefix.Bits() < rows[j].prefix.Bits()
	})

	out, err := os.Create(os.Args[2])
	if err != nil {
		fatal(err)
	}
	defer out.Close()
	w := csv.NewWriter(out)
	w.Comma = '\t'
	if err := w.Write([]string{"CATEGORY", "PREFIX", "FAMILY", "ADDRESS_COUNT"}); err != nil {
		fatal(err)
	}
	for _, row := range rows {
		family := "IPv6"
		if row.prefix.Addr().Is4() {
			family = "IPv4"
		}
		if err := w.Write([]string{
			row.category,
			row.prefix.String(),
			family,
			addressCount(row.prefix),
		}); err != nil {
			fatal(err)
		}
	}
	w.Flush()
	if err := w.Error(); err != nil {
		fatal(err)
	}
	fmt.Printf("Exported inventory: RU=%d PRIVATE=%d total=%d\n", len(ru), len(private), len(rows))
}

func addressCount(prefix netip.Prefix) string {
	hostBits := prefix.Addr().BitLen() - prefix.Bits()
	count := new(big.Int).Lsh(big.NewInt(1), uint(hostBits))
	return count.String()
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "geoip-inventory:", err)
	os.Exit(1)
}
