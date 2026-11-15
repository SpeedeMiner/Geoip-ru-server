package main

import (
	"fmt"
	"math/big"
	"net/netip"
	"os"
	"path/filepath"
	"strings"
	"testing"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/proto"
)

func mustPrefix(t *testing.T, value string) netip.Prefix {
	t.Helper()
	prefix, err := netip.ParsePrefix(value)
	if err != nil {
		t.Fatal(err)
	}
	return prefix
}

func TestGlobalBGPUsesAggregateAndMoreSpecificCoverage(t *testing.T) {
	target := mustPrefix(t, "192.0.2.0/23")

	parent := newIPTrie()
	parent.insert(mustPrefix(t, "192.0.0.0/16"))
	if got := prefixOverlapAddressCount(target, parent); got.Cmp(big.NewInt(512)) != 0 {
		t.Fatalf("less-specific aggregate should fully cover /23: got %s", got)
	}

	specifics := newIPTrie()
	specifics.insert(mustPrefix(t, "192.0.2.0/24"))
	specifics.insert(mustPrefix(t, "192.0.3.0/24"))
	if got := prefixOverlapAddressCount(target, specifics); got.Cmp(big.NewInt(512)) != 0 {
		t.Fatalf("two more-specific routes should fully cover /23: got %s", got)
	}

	partial := newIPTrie()
	partial.insert(mustPrefix(t, "192.0.2.0/24"))
	if got := prefixOverlapAddressCount(target, partial); got.Cmp(big.NewInt(256)) != 0 {
		t.Fatalf("one /24 should partially cover /23: got %s", got)
	}
}

func TestGlobalBGPReachabilityClassifiesPrefixAndAddressCoverage(t *testing.T) {
	final := []netip.Prefix{
		mustPrefix(t, "192.0.2.0/23"),
		mustPrefix(t, "198.51.100.0/24"),
		mustPrefix(t, "203.0.113.0/24"),
	}
	observed := newIPTrie()
	observed.insert(mustPrefix(t, "192.0.2.0/24"))
	observed.insert(mustPrefix(t, "198.51.100.0/24"))
	stats := classifyGlobalBGPReachability(final, observed).IPv4
	if stats.TotalPrefixes != 3 || stats.FullPrefixes != 1 || stats.PartialPrefixes != 1 || stats.NonePrefixes != 1 {
		t.Fatalf("unexpected prefix classes: %+v", stats)
	}
	if stats.TotalAddresses.Cmp(big.NewInt(1024)) != 0 || stats.ObservedAddresses.Cmp(big.NewInt(512)) != 0 {
		t.Fatalf("unexpected address totals: total=%s observed=%s", stats.TotalAddresses, stats.ObservedAddresses)
	}
}

func TestGlobalBGPIPv6PartialCoverageIsExact(t *testing.T) {
	final := []netip.Prefix{mustPrefix(t, "2001:db8::/126")}
	observed := newIPTrie()
	observed.insert(mustPrefix(t, "2001:db8::/127"))
	stats := classifyGlobalBGPReachability(final, observed).IPv6
	if stats.TotalPrefixes != 1 || stats.PartialPrefixes != 1 || stats.FullPrefixes != 0 || stats.NonePrefixes != 0 {
		t.Fatalf("unexpected IPv6 prefix class: %+v", stats)
	}
	if stats.TotalAddresses.Cmp(big.NewInt(4)) != 0 || stats.PartialObservedAddresses.Cmp(big.NewInt(2)) != 0 || stats.PartialUnobservedAddresses.Cmp(big.NewInt(2)) != 0 {
		t.Fatalf("unexpected IPv6 address split: total=%s partial-observed=%s partial-unobserved=%s", stats.TotalAddresses, stats.PartialObservedAddresses, stats.PartialUnobservedAddresses)
	}
}

func TestSourceCountRolesReconcileIndependently(t *testing.T) {
	counts := map[string]sourceCounts{
		"feed-a": {RU: 100, Candidate: 20},
		"feed-b": {RU: 50, Private: 3},
		"bgp":    {Other: 75},
	}
	totals := sumSourceCounts(counts)
	if totals.RU != 150 || totals.Candidate != 20 || totals.Private != 3 || totals.Other != 75 || totals.total() != 248 {
		t.Fatalf("unexpected source role totals: %+v total=%d", totals, totals.total())
	}
}

func TestRegionalGeoIPCategoryMapping(t *testing.T) {
	cases := []struct{ source, category, want string }{
		{"loyalsoldier", "ru", "ru"},
		{"loyalsoldier-by", "by", "ru-by"},
		{"v2fly", "ru", "ru"},
		{"v2fly", "by", "ru-by"},
		{"v2fly", "kz", "ru-kz"},
		{"v2fly", "de", ""},
		{"loyalsoldier-by", "ru", ""},
	}
	for _, tc := range cases {
		if got := targetCategory(tc.source, tc.category); got != tc.want {
			t.Errorf("targetCategory(%q,%q)=%q, want %q", tc.source, tc.category, got, tc.want)
		}
	}
}

func TestBlockedPrefixLoaderAcceptsHostsBoundedSubnetsAndRejectsUnsafeWideNetworks(t *testing.T) {
	good := filepath.Join(t.TempDir(), "blocked-good.txt")
	var content strings.Builder
	for i := 0; i < 1000; i++ {
		fmt.Fprintf(&content, "198.51.%d.%d\n", i/256, i%256)
	}
	content.WriteString("2001:db8::1\n198.51.100.0/24\n2001:db8:1::/112\n91.108.4.0/22 # curated Telegram\n")
	if err := os.WriteFile(good, []byte(content.String()), 0600); err != nil {
		t.Fatal(err)
	}
	trie := newIPTrie()
	count, err := loadApprovedBlockedPrefixes(trie, good)
	if err != nil {
		t.Fatal(err)
	}
	if count != 1004 {
		t.Fatalf("expected 1004 approved entries, got %d", count)
	}

	for _, value := range []string{"203.0.0.0/15", "2001:db8::/111", "2001:db8:1::/48", "192.0.0.0/8"} {
		bad := filepath.Join(t.TempDir(), "blocked-bad.txt")
		if err := os.WriteFile(bad, []byte(value+"\n"), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := loadApprovedBlockedPrefixes(newIPTrie(), bad); err == nil {
			t.Fatalf("unsafe broad blocked prefix %s must be rejected", value)
		}
	}
}

func TestDirectPrecedenceKeepsUnblockedAndTelemetryDestinationsDirect(t *testing.T) {
	direct := newIPTrie()
	direct.insert(mustPrefix(t, "198.51.100.0/24"))
	private := newIPTrie()
	private.insert(mustPrefix(t, "198.51.100.0/30"))
	blocked := newIPTrie()
	blocked.insert(mustPrefix(t, "198.51.100.5/32"))
	final := applyDirectPrecedence(direct, private, blocked)
	contains := func(addr string) bool {
		a := netip.MustParseAddr(addr)
		probe := newIPTrie()
		probe.insert(netip.PrefixFrom(a, a.BitLen()))
		probe.subtract(final)
		return len(probe.toPrefixes()) == 0
	}
	if contains("198.51.100.1") {
		t.Fatal("PRIVATE must never remain in the public DIRECT set")
	}
	if contains("198.51.100.5") {
		t.Fatal("an exact blocked host must be carved from DIRECT")
	}
	if !contains("198.51.100.6") {
		t.Fatal("an unblocked neighboring host must stay DIRECT")
	}
	// There is intentionally no telemetry/privacy-risk argument: these labels
	// cannot alter DIRECT membership in this GeoIP-only policy.
}

func TestCorrelatedGrimbirdAndDigneCannotSelfConfirm(t *testing.T) {
	grimbird := newIPTrie()
	grimbird.insert(mustPrefix(t, "198.51.100.0/24"))
	digne := newIPTrie()
	digne.insert(mustPrefix(t, "198.51.100.0/24"))
	davoyan := newIPTrie()
	golukon := newIPTrie()

	correlatedGroup := newIPTrie()
	unionInto(correlatedGroup, grimbird)
	unionInto(correlatedGroup, digne)
	groups := map[string]*ipTrie{
		"grimbird+digne-correlation-group": correlatedGroup,
		"davoyan":                          davoyan,
		"golukon":                          golukon,
	}
	if got := len(buildTwoGroupAgreement(groups).toPrefixes()); got != 0 {
		t.Fatalf("correlated feeds self-confirmed: got %d prefixes", got)
	}

	davoyan.insert(mustPrefix(t, "198.51.100.0/24"))
	groups["davoyan"] = davoyan
	if got := len(buildTwoGroupAgreement(groups).toPrefixes()); got != 1 {
		t.Fatalf("independent group overlap should confirm: got %d prefixes", got)
	}
}

func TestNewlyAddedDirectSpaceCountsOnlyUncoveredUnblockedAddresses(t *testing.T) {
	existing := newIPTrie()
	existing.insert(mustPrefix(t, "192.0.2.0/24"))
	additions := newIPTrie()
	additions.insert(mustPrefix(t, "192.0.2.0/25")) // already covered by baseline
	additions.insert(mustPrefix(t, "192.0.3.0/24")) // new contribution before carve
	private := newIPTrie()
	private.insert(mustPrefix(t, "192.0.3.0/25"))
	blocked := newIPTrie()
	blocked.insert(mustPrefix(t, "192.0.3.128/32"))
	got := newlyAddedDirectSpace(additions, existing, private, blocked)
	addresses := countAddressSpace(got.toPrefixes(), 32)
	if addresses.Cmp(big.NewInt(127)) != 0 {
		t.Fatalf("expected 127 newly added IPv4 addresses after PRIVATE and blocked carve, got %s", addresses)
	}
}

func TestReadExactPrefixSetParsesCanonicalPrefixesAndAddresses(t *testing.T) {
	path := filepath.Join(t.TempDir(), "global-bgp.txt")
	content := "# comment\nIP-CIDR, 192.0.2.7/24,no-resolve\n\"198.51.100.1\"\n[203.0.113.0/24]\n2001:db8::/32\n"
	if err := os.WriteFile(path, []byte(content), 0600); err != nil {
		t.Fatal(err)
	}
	got, err := readExactPrefixSet(path)
	if err != nil {
		t.Fatal(err)
	}
	expected := []string{"192.0.2.0/24", "198.51.100.1/32", "203.0.113.0/24", "2001:db8::/32"}
	if len(got) != len(expected) {
		t.Fatalf("expected %d exact prefixes, got %d: %#v", len(expected), len(got), got)
	}
	for _, prefix := range expected {
		if _, ok := got[prefix]; !ok {
			t.Errorf("missing canonical prefix %s", prefix)
		}
	}
}

func TestInputCIDRDoesNotMaskHostBits(t *testing.T) {
	p := filepath.Join(t.TempDir(), "raw.txt")
	if err := os.WriteFile(p, []byte("1.2.3.4/8\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := loadTextPrefixes(newIPTrie(), p); err == nil {
		t.Fatal("accepted non-canonical input")
	}
}

func TestSelectedDATRejectsInverseAndWideRoutes(t *testing.T) {
	for _, tc := range []struct {
		name    string
		inverse bool
		prefix  uint32
		raw     []byte
	}{
		{"inverse", true, 24, []byte{192, 0, 2, 0}},
		{"wide", false, 1, []byte{0, 0, 0, 0}},
		{"host-bits", false, 24, []byte{192, 0, 2, 1}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p := filepath.Join(t.TempDir(), "raw.dat")
			body, err := proto.Marshal(&router.GeoIPList{Entry: []*router.GeoIP{{CountryCode: "RU", InverseMatch: tc.inverse, Cidr: []*router.CIDR{{Ip: tc.raw, Prefix: tc.prefix}}}}})
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(p, body, 0600); err != nil {
				t.Fatal(err)
			}
			_, _, _, err = loadGeoIPSource(sourceFile{Name: "grimbird", Path: p}, nil, nil, nil, nil, nil, nil, nil, nil, nil)
			if err == nil {
				t.Fatal("unsafe selected category accepted")
			}
		})
	}
}
