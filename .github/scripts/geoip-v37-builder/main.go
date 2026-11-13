package main

import (
	"bufio"
	"fmt"
	"math/big"
	"net/netip"
	"os"
	"sort"
	"strings"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/proto"
)

type sourceFile struct {
	Name string
	Path string
	Kind string
}

type trieNode struct {
	covered bool
	child   [2]*trieNode
}

type ipTrie struct {
	v4 *trieNode
	v6 *trieNode
}

func newIPTrie() *ipTrie                { return &ipTrie{v4: &trieNode{}, v6: &trieNode{}} }
func normalizeName(value string) string { return strings.ToLower(strings.TrimSpace(value)) }

func getBit(addr netip.Addr, pos int) int {
	if addr.Is4() {
		b := addr.As4()
		return int((b[pos/8] >> (7 - (pos % 8))) & 1)
	}
	b := addr.As16()
	return int((b[pos/8] >> (7 - (pos % 8))) & 1)
}

func setBit(addr netip.Addr, pos int) netip.Addr {
	if addr.Is4() {
		b := addr.As4()
		b[pos/8] |= 1 << (7 - (pos % 8))
		return netip.AddrFrom4(b)
	}
	b := addr.As16()
	b[pos/8] |= 1 << (7 - (pos % 8))
	return netip.AddrFrom16(b)
}

func (t *ipTrie) insert(prefix netip.Prefix) {
	prefix = prefix.Masked()
	addr, bits := prefix.Addr(), prefix.Bits()
	curr := t.v6
	if addr.Is4() {
		curr = t.v4
	}
	for i := 0; i < bits; i++ {
		if curr.covered {
			return
		}
		bit := getBit(addr, i)
		if curr.child[bit] == nil {
			curr.child[bit] = &trieNode{}
		}
		curr = curr.child[bit]
	}
	curr.covered = true
	curr.child[0], curr.child[1] = nil, nil
}

func compressNode(n *trieNode) bool {
	if n == nil {
		return false
	}
	if n.covered {
		n.child[0], n.child[1] = nil, nil
		return true
	}
	if !compressNode(n.child[0]) {
		n.child[0] = nil
	}
	if !compressNode(n.child[1]) {
		n.child[1] = nil
	}
	if n.child[0] != nil && n.child[0].covered && n.child[1] != nil && n.child[1].covered {
		n.covered = true
		n.child[0], n.child[1] = nil, nil
		return true
	}
	return n.child[0] != nil || n.child[1] != nil
}

func (t *ipTrie) compress() {
	if !compressNode(t.v4) {
		t.v4 = &trieNode{}
	}
	if !compressNode(t.v6) {
		t.v6 = &trieNode{}
	}
}

func cloneNode(n *trieNode) *trieNode {
	if n == nil {
		return nil
	}
	copyNode := &trieNode{covered: n.covered}
	copyNode.child[0], copyNode.child[1] = cloneNode(n.child[0]), cloneNode(n.child[1])
	return copyNode
}

func cloneTrie(source *ipTrie) *ipTrie {
	return &ipTrie{v4: cloneNode(source.v4), v6: cloneNode(source.v6)}
}

func intersectNode(target, mask *trieNode) *trieNode {
	if target == nil || mask == nil {
		return nil
	}
	if mask.covered {
		return cloneNode(target)
	}
	if target.covered {
		target = &trieNode{child: [2]*trieNode{{covered: true}, {covered: true}}}
	}
	out := &trieNode{}
	for bit := 0; bit < 2; bit++ {
		out.child[bit] = intersectNode(target.child[bit], mask.child[bit])
	}
	if out.child[0] == nil && out.child[1] == nil {
		return nil
	}
	if out.child[0] != nil && out.child[0].covered && out.child[1] != nil && out.child[1].covered {
		return &trieNode{covered: true}
	}
	return out
}

func (t *ipTrie) intersect(mask *ipTrie) {
	t.v4, t.v6 = intersectNode(t.v4, mask.v4), intersectNode(t.v6, mask.v6)
	if t.v4 == nil {
		t.v4 = &trieNode{}
	}
	if t.v6 == nil {
		t.v6 = &trieNode{}
	}
	t.compress()
}

func subtractNode(target, mask *trieNode) {
	if target == nil || mask == nil {
		return
	}
	if mask.covered {
		target.covered = false
		target.child[0], target.child[1] = nil, nil
		return
	}
	if target.covered {
		target.covered = false
		target.child[0], target.child[1] = &trieNode{covered: true}, &trieNode{covered: true}
	}
	if mask.child[0] != nil && target.child[0] != nil {
		subtractNode(target.child[0], mask.child[0])
	}
	if mask.child[1] != nil && target.child[1] != nil {
		subtractNode(target.child[1], mask.child[1])
	}
}

func (t *ipTrie) subtract(mask *ipTrie) {
	subtractNode(t.v4, mask.v4)
	subtractNode(t.v6, mask.v6)
	t.compress()
}

func extractPrefixes(n *trieNode, addr netip.Addr, depth, bitLen int, out *[]netip.Prefix) {
	if n == nil {
		return
	}
	if n.covered {
		*out = append(*out, netip.PrefixFrom(addr, depth).Masked())
		return
	}
	if depth >= bitLen {
		return
	}
	if n.child[0] != nil {
		extractPrefixes(n.child[0], addr, depth+1, bitLen, out)
	}
	if n.child[1] != nil {
		extractPrefixes(n.child[1], setBit(addr, depth), depth+1, bitLen, out)
	}
}

func (t *ipTrie) toPrefixes() []netip.Prefix {
	var out []netip.Prefix
	extractPrefixes(t.v4, netip.IPv4Unspecified(), 0, 32, &out)
	extractPrefixes(t.v6, netip.IPv6Unspecified(), 0, 128, &out)
	return out
}

func unionInto(dst, src *ipTrie) {
	for _, prefix := range src.toPrefixes() {
		dst.insert(prefix)
	}
	dst.compress()
}

// applyDirectPrecedence enforces the single-file routing policy. PRIVATE always
// wins; approved exact hosts, bounded subnet ranges and curated Telegram prefixes
// are carved from DIRECT. Privacy/telemetry classifications are not inputs and
// therefore never route an otherwise
// DIRECT destination through the VPN.
func applyDirectPrecedence(direct, privateTrie, blockedIPs *ipTrie) *ipTrie {
	result := cloneTrie(direct)
	result.subtract(privateTrie)
	result.subtract(blockedIPs)
	result.compress()
	return result
}

// newlyAddedDirectSpace returns only addresses contributed by additions
// that were not already in the existing DIRECT baseline, PRIVATE, or blocked.
func newlyAddedDirectSpace(additions, existing, privateTrie, blockedIPs *ipTrie) *ipTrie {
	result := cloneTrie(additions)
	result.subtract(privateTrie)
	result.subtract(blockedIPs)
	baseline := cloneTrie(existing)
	baseline.subtract(privateTrie)
	baseline.subtract(blockedIPs)
	result.subtract(baseline)
	result.compress()
	return result
}

func isBlockedCategory(category string) bool {
	category = normalizeName(category)
	for _, token := range []string{"blocked", "blacklist", "deny", "antifilter", "re-filter"} {
		if strings.Contains(category, token) {
			return true
		}
	}
	return false
}

// Direct/whitelist entries are audit signals only; they never subtract GeoIP data.
func targetCategory(source, category string) string {
	source, category = normalizeName(source), normalizeName(category)
	if isBlockedCategory(category) {
		return ""
	}
	if category == "private" {
		if source == "loyalsoldier-private" {
			return "private"
		}
		return ""
	}
	switch source {
	case "hydra":
		// Upstream roscomvpn-geoip publishes direct, whitelist and private,
		// not a strict geoip:ru category. direct/whitelist include RU/BY, CDN
		// and foreign infrastructure, so treat these entries as diagnostic
		// candidates only; never admit them as geographic RU on their own.
		if category == "direct" || category == "whitelist" {
			return "candidate"
		}
	case "grimbird":
		if category == "ru" {
			return "ru"
		}
		if strings.HasPrefix(category, "ru-") {
			if strings.Contains(category, "direct") || strings.Contains(category, "whitelist") || strings.Contains(category, "wl-") {
				return "candidate"
			}
			return "ru"
		}
	case "digne":
		if category == "ru" || category == "ru-ip" {
			return "ru"
		}
		if category == "direct-ip" || category == "whitelist" {
			return "candidate"
		}
	case "davoyan":
		if category == "ru" {
			return "ru"
		}
		if category == "wl-ru" {
			return "candidate"
		}
	case "kirill":
		if category == "whitelist" {
			return "candidate"
		}
	case "golukon", "loyalsoldier":
		if category == "ru" {
			return "ru"
		}
	case "loyalsoldier-by":
		if category == "by" {
			return "ru-by"
		}
	case "v2fly":
		switch category {
		case "ru":
			return "ru"
		case "by":
			return "ru-by"
		case "kz":
			return "ru-kz"
		}
	}
	return ""
}

func cidrPrefix(cidr *router.CIDR) (netip.Prefix, bool) {
	if cidr == nil || cidr.Prefix > 128 {
		return netip.Prefix{}, false
	}
	var addr netip.Addr
	switch len(cidr.Ip) {
	case 4:
		var b [4]byte
		copy(b[:], cidr.Ip)
		addr = netip.AddrFrom4(b)
	case 16:
		var b [16]byte
		copy(b[:], cidr.Ip)
		addr = netip.AddrFrom16(b)
	default:
		return netip.Prefix{}, false
	}
	if int(cidr.Prefix) > addr.BitLen() {
		return netip.Prefix{}, false
	}
	prefix := netip.PrefixFrom(addr, int(cidr.Prefix))
	return prefix, prefix == prefix.Masked()
}

func loadGeoIP(path string) (*router.GeoIPList, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(data) == 0 {
		return nil, fmt.Errorf("empty GeoIP file: %s", path)
	}
	list := new(router.GeoIPList)
	if err := proto.Unmarshal(data, list); err != nil {
		return nil, fmt.Errorf("invalid GeoIP %s: %w", path, err)
	}
	return list, nil
}

func minDirectBits(p netip.Prefix) int {
	if p.Addr().Is4() {
		return 8
	}
	return 24
}

func loadGeoIPSource(source sourceFile, coreRU, candidates, privateTrie, protectedLoyalsoldierRU, protectedV2FlyRU *ipTrie, regionalDirect map[string]*ipTrie, regionalRawCounts map[string]int, additional map[string]*ipTrie, categoryAudit map[string]int) (ruCount, candidateCount, privateCount int, err error) {
	list, err := loadGeoIP(source.Path)
	if err != nil {
		return 0, 0, 0, err
	}
	for _, entry := range list.Entry {
		if entry == nil {
			continue
		}
		target := targetCategory(source.Name, entry.CountryCode)
		if target != "" && entry.InverseMatch {
			return 0, 0, 0, fmt.Errorf("inverted %s category in %s", entry.CountryCode, source.Name)
		}
		role := target
		if role == "" {
			role = "ignored"
		}
		category := normalizeName(entry.CountryCode)
		if category == "" {
			category = "(empty)"
		}
		for _, cidr := range entry.Cidr {
			prefix, ok := cidrPrefix(cidr)
			if !ok || prefix.Bits() == 0 || (target != "" && target != "private" && prefix.Bits() < minDirectBits(prefix)) {
				if target != "" {
					return 0, 0, 0, fmt.Errorf("invalid, non-canonical or overly broad CIDR in %s category %s", source.Name, entry.CountryCode)
				}
				continue
			}
			categoryAudit[source.Name+"\t"+category+"\t"+role]++
			switch target {
			case "private":
				privateTrie.insert(prefix)
				privateCount++
			case "candidate":
				candidates.insert(prefix)
				candidateCount++
			case "ru", "ru-by", "ru-kz":
				coreRU.insert(prefix)
				ruCount++
				if target == "ru-by" {
					regionalDirect["BY"].insert(prefix)
					regionalRawCounts["BY"]++
				}
				if target == "ru-kz" {
					regionalDirect["KZ"].insert(prefix)
					regionalRawCounts["KZ"]++
				}
				if target == "ru" && source.Name == "loyalsoldier" {
					protectedLoyalsoldierRU.insert(prefix)
				}
				if target == "ru" && source.Name == "v2fly" {
					protectedV2FlyRU.insert(prefix)
				}
				if target == "ru" {
					if dst := additional[source.Name]; dst != nil {
						dst.insert(prefix)
					}
				}
			}
		}
	}
	return ruCount, candidateCount, privateCount, nil
}

func loadTextPrefixes(trie *ipTrie, path string) (int, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer file.Close()
	added := 0
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64*1024), 4*1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(strings.TrimPrefix(scanner.Text(), "\ufeff"))
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if idx := strings.IndexByte(line, '#'); idx >= 0 {
			line = strings.TrimSpace(line[:idx])
		}
		upper := strings.ToUpper(line)
		for _, prefix := range []string{"IP-CIDR,", "IP-CIDR6,", "IPSET,", "CIDR,"} {
			if strings.HasPrefix(upper, prefix) {
				line = strings.TrimSpace(line[len(prefix):])
				break
			}
		}
		fields := strings.FieldsFunc(line, func(r rune) bool { return r == ' ' || r == '\t' || r == ',' || r == ';' })
		for _, field := range fields {
			field = strings.Trim(field, "[](){}\"'")
			if field == "" {
				continue
			}
			if prefix, parseErr := netip.ParsePrefix(field); parseErr == nil {
				if prefix.Bits() == 0 || prefix != prefix.Masked() {
					return added, fmt.Errorf("invalid or non-canonical prefix in %s: %s", path, field)
				}
				trie.insert(prefix)
				added++
				break
			}
			if addr, parseErr := netip.ParseAddr(field); parseErr == nil {
				trie.insert(netip.PrefixFrom(addr, addr.BitLen()).Masked())
				added++
				break
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return added, err
	}
	return added, nil
}

// loadApprovedBlockedPrefixes accepts exact host IPs plus bounded explicit
// subnet.lst prefixes. Only explicitly configured Telegram routes may exceed
// the /16 IPv4 or /112 IPv6 automatic-carve thresholds (65,536 addresses).
func isCuratedWideBlockedPrefix(prefix netip.Prefix) bool {
	curated := map[string]struct{}{
		"91.105.192.0/23": {}, "91.108.4.0/22": {}, "91.108.8.0/21": {},
		"91.108.16.0/21": {}, "91.108.56.0/22": {}, "95.161.64.0/20": {},
		"149.154.160.0/20": {}, "185.76.151.0/24": {},
		"2001:67c:4e8::/48": {}, "2001:b28:f23c::/47": {},
		"2001:b28:f23f::/48": {}, "2a0a:f280::/32": {},
	}
	_, ok := curated[prefix.Masked().String()]
	return ok
}

func isApprovedBlockedPrefix(prefix netip.Prefix) bool {
	prefix = prefix.Masked()
	if prefix.Bits() == prefix.Addr().BitLen() || isCuratedWideBlockedPrefix(prefix) {
		return true
	}
	if prefix.Addr().Is4() {
		return prefix.Bits() >= 16 // at most 65,536 IPv4 addresses per automatic subnet carve
	}
	return prefix.Bits() >= 112 // at most 65,536 IPv6 addresses per automatic subnet carve
}

func loadApprovedBlockedPrefixes(trie *ipTrie, path string) (int, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer file.Close()
	count := 0
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64*1024), 4*1024*1024)
	for lineNo := 1; scanner.Scan(); lineNo++ {
		line := strings.TrimSpace(strings.TrimPrefix(scanner.Text(), "\ufeff"))
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if index := strings.IndexByte(line, '#'); index >= 0 {
			line = strings.TrimSpace(line[:index])
		}
		upper := strings.ToUpper(line)
		for _, prefix := range []string{"IP-CIDR,", "IP-CIDR6,", "CIDR,"} {
			if strings.HasPrefix(upper, prefix) {
				line = strings.TrimSpace(line[len(prefix):])
				break
			}
		}
		fields := strings.FieldsFunc(line, func(r rune) bool { return r == ' ' || r == '\t' || r == ',' || r == ';' })
		if len(fields) == 0 {
			continue
		}
		value := strings.Trim(fields[0], `[](){}\"'`)
		var prefix netip.Prefix
		if parsed, parseErr := netip.ParsePrefix(value); parseErr == nil {
			if parsed != parsed.Masked() {
				return count, fmt.Errorf("non-canonical block prefix in %s: %s", path, value)
			}
			prefix = parsed
		} else if addr, addrErr := netip.ParseAddr(value); addrErr == nil {
			prefix = netip.PrefixFrom(addr, addr.BitLen()).Masked()
		} else {
			return count, fmt.Errorf("invalid blocked prefix at line %d: %q", lineNo, value)
		}
		if !isApprovedBlockedPrefix(prefix) {
			return count, fmt.Errorf("blocked prefix at line %d exceeds safe carve threshold and is not an explicit Telegram route: %s", lineNo, prefix)
		}
		trie.insert(prefix)
		count++
	}
	if err := scanner.Err(); err != nil {
		return count, err
	}
	if count < 1000 {
		return count, fmt.Errorf("approved blocked-prefix set unexpectedly small: only %d entries", count)
	}
	return count, nil
}

// Explicit local-use/reserved networks supplemented by the current IANA
// Special-Purpose registry's Globally Reachable=False entries.
func insertBuiltInPrivate(t *ipTrie) {
	for _, value := range []string{
		"0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
		"169.254.0.0/16", "172.16.0.0/12", "192.0.2.0/24", "192.168.0.0/16",
		"198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
		"::/128", "::1/128", "fc00::/7", "fe80::/10", "ff00::/8", "2001:db8::/32",
	} {
		if p, err := netip.ParsePrefix(value); err == nil {
			t.insert(p)
		}
	}
}

func sortPrefixes(prefixes []netip.Prefix) {
	sort.Slice(prefixes, func(i, j int) bool {
		if prefixes[i].Addr().BitLen() != prefixes[j].Addr().BitLen() {
			return prefixes[i].Addr().BitLen() < prefixes[j].Addr().BitLen()
		}
		if cmp := prefixes[i].Addr().Compare(prefixes[j].Addr()); cmp != 0 {
			return cmp < 0
		}
		return prefixes[i].Bits() < prefixes[j].Bits()
	})
}

func countAddressSpace(prefixes []netip.Prefix, bitLen int) *big.Int {
	total := new(big.Int)
	for _, prefix := range prefixes {
		if prefix.Addr().BitLen() != bitLen {
			continue
		}
		count := new(big.Int).Lsh(big.NewInt(1), uint(bitLen-prefix.Bits()))
		total.Add(total, count)
	}
	return total
}

func setStats(set *ipTrie) (int, string, string) {
	copySet := cloneTrie(set)
	copySet.compress()
	prefixes := copySet.toPrefixes()
	return len(prefixes), countAddressSpace(prefixes, 32).String(), countAddressSpace(prefixes, 128).String()
}

func statsLine(label string, set *ipTrie) string {
	count, v4, v6 := setStats(set)
	return fmt.Sprintf("%s: CIDR=%d IPv4=%s IPv6=%s", label, count, v4, v6)
}

// prefixAddressCount returns the exact address count represented by one CIDR.
func prefixAddressCount(prefix netip.Prefix) *big.Int {
	return new(big.Int).Lsh(big.NewInt(1), uint(prefix.Addr().BitLen()-prefix.Bits()))
}

// countCoveredTrieAddresses sums the address space covered below one trie node.
// The caller provides the prefix depth represented by that node.
func countCoveredTrieAddresses(node *trieNode, depth, bitLen int) *big.Int {
	if node == nil {
		return new(big.Int)
	}
	if node.covered {
		return new(big.Int).Lsh(big.NewInt(1), uint(bitLen-depth))
	}
	total := new(big.Int)
	if node.child[0] != nil {
		total.Add(total, countCoveredTrieAddresses(node.child[0], depth+1, bitLen))
	}
	if node.child[1] != nil {
		total.Add(total, countCoveredTrieAddresses(node.child[1], depth+1, bitLen))
	}
	return total
}

// prefixOverlapAddressCount counts addresses from one prefix covered by a set.
// Walk the requested path once, then sum only the matching descendant subtree.
// This avoids allocating and intersecting a temporary trie for every output CIDR.
func prefixOverlapAddressCount(prefix netip.Prefix, coverage *ipTrie) *big.Int {
	prefix = prefix.Masked()
	addr, bits := prefix.Addr(), prefix.Bits()
	root := coverage.v6
	if addr.Is4() {
		root = coverage.v4
	}
	node := root
	for depth := 0; depth < bits; depth++ {
		if node == nil {
			return new(big.Int)
		}
		if node.covered {
			return prefixAddressCount(prefix)
		}
		node = node.child[getBit(addr, depth)]
	}
	return countCoveredTrieAddresses(node, bits, addr.BitLen())
}

type familyBGPReachability struct {
	TotalPrefixes              int
	FullPrefixes               int
	PartialPrefixes            int
	NonePrefixes               int
	TotalAddresses             *big.Int
	FullAddresses              *big.Int
	PartialAddresses           *big.Int
	PartialObservedAddresses   *big.Int
	PartialUnobservedAddresses *big.Int
	NoneAddresses              *big.Int
	ObservedAddresses          *big.Int
}

type bgpReachability struct {
	IPv4 familyBGPReachability
	IPv6 familyBGPReachability
}

func newFamilyBGPReachability() familyBGPReachability {
	return familyBGPReachability{
		TotalAddresses: new(big.Int), FullAddresses: new(big.Int),
		PartialAddresses: new(big.Int), PartialObservedAddresses: new(big.Int),
		PartialUnobservedAddresses: new(big.Int), NoneAddresses: new(big.Int),
		ObservedAddresses: new(big.Int),
	}
}

// classifyGlobalBGPReachability classifies each final, disjoint output CIDR as
// fully, partially, or not observed by the global ipverse prefix union. This is
// address-space aware: a less-specific route can fully cover a CIDR, while a set
// of more-specific routes can also fully cover it.
func classifyGlobalBGPReachability(prefixes []netip.Prefix, global *ipTrie) bgpReachability {
	result := bgpReachability{IPv4: newFamilyBGPReachability(), IPv6: newFamilyBGPReachability()}
	for _, prefix := range prefixes {
		family := &result.IPv6
		if prefix.Addr().Is4() {
			family = &result.IPv4
		}
		total := prefixAddressCount(prefix)
		observed := prefixOverlapAddressCount(prefix, global)
		family.TotalPrefixes++
		family.TotalAddresses.Add(family.TotalAddresses, total)
		family.ObservedAddresses.Add(family.ObservedAddresses, observed)
		switch {
		case observed.Sign() == 0:
			family.NonePrefixes++
			family.NoneAddresses.Add(family.NoneAddresses, total)
		case observed.Cmp(total) == 0:
			family.FullPrefixes++
			family.FullAddresses.Add(family.FullAddresses, total)
		default:
			family.PartialPrefixes++
			family.PartialAddresses.Add(family.PartialAddresses, total)
			family.PartialObservedAddresses.Add(family.PartialObservedAddresses, observed)
			unobserved := new(big.Int).Sub(total, observed)
			family.PartialUnobservedAddresses.Add(family.PartialUnobservedAddresses, unobserved)
		}
	}
	return result
}

// buildTwoGroupAgreement admits only address space shared by two distinct
// logical feed groups. Correlated feeds are first unioned into one group.
func buildTwoGroupAgreement(groups map[string]*ipTrie) *ipTrie {
	names := make([]string, 0, len(groups))
	for name := range groups {
		names = append(names, name)
	}
	sort.Strings(names)
	accepted := newIPTrie()
	for i := 0; i < len(names); i++ {
		for j := i + 1; j < len(names); j++ {
			pair := cloneTrie(groups[names[i]])
			pair.intersect(groups[names[j]])
			unionInto(accepted, pair)
		}
	}
	accepted.compress()
	return accepted
}

func overlapAddressesForSet(prefix netip.Prefix, set *ipTrie) string {
	return prefixOverlapAddressCount(prefix, set).String()
}

// writeAdditionalProvenance writes exact address-overlap counts for each accepted
// additional CIDR. Evidence columns are independent intersections and can overlap;
// they must not be summed to derive the final address count.
func writeAdditionalProvenance(path string, accepted *ipTrie, feeds, groups map[string]*ipTrie, twoGroups, additionalBGP, additionalRIR, asnRU, rirRU, globalBGP *ipTrie) error {
	prefixes := accepted.toPrefixes()
	sortPrefixes(prefixes)
	var b strings.Builder
	b.WriteString("PREFIX\tFAMILY\tPREFIX_ADDRESSES\tGRIMBIRD_OVERLAP_ADDRESSES\tDIGNE_OVERLAP_ADDRESSES\tDAVOYAN_OVERLAP_ADDRESSES\tGOLUKON_OVERLAP_ADDRESSES\tGROUPS_WITH_OVERLAP\tTWO_GROUP_CONFIRMED_ADDRESSES\tREGIONAL_RIR_OR_COMPANY_ASN_BGP_CONFIRMED_ADDRESSES\tRIR_RU_CONFIRMED_ADDRESSES\tREGIONAL_RIR_OR_COMPANY_ASN_BGP_OVERLAP_ADDRESSES\tRIR_RU_OVERLAP_ADDRESSES\tGLOBAL_BGP_OBSERVED_OVERLAP_ADDRESSES\n")
	for _, prefix := range prefixes {
		family := "IPv6"
		if prefix.Addr().Is4() {
			family = "IPv4"
		}
		groupNames := make([]string, 0, len(groups))
		for name, set := range groups {
			if prefixOverlapAddressCount(prefix, set).Sign() > 0 {
				groupNames = append(groupNames, name)
			}
		}
		sort.Strings(groupNames)
		fmt.Fprintf(&b, "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
			prefix,
			family,
			prefixAddressCount(prefix).String(),
			overlapAddressesForSet(prefix, feeds["grimbird"]),
			overlapAddressesForSet(prefix, feeds["digne"]),
			overlapAddressesForSet(prefix, feeds["davoyan"]),
			overlapAddressesForSet(prefix, feeds["golukon"]),
			strings.Join(groupNames, ","),
			overlapAddressesForSet(prefix, twoGroups),
			overlapAddressesForSet(prefix, additionalBGP),
			overlapAddressesForSet(prefix, additionalRIR),
			overlapAddressesForSet(prefix, asnRU),
			overlapAddressesForSet(prefix, rirRU),
			overlapAddressesForSet(prefix, globalBGP),
		)
	}
	return os.WriteFile(path, []byte(b.String()), 0644)
}

func bgpFamilyReport(label string, coverage familyBGPReachability) []string {
	return []string{
		fmt.Sprintf("%s output CIDRs: total=%d fully_observed=%d partially_observed=%d not_observed=%d", label, coverage.TotalPrefixes, coverage.FullPrefixes, coverage.PartialPrefixes, coverage.NonePrefixes),
		fmt.Sprintf("%s address coverage: total=%s fully_observed_prefix_space=%s partially_observed_prefix_space=%s none_observed_prefix_space=%s", label, coverage.TotalAddresses, coverage.FullAddresses, coverage.PartialAddresses, coverage.NoneAddresses),
		fmt.Sprintf("%s partial-CIDR split: actually_observed=%s still_unobserved=%s; total actually observed across all CIDRs=%s", label, coverage.PartialObservedAddresses, coverage.PartialUnobservedAddresses, coverage.ObservedAddresses),
	}
}

func writeOutput(priv, ru []netip.Prefix, path string) ([]byte, error) {
	result := new(router.GeoIPList)
	for _, target := range []struct {
		name     string
		prefixes []netip.Prefix
	}{{"PRIVATE", priv}, {"RU", ru}} {
		if len(target.prefixes) == 0 {
			continue
		}
		entry := &router.GeoIP{CountryCode: target.name}
		for _, prefix := range target.prefixes {
			if prefix.Addr().Is4() {
				a := prefix.Addr().As4()
				entry.Cidr = append(entry.Cidr, &router.CIDR{Ip: []byte{a[0], a[1], a[2], a[3]}, Prefix: uint32(prefix.Bits())})
			} else {
				a := prefix.Addr().As16()
				ip := make([]byte, 16)
				copy(ip, a[:])
				entry.Cidr = append(entry.Cidr, &router.CIDR{Ip: ip, Prefix: uint32(prefix.Bits())})
			}
		}
		result.Entry = append(result.Entry, entry)
	}
	data, err := proto.MarshalOptions{Deterministic: true}.Marshal(result)
	if err != nil {
		return nil, err
	}
	return data, os.WriteFile(path, data, 0644)
}

func verifyOutputBinary(path string, expectedRU, expectedPrivate *ipTrie) error {
	decoded, err := loadGeoIP(path)
	if err != nil {
		return err
	}
	if len(decoded.Entry) != 2 {
		return fmt.Errorf("expected exactly 2 protobuf categories (RU, PRIVATE), got %d", len(decoded.Entry))
	}
	seenCategories := map[string]bool{}
	decodedSets := map[string]*ipTrie{"RU": newIPTrie(), "PRIVATE": newIPTrie()}
	seenPrefixes := map[string]map[string]bool{"RU": {}, "PRIVATE": {}}
	for _, entry := range decoded.Entry {
		if entry == nil {
			return fmt.Errorf("nil protobuf GeoIP entry")
		}
		if entry.InverseMatch {
			return fmt.Errorf("inverted output GeoIP category")
		}
		category := strings.ToUpper(strings.TrimSpace(entry.CountryCode))
		if category != "RU" && category != "PRIVATE" {
			return fmt.Errorf("unexpected protobuf category %q", entry.CountryCode)
		}
		if seenCategories[category] {
			return fmt.Errorf("duplicate protobuf category %q", category)
		}
		seenCategories[category] = true
		for _, cidr := range entry.Cidr {
			prefix, ok := cidrPrefix(cidr)
			if !ok || prefix.Bits() == 0 {
				return fmt.Errorf("invalid CIDR in protobuf category %s", category)
			}
			if prefix != prefix.Masked() {
				return fmt.Errorf("non-canonical CIDR in protobuf category %s: %s", category, prefix)
			}
			key := prefix.String()
			if seenPrefixes[category][key] {
				return fmt.Errorf("duplicate prefix %s in protobuf category %s", key, category)
			}
			seenPrefixes[category][key] = true
			decodedSets[category].insert(prefix)
		}
	}
	if !seenCategories["RU"] || !seenCategories["PRIVATE"] {
		return fmt.Errorf("protobuf must contain both RU and PRIVATE categories")
	}
	for category, expected := range map[string]*ipTrie{"RU": expectedRU, "PRIVATE": expectedPrivate} {
		missing := cloneTrie(expected)
		missing.subtract(decodedSets[category])
		extra := cloneTrie(decodedSets[category])
		extra.subtract(expected)
		if len(missing.toPrefixes()) != 0 || len(extra.toPrefixes()) != 0 {
			return fmt.Errorf("protobuf category %s does not match builder address set: missing=%d extra=%d", category, len(missing.toPrefixes()), len(extra.toPrefixes()))
		}
	}
	overlap := cloneTrie(decodedSets["RU"])
	overlap.intersect(decodedSets["PRIVATE"])
	if len(overlap.toPrefixes()) != 0 {
		return fmt.Errorf("protobuf RU/PRIVATE overlap: %d prefixes", len(overlap.toPrefixes()))
	}
	return nil
}

func writeCategories(path string, privateCount, ruCount int) error {
	return os.WriteFile(path, []byte(fmt.Sprintf("RU\t%d\nPRIVATE\t%d\n", ruCount, privateCount)), 0644)
}

type sourceCounts struct {
	RU        int
	Candidate int
	Private   int
	Other     int
}

func (c sourceCounts) total() int { return c.RU + c.Candidate + c.Private + c.Other }

func sumSourceCounts(counts map[string]sourceCounts) sourceCounts {
	var total sourceCounts
	for _, count := range counts {
		total.RU += count.RU
		total.Candidate += count.Candidate
		total.Private += count.Private
		total.Other += count.Other
	}
	return total
}

func writeSourceCounts(path string, counts map[string]sourceCounts) error {
	order := []string{"hydra", "grimbird", "digne", "davoyan", "golukon", "loyalsoldier", "loyalsoldier-by", "v2fly", "loyalsoldier-private", "kirill", "hxehex-whitelist", "w1zardz-ru", "ru-asn-bgp", "rir-ru", "global-bgp", "iana-non-global", "iana-global-exceptions", "blocked-direct-exclusions"}
	var b strings.Builder
	b.WriteString("SOURCE\tRU_CATEGORY_CIDR_INPUTS\tCANDIDATE_CIDR_INPUTS\tPRIVATE_CIDR_INPUTS\tOTHER_EVIDENCE_CIDR_INPUTS\tTOTAL_CIDR_INPUTS\n")
	for _, name := range order {
		c := counts[name]
		fmt.Fprintf(&b, "%s\t%d\t%d\t%d\t%d\t%d\n", name, c.RU, c.Candidate, c.Private, c.Other, c.total())
	}
	total := sumSourceCounts(counts)
	fmt.Fprintf(&b, "TOTAL\t%d\t%d\t%d\t%d\t%d\n", total.RU, total.Candidate, total.Private, total.Other, total.total())
	return os.WriteFile(path, []byte(b.String()), 0644)
}

func writeCategoryAudit(path string, counts map[string]int) error {
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString("SOURCE\tNORMALIZED_CATEGORY\tASSIGNED_ROLE\tVALID_CIDR_INPUT_RECORDS\n")
	for _, key := range keys {
		fields := strings.Split(key, "\t")
		if len(fields) != 3 {
			return fmt.Errorf("invalid source category audit key: %q", key)
		}
		fmt.Fprintf(&b, "%s\t%s\t%s\t%d\n", fields[0], fields[1], fields[2], counts[key])
	}
	return os.WriteFile(path, []byte(b.String()), 0644)
}

func readExactPrefixSet(path string) (map[string]struct{}, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	result := make(map[string]struct{})
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64*1024), 4*1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(strings.TrimPrefix(scanner.Text(), "\ufeff"))
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if idx := strings.IndexByte(line, '#'); idx >= 0 {
			line = strings.TrimSpace(line[:idx])
		}
		upper := strings.ToUpper(line)
		for _, prefix := range []string{"IP-CIDR,", "IP-CIDR6,", "IPSET,", "CIDR,"} {
			if strings.HasPrefix(upper, prefix) {
				line = strings.TrimSpace(line[len(prefix):])
				break
			}
		}
		fields := strings.FieldsFunc(line, func(r rune) bool { return r == ' ' || r == '\t' || r == ',' || r == ';' })
		for _, field := range fields {
			field = strings.Trim(field, "[](){}\"'")
			if field == "" {
				continue
			}
			if prefix, parseErr := netip.ParsePrefix(field); parseErr == nil {
				if prefix.Bits() > 0 {
					result[prefix.Masked().String()] = struct{}{}
				}
				break
			}
			if addr, parseErr := netip.ParseAddr(field); parseErr == nil {
				result[netip.PrefixFrom(addr, addr.BitLen()).Masked().String()] = struct{}{}
				break
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return result, nil
}

func addressSpacePercent(covered, total *ipTrie, bitLen int) string {
	numerator := countAddressSpace(covered.toPrefixes(), bitLen)
	denominator := countAddressSpace(total.toPrefixes(), bitLen)
	if denominator.Sign() == 0 {
		return "n/a"
	}
	n := new(big.Float).SetPrec(128).SetInt(numerator)
	d := new(big.Float).SetPrec(128).SetInt(denominator)
	ratio := new(big.Float).SetPrec(128).Quo(n, d)
	ratio.Mul(ratio, big.NewFloat(100))
	return ratio.Text('f', 2) + "%"
}

func writeQualityReport(path string, lines []string) error {
	content := "GeoIP DIRECT RU+BY+KZ CLIENT v37 Quality Report\nGenerated by the Go builder; all coverage counts are exact address-space sums of disjoint trie prefixes.\n\n" + strings.Join(lines, "\n") + "\n"
	return os.WriteFile(path, []byte(content), 0644)
}

func main() {
	if len(os.Args) != 26 {
		fmt.Fprintf(os.Stderr, "usage: %s <hydra> <grimbird> <digne> <davoyan> <kirill> <golukon> <v2fly> <loyalsoldier-ru> <loyalsoldier-private> <hxehex> <w1zardz> <regional-asn-bgp> <rir-ru> <global-bgp> <iana-non-global> <iana-global-exceptions> <output> <categories> <sources> <source-counts> <category-audit> <quality-report> <additional-provenance> <loyalsoldier-by> <blocked-ip-list>\n", os.Args[0])
		os.Exit(2)
	}
	files := []sourceFile{
		{"hydra", os.Args[1], "dat"}, {"grimbird", os.Args[2], "dat"}, {"digne", os.Args[3], "dat"},
		{"davoyan", os.Args[4], "dat"}, {"kirill", os.Args[5], "dat"}, {"golukon", os.Args[6], "dat"},
		{"v2fly", os.Args[7], "dat"}, {"loyalsoldier", os.Args[8], "dat"}, {"loyalsoldier-private", os.Args[9], "dat"},
		{"loyalsoldier-by", os.Args[24], "dat"},
		{"hxehex-whitelist", os.Args[10], "text"}, {"w1zardz-ru", os.Args[11], "text"},
		{"ru-asn-bgp", os.Args[12], "text"}, {"rir-ru", os.Args[13], "text"}, {"global-bgp", os.Args[14], "text"},
	}
	ianaPrivatePath, ianaExceptionsPath := os.Args[15], os.Args[16]
	outputPath, categoryPath, sourcePath, countsPath, categoryAuditPath, qualityPath, provenancePath := os.Args[17], os.Args[18], os.Args[19], os.Args[20], os.Args[21], os.Args[22], os.Args[23]
	blockedPath := os.Args[25]

	coreRU, candidates, asnRU, rirRU, globalBGP, privateTrie := newIPTrie(), newIPTrie(), newIPTrie(), newIPTrie(), newIPTrie(), newIPTrie()
	protectedLoyalsoldierRU, protectedV2FlyRU := newIPTrie(), newIPTrie()
	regionalDirect := map[string]*ipTrie{"BY": newIPTrie(), "KZ": newIPTrie()}
	regionalRawCounts := map[string]int{"BY": 0, "KZ": 0}
	blockedIPs := newIPTrie()
	additional := map[string]*ipTrie{}
	for _, name := range []string{"grimbird", "digne", "davoyan", "golukon"} {
		additional[name] = newIPTrie()
	}
	insertBuiltInPrivate(privateTrie)
	counts := make(map[string]sourceCounts)
	categoryAudit := make(map[string]int)
	candidateRaw, coreRaw, bgpRaw, rirRaw, globalRaw, privateRaw := 0, 0, 0, 0, 0, 0

	for _, source := range files {
		if source.Kind == "dat" {
			ruCount, candidateCount, privateCount, err := loadGeoIPSource(source, coreRU, candidates, privateTrie, protectedLoyalsoldierRU, protectedV2FlyRU, regionalDirect, regionalRawCounts, additional, categoryAudit)
			if err != nil {
				panic(fmt.Errorf("%s: %w", source.Name, err))
			}
			counts[source.Name] = sourceCounts{RU: ruCount, Candidate: candidateCount, Private: privateCount}
			privateRaw += privateCount
			if source.Name == "loyalsoldier-private" {
				if privateCount == 0 {
					panic("Loyalsoldier private.dat has no PRIVATE CIDRs")
				}
				continue
			}
			if source.Name == "kirill" {
				candidateRaw += candidateCount
				continue
			}
			if source.Name == "hydra" && candidateCount == 0 {
				panic("Hydra direct/whitelist input contains no candidate CIDRs; refusing silent source loss")
			}
			if source.Name == "grimbird" || source.Name == "digne" || source.Name == "davoyan" || source.Name == "golukon" || source.Name == "loyalsoldier" || source.Name == "v2fly" || source.Name == "loyalsoldier-by" {
				if ruCount == 0 {
					panic(fmt.Errorf("source %s has no accepted DIRECT geographic CIDRs; refusing silent source loss", source.Name))
				}
			}
			candidateRaw += candidateCount
			coreRaw += ruCount
			fmt.Printf("Loaded %-20s RU=%d candidates=%d private=%d\n", source.Name, ruCount, candidateCount, privateCount)
			continue
		}

		target := candidates
		switch source.Name {
		case "ru-asn-bgp":
			target = asnRU
		case "rir-ru":
			target = rirRU
		case "global-bgp":
			target = globalBGP
		}
		matched, err := loadTextPrefixes(target, source.Path)
		if err != nil {
			panic(fmt.Errorf("%s: %w", source.Name, err))
		}
		switch source.Name {
		case "ru-asn-bgp", "rir-ru", "global-bgp":
			counts[source.Name] = sourceCounts{Other: matched}
		default:
			counts[source.Name] = sourceCounts{Candidate: matched}
		}
		switch source.Name {
		case "ru-asn-bgp":
			bgpRaw = matched
		case "rir-ru":
			rirRaw = matched
		case "global-bgp":
			globalRaw = matched
		default:
			candidateRaw += matched
		}
		if matched == 0 {
			panic(fmt.Errorf("source %s parsed zero prefixes; refusing incomplete build", source.Name))
		}
		fmt.Printf("Loaded %-20s CIDRs=%d\n", source.Name, matched)
	}

	ianaPrivateCount, err := loadTextPrefixes(privateTrie, ianaPrivatePath)
	if err != nil {
		panic(fmt.Errorf("IANA non-global registry: %w", err))
	}
	counts["iana-non-global"] = sourceCounts{Private: ianaPrivateCount}
	privateRaw += ianaPrivateCount
	if ianaPrivateCount < 20 {
		panic(fmt.Errorf("IANA non-global registry unexpectedly small: %d", ianaPrivateCount))
	}
	ianaExceptions := newIPTrie()
	ianaExceptionCount, err := loadTextPrefixes(ianaExceptions, ianaExceptionsPath)
	if err != nil {
		panic(fmt.Errorf("IANA globally-reachable exceptions: %w", err))
	}
	counts["iana-global-exceptions"] = sourceCounts{Other: ianaExceptionCount}
	if ianaExceptionCount == 0 {
		panic("IANA global-reachable exception list is empty; refusing ambiguous PRIVATE policy")
	}
	// Specific globally-reachable exceptions override broad special-purpose parent blocks.
	privateTrie.subtract(ianaExceptions)

	blockedRawCount, err := loadApprovedBlockedPrefixes(blockedIPs, blockedPath)
	if err != nil {
		panic(fmt.Errorf("exact blocked-IP input: %w", err))
	}
	counts["blocked-direct-exclusions"] = sourceCounts{Other: blockedRawCount}

	roleTotals := sumSourceCounts(counts)
	globalExactPrefixes, err := readExactPrefixSet(os.Args[14])
	if err != nil {
		panic(fmt.Errorf("read exact global BGP prefix set: %w", err))
	}
	if roleTotals.RU != coreRaw || roleTotals.Candidate != candidateRaw || roleTotals.Private != privateRaw || roleTotals.Other != bgpRaw+rirRaw+globalRaw+ianaExceptionCount+blockedRawCount {
		panic(fmt.Errorf("source-count/build-counter reconciliation failed: source roles RU=%d candidate=%d private=%d other=%d; builder RU=%d candidate=%d private=%d other=%d",
			roleTotals.RU, roleTotals.Candidate, roleTotals.Private, roleTotals.Other,
			coreRaw, candidateRaw, privateRaw, bgpRaw+rirRaw+globalRaw+ianaExceptionCount+blockedRawCount))
	}

	for _, trie := range []*ipTrie{coreRU, candidates, asnRU, rirRU, globalBGP, privateTrie, protectedLoyalsoldierRU, protectedV2FlyRU, regionalDirect["BY"], regionalDirect["KZ"], blockedIPs} {
		trie.compress()
	}
	for _, trie := range additional {
		trie.compress()
	}
	if len(protectedLoyalsoldierRU.toPrefixes()) == 0 {
		panic("Loyalsoldier geoip:ru is empty")
	}
	if len(protectedV2FlyRU.toPrefixes()) == 0 {
		panic("v2fly geoip:ru is empty")
	}
	if len(asnRU.toPrefixes()) == 0 {
		panic("RU/BY/KZ ASN/BGP is empty")
	}
	if len(regionalDirect["BY"].toPrefixes()) == 0 || len(regionalDirect["KZ"].toPrefixes()) == 0 {
		panic("BY or KZ regional GeoIP category is empty; refusing a partial DIRECT region build")
	}
	if len(rirRU.toPrefixes()) == 0 {
		panic("RIR RU allocation inventory is empty")
	}
	if len(globalBGP.toPrefixes()) == 0 {
		panic("global ipverse BGP observation set is empty")
	}

	// Trusted RU geographic layers: retain their address space, except for the
	// explicitly higher-priority PRIVATE set.
	trustedGeo := cloneTrie(protectedLoyalsoldierRU)
	unionInto(trustedGeo, protectedV2FlyRU)
	trustedShared := cloneTrie(protectedLoyalsoldierRU)
	trustedShared.intersect(protectedV2FlyRU)
	loyalsoldierOnly := cloneTrie(protectedLoyalsoldierRU)
	loyalsoldierOnly.subtract(protectedV2FlyRU)
	v2flyOnly := cloneTrie(protectedV2FlyRU)
	v2flyOnly.subtract(protectedLoyalsoldierRU)
	trustedPublic := cloneTrie(trustedGeo)
	trustedPublic.subtract(privateTrie)

	// Additional feeds are admitted where corroborated by two distinct logical
	// source groups, RU/BY/KZ RIR/company ASN BGP, or RIR-RU registration. Grimbird and Digne are
	// grouped together because their datasets are materially correlated and must
	// not count as two independent confirmations of one another.
	additionalUnion := newIPTrie()
	extraNames := []string{"grimbird", "digne", "davoyan", "golukon"}
	for _, name := range extraNames {
		unionInto(additionalUnion, additional[name])
	}
	additionalGroups := map[string]*ipTrie{
		"grimbird+digne-correlation-group": newIPTrie(),
		"davoyan":                          newIPTrie(),
		"golukon":                          newIPTrie(),
	}
	unionInto(additionalGroups["grimbird+digne-correlation-group"], additional["grimbird"])
	unionInto(additionalGroups["grimbird+digne-correlation-group"], additional["digne"])
	unionInto(additionalGroups["davoyan"], additional["davoyan"])
	unionInto(additionalGroups["golukon"], additional["golukon"])
	additionalTwoSources := buildTwoGroupAgreement(additionalGroups)
	additionalWithRUBGP := cloneTrie(additionalUnion)
	additionalWithRUBGP.intersect(asnRU)
	additionalWithRUBGP.subtract(privateTrie)
	additionalWithRIRRU := cloneTrie(additionalUnion)
	additionalWithRIRRU.intersect(rirRU)
	additionalWithRIRRU.subtract(privateTrie)
	additionalTwoSources.subtract(privateTrie)
	eligibleAdditional := cloneTrie(additionalTwoSources)
	unionInto(eligibleAdditional, additionalWithRUBGP)
	unionInto(eligibleAdditional, additionalWithRIRRU)
	eligibleAdditional.subtract(trustedGeo)
	// Count only newly contributing addresses; regional GeoIP and BGP layers
	// can already cover the same feed prefixes.
	eligibleAdditional.subtract(regionalDirect["BY"])
	eligibleAdditional.subtract(regionalDirect["KZ"])
	eligibleAdditional.subtract(asnRU)
	eligibleAdditional.compress()

	// Measure blocked addresses against the pre-carve DIRECT union, then remove
	// only the approved, source-classified blocked prefixes. PRIVATE is unaffected.
	preBlockDirect := cloneTrie(trustedGeo)
	unionInto(preBlockDirect, regionalDirect["BY"])
	unionInto(preBlockDirect, regionalDirect["KZ"])
	unionInto(preBlockDirect, eligibleAdditional)
	unionInto(preBlockDirect, asnRU)
	preBlockDirect.subtract(privateTrie)
	blockedDirectOverlap := cloneTrie(preBlockDirect)
	blockedDirectOverlap.intersect(blockedIPs)
	eligibleAdditional.subtract(blockedIPs)
	eligibleAdditional.compress()

	acceptedAdditionalEvidence := cloneTrie(eligibleAdditional)
	unconfirmedAdditional := cloneTrie(additionalUnion)
	unconfirmedAdditional.subtract(trustedGeo)
	unconfirmedAdditional.subtract(regionalDirect["BY"])
	unconfirmedAdditional.subtract(regionalDirect["KZ"])
	unconfirmedAdditional.subtract(asnRU)
	unconfirmedAdditional.subtract(acceptedAdditionalEvidence)
	unconfirmedAdditional.subtract(privateTrie)
	unconfirmedAdditional.subtract(blockedIPs)
	unconfirmedAdditional.compress()

	// Candidate lists do not carve out geo ranges. They are diagnostic signals;
	// candidate ranges already included by RU/BY/KZ RIR/company ASN BGP remain included via BGP.
	candidateOnRUBGP := cloneTrie(candidates)
	candidateOnRUBGP.intersect(asnRU)
	candidateOnRUBGP.subtract(privateTrie)
	candidateOnRIR := cloneTrie(candidates)
	candidateOnRIR.intersect(rirRU)
	candidateOnRIR.subtract(privateTrie)
	candidateOnTrusted := cloneTrie(candidates)
	candidateOnTrusted.intersect(trustedGeo)
	candidateOnTrusted.subtract(privateTrie)

	// Build the pre-ASN regional baseline separately so the report can measure
	// genuinely new address space contributed by RU/BY/KZ/company ASN origins.
	// Subtract PRIVATE and approved blocked destinations from both sides before calculating
	// the incremental ASN contribution; otherwise finalRU-beforeBGP is always zero.
	preASNDirect := cloneTrie(trustedGeo)
	unionInto(preASNDirect, regionalDirect["BY"])
	unionInto(preASNDirect, regionalDirect["KZ"])
	unionInto(preASNDirect, eligibleAdditional)
	preASNDirect = applyDirectPrecedence(preASNDirect, privateTrie, blockedIPs)
	newBGP := newlyAddedDirectSpace(asnRU, preASNDirect, privateTrie, blockedIPs)

	beforeBGP := cloneTrie(preASNDirect)
	unionInto(beforeBGP, asnRU)
	finalRU := applyDirectPrecedence(beforeBGP, privateTrie, blockedIPs)

	// Every selected regional/company origin prefix must survive in DIRECT
	// except for addresses removed by PRIVATE and approved blocked-destination
	// policies. Check the actual final address set, not only the pre-build BGP list.
	expectedASNDirect := applyDirectPrecedence(asnRU, privateTrie, blockedIPs)
	missingASNDirect := cloneTrie(expectedASNDirect)
	missingASNDirect.subtract(finalRU)
	if missing := missingASNDirect.toPrefixes(); len(missing) > 0 {
		sortPrefixes(missing)
		panic(fmt.Errorf("selected RIR/company ASN DIRECT coverage lost after allowed carve-outs: %d prefixes; first=%s", len(missing), missing[0]))
	}
	yandexTurkeyFinalCoverage := 0
	for _, value := range []string{"45.148.65.0/24", "2a14:48c6::/48"} {
		prefix, err := netip.ParsePrefix(value)
		if err != nil {
			panic(err)
		}
		expected := newIPTrie()
		expected.insert(prefix.Masked())
		expected = applyDirectPrecedence(expected, privateTrie, blockedIPs)
		missing := cloneTrie(expected)
		missing.subtract(finalRU)
		if lost := missing.toPrefixes(); len(lost) > 0 {
			panic(fmt.Errorf("Yandex Turkey AS212066 final DIRECT coverage lost beyond PRIVATE/blocked carve: %s", value))
		}
		yandexTurkeyFinalCoverage++
	}
	privateTrie.compress()

	// Protected-source invariants after PRIVATE policy. These compare address
	// coverage as sets, not literal CIDR strings.
	lostLoyalsoldier := cloneTrie(protectedLoyalsoldierRU)
	lostLoyalsoldier.subtract(privateTrie)
	lostLoyalsoldier.subtract(blockedIPs)
	checkLoyalsoldier := cloneTrie(lostLoyalsoldier)
	checkLoyalsoldier.subtract(finalRU)
	if lost := checkLoyalsoldier.toPrefixes(); len(lost) > 0 {
		sortPrefixes(lost)
		panic(fmt.Errorf("Loyalsoldier public coverage lost after PRIVATE: %d prefixes; first=%s", len(lost), lost[0]))
	}
	lostV2Fly := cloneTrie(protectedV2FlyRU)
	lostV2Fly.subtract(privateTrie)
	lostV2Fly.subtract(blockedIPs)
	checkV2Fly := cloneTrie(lostV2Fly)
	checkV2Fly.subtract(finalRU)
	if lost := checkV2Fly.toPrefixes(); len(lost) > 0 {
		sortPrefixes(lost)
		panic(fmt.Errorf("v2fly public coverage lost after PRIVATE: %d prefixes; first=%s", len(lost), lost[0]))
	}
	for _, country := range []string{"BY", "KZ"} {
		regionalExpected := cloneTrie(regionalDirect[country])
		regionalExpected.subtract(privateTrie)
		regionalExpected.subtract(blockedIPs)
		regionalMissing := cloneTrie(regionalExpected)
		regionalMissing.subtract(finalRU)
		if lost := regionalMissing.toPrefixes(); len(lost) > 0 {
			sortPrefixes(lost)
			panic(fmt.Errorf("%s direct GeoIP coverage lost after PRIVATE/blocked policy: %d prefixes; first=%s", country, len(lost), lost[0]))
		}
	}
	blockedStillDirect := cloneTrie(finalRU)
	blockedStillDirect.intersect(blockedIPs)
	if overlap := blockedStillDirect.toPrefixes(); len(overlap) > 0 {
		panic(fmt.Errorf("blocked-IP carve invariant failed: %d prefixes remain in DIRECT; first=%s", len(overlap), overlap[0]))
	}
	privateOverlap := cloneTrie(finalRU)
	privateOverlap.intersect(privateTrie)
	if overlap := privateOverlap.toPrefixes(); len(overlap) > 0 {
		panic(fmt.Errorf("PRIVATE/RU overlap invariant failed: %d prefixes", len(overlap)))
	}

	if len(finalRU.toPrefixes()) == 0 {
		panic("final RU category is empty")
	}
	if len(privateTrie.toPrefixes()) == 0 {
		panic("final PRIVATE category is empty")
	}

	// Global BGP audit is observation-only. ipverse contains AS data with
	// announcements seen in its preceding 90-day window, not a real-time RIB.
	observedGlobal := cloneTrie(finalRU)
	observedGlobal.intersect(globalBGP)
	notObservedGlobal := cloneTrie(finalRU)
	notObservedGlobal.subtract(globalBGP)
	finalInRUASN := cloneTrie(finalRU)
	finalInRUASN.intersect(asnRU)
	finalInRIR := cloneTrie(finalRU)
	finalInRIR.intersect(rirRU)
	finalTrusted := cloneTrie(finalRU)
	finalTrusted.intersect(trustedGeo)

	privatePrefixes, ruPrefixes := privateTrie.toPrefixes(), finalRU.toPrefixes()
	globalReachability := classifyGlobalBGPReachability(ruPrefixes, globalBGP)
	exactGlobalPrefixes, nonExactObservedPrefixes, noGlobalOverlapPrefixes := 0, 0, 0
	for _, prefix := range ruPrefixes {
		_, exact := globalExactPrefixes[prefix.String()]
		observed := prefixOverlapAddressCount(prefix, globalBGP)
		switch {
		case exact:
			exactGlobalPrefixes++
		case observed.Sign() > 0:
			nonExactObservedPrefixes++
		default:
			noGlobalOverlapPrefixes++
		}
	}
	if exactGlobalPrefixes+nonExactObservedPrefixes+noGlobalOverlapPrefixes != len(ruPrefixes) {
		panic("exact-prefix/global-overlap classification does not reconcile to final RU CIDR count")
	}
	if err := writeAdditionalProvenance(provenancePath, eligibleAdditional, additional, additionalGroups, additionalTwoSources, additionalWithRUBGP, additionalWithRIRRU, asnRU, rirRU, globalBGP); err != nil {
		panic(fmt.Errorf("write additional source provenance: %w", err))
	}
	sortPrefixes(privatePrefixes)
	sortPrefixes(ruPrefixes)
	ipv4Count := countAddressSpace(ruPrefixes, 32).String()
	ipv6Exact := countAddressSpace(ruPrefixes, 128)
	ipv6Count := ipv6Exact.String()
	ipv6Per32 := new(big.Int).Lsh(big.NewInt(1), 96)
	ipv6Equivalent32, ipv6Remainder := new(big.Int), new(big.Int)
	ipv6Equivalent32.QuoRem(new(big.Int).Set(ipv6Exact), ipv6Per32, ipv6Remainder)
	data, err := writeOutput(privatePrefixes, ruPrefixes, outputPath)
	if err != nil {
		panic(fmt.Errorf("write GeoIP protobuf: %w", err))
	}
	if err := verifyOutputBinary(outputPath, finalRU, privateTrie); err != nil {
		panic(fmt.Errorf("protobuf read-back verification: %w", err))
	}
	if err := writeCategories(categoryPath, len(privatePrefixes), len(ruPrefixes)); err != nil {
		panic(err)
	}
	if err := writeSourceCounts(countsPath, counts); err != nil {
		panic(err)
	}
	if err := writeCategoryAudit(categoryAuditPath, categoryAudit); err != nil {
		panic(fmt.Errorf("write raw source-category audit: %w", err))
	}

	manifest := []string{
		"GeoIP DIRECT RU+BY+KZ CLIENT v37 — unified regional direct coverage, company-affiliate ASN policy and curated blocked-destination carve-outs",
		"The single emitted RU category is the unified DIRECT region: geographic RU + BY + KZ, plus confirmed company-affiliate origin ASNs, minus approved blocked destinations and higher-priority PRIVATE space.",
		"Geographic sources: Loyalsoldier geoip:ru and geoip:by; v2fly geoip.dat categories ru, by and kz. The client still receives one geoip_RU.dat with only RU and PRIVATE categories.",
		"v24 is not fetched, protected, or used as a regression baseline.",
		"Additional RU GeoIP feeds: Grimbird, Digne, Davoyan, Golukon.",
		"Hydra roscomvpn-geoip currently publishes direct/whitelist/private, not strict geoip:ru; its direct/whitelist CIDRs are diagnostic candidates only, not an additional RU GeoIP feed.",
		"Additional-feed admission: overlap of two distinct logical source groups OR overlap with RIR-RU/BY/KZ or company-allowlisted ASN BGP OR overlap with an RIR-RU registered address resource.",
		"Correlation control: Grimbird and Digne are grouped together and cannot independently corroborate one another.",
		"Per-prefix additional-feed evidence is exported in geoip_RU_additional_provenance.tsv; overlap columns are independent and may overlap.",
		"All observed prefixes originated by RIR-RU or RIR-BY/KZ ASNs, plus curated Russian-company affiliate ASNs, are included regardless of ipverse countryCode; this identifies the network operator, not physical server location.",
		"RIR-RU IPv4/IPv6 resources are corroboration only; RIR-BY/KZ ASNs contribute observed origin prefixes, while registration country does not prove physical server location.",
		"Curated Russian-company ASN allowlist: geoip_RU_company_asns.txt; output manifest: geoip_RU_company_asn_manifest.tsv.",
		"Hydra direct/whitelist and other candidate lists are diagnostic only and never subtract from RU. Candidate-only ranges are not independently admitted.",
		"PRIVATE priority: built-in local/reserved ranges + IANA Globally-Reachable=False entries + Loyalsoldier private.dat. IANA Globally-Reachable=True exceptions carve out broad special-purpose blocks.",
		"Blocked exclusions: Antifilter ip.lst/ipresolve.lst exact hosts, bounded subnet.lst CIDRs, and explicitly configured RunetFreedom Telegram routes. Community and Re-filter remain review-only.",
		"RunetFreedom source configuration: https://github.com/runetfreedom/russia-blocked-geoip/blob/main/config.json",
		"Broader subnet.lst entries beyond /16 IPv4 or /112 IPv6 are not auto-carved; they are exported for manual review. This is third-party RKN-derived data, not an official API.",
		"Telemetry/privacy-risk classifications are audit-only and are NOT carved out of DIRECT. Confirmed telemetry stays DIRECT unless its exact IP independently appears in an approved blocked source; the GeoIP file cannot identify application or domain intent on shared IPs.",
		"Global BGP observation comes from ipverse/as-ip-blocks aggregated.json dataset; it covers ASes observed announcing within the preceding 90 days, not a real-time global RIB.",
		"A prefix not observed in the ipverse aggregate must not be called globally unroutable solely on that basis.",
		"Only existing GeoIP categories RU and PRIVATE are emitted; RU is the unified DIRECT RU+BY+KZ set. Both IPv4 and IPv6 are supported.",
		"Attribution: v2fly/geoip is licensed CC-BY-SA-4.0; upstream README also identifies DB-IP data under CC-BY-4.0. Preserve applicable notices.",
	}
	if err := os.WriteFile(sourcePath, []byte(strings.Join(manifest, "\n")+"\n"), 0644); err != nil {
		panic(err)
	}

	quality := []string{
		"=== FINAL OUTPUT ===",
		statsLine("RU", finalRU),
		statsLine("PRIVATE", privateTrie),
		fmt.Sprintf("Final IPv4 address count: %s", ipv4Count),
		fmt.Sprintf("Final IPv6 address count: %s", ipv6Count),
		fmt.Sprintf("IPv6 address-space equivalent in /32-sized units: %s full units plus %s addresses (1 /32 = 2^96 addresses)", ipv6Equivalent32.String(), ipv6Remainder.String()),
		fmt.Sprintf("Final protobuf bytes: %d", len(data)),
		"",
		"=== UNIFIED DIRECT REGION RU+BY+KZ ===",
		"The emitted RU category is intentionally used as one DIRECT bucket for geolocated Russia, Belarus and Kazakhstan plus confirmed company-affiliate origin ASN networks.",
		statsLine("Belarus direct GeoIP layer (Loyalsoldier BY + v2fly BY)", regionalDirect["BY"]),
		statsLine("Kazakhstan direct GeoIP layer (v2fly KZ)", regionalDirect["KZ"]),
		fmt.Sprintf("Raw BY GeoIP CIDR input records: %d", regionalRawCounts["BY"]),
		fmt.Sprintf("Raw KZ GeoIP CIDR input records: %d", regionalRawCounts["KZ"]),
		fmt.Sprintf("Final unified DIRECT RU+BY+KZ: IPv4=%s IPv6=%s", ipv4Count, ipv6Count),
		"Selected RIR-RU/BY/KZ and curated company ASN origins are preserved in final DIRECT except PRIVATE and approved blocked destinations.",
		fmt.Sprintf("Yandex Turkey AS212066 final DIRECT prefix checks (after PRIVATE/blocked carve): %d of 2", yandexTurkeyFinalCoverage),
		"=== TRUSTED GEOIP LAYERS ===",
		statsLine("Loyalsoldier geoip:ru", protectedLoyalsoldierRU),
		statsLine("v2fly geoip.dat ru", protectedV2FlyRU),
		statsLine("Loyalsoldier/v2fly shared address space", trustedShared),
		statsLine("Loyalsoldier-only address space", loyalsoldierOnly),
		statsLine("v2fly-only address space", v2flyOnly),
		statsLine("Trusted union before PRIVATE", trustedGeo),
		fmt.Sprintf("Loyalsoldier/v2fly overlap as share of union address space: IPv4=%s IPv6=%s", addressSpacePercent(trustedShared, trustedGeo, 32), addressSpacePercent(trustedShared, trustedGeo, 128)),
		fmt.Sprintf("Shared coverage as share of Loyalsoldier: IPv4=%s IPv6=%s", addressSpacePercent(trustedShared, protectedLoyalsoldierRU, 32), addressSpacePercent(trustedShared, protectedLoyalsoldierRU, 128)),
		fmt.Sprintf("Shared coverage as share of v2fly: IPv4=%s IPv6=%s", addressSpacePercent(trustedShared, protectedV2FlyRU, 32), addressSpacePercent(trustedShared, protectedV2FlyRU, 128)),
		statsLine("Trusted union after PRIVATE", trustedPublic),
		"",
		"=== ADDITIONAL GEOGRAPHIC FEEDS ===",
		statsLine("All additional GeoIP feed union", additionalUnion),
		statsLine("Accepted with 2+ distinct logical groups", additionalTwoSources),
		statsLine("Additional feed overlap regional RIR/company ASN BGP", additionalWithRUBGP),
		statsLine("Additional feed overlap RIR-RU resources", additionalWithRIRRU),
		statsLine("Accepted additional union (post-trust dedupe)", eligibleAdditional),
		statsLine("Unconfirmed additional feed space not included", unconfirmedAdditional),
		"",
		"=== ASN / RIR / GLOBAL ROUTING EVIDENCE ===",
		statsLine("RU/BY/KZ RIR or company-allowlisted ASN BGP prefixes", asnRU),
		statsLine("RIR-RU registered address resources", rirRU),
		statsLine("All-AS ipverse global BGP observation union", globalBGP),
		statsLine("Final DIRECT covered by RU/BY/KZ RIR/company ASN BGP", finalInRUASN),
		statsLine("New final address space from RU/BY/KZ RIR/company ASN BGP layer", newBGP),
		statsLine("Final RU covered by RIR-RU resource registration", finalInRIR),
		statsLine("Final RU covered by trusted GeoIP layers", finalTrusted),
		statsLine("Final RU observed in global ipverse aggregate", observedGlobal),
		statsLine("Final RU not observed in global ipverse aggregate", notObservedGlobal),
		"",
		"=== GLOBAL BGP COVERAGE BY FINAL OUTPUT CIDR ===",
	}
	quality = append(quality, bgpFamilyReport("IPv4", globalReachability.IPv4)...)
	quality = append(quality, bgpFamilyReport("IPv6", globalReachability.IPv6)...)
	quality = append(quality,
		fmt.Sprintf("Final output CIDRs with an exact same-prefix global BGP announcement: %d", exactGlobalPrefixes),
		fmt.Sprintf("Final output CIDRs with BGP address-space overlap but no exact same-prefix announcement: %d", nonExactObservedPrefixes),
		fmt.Sprintf("Final output CIDRs with no global BGP address-space overlap: %d", noGlobalOverlapPrefixes),
		fmt.Sprintf("Final output CIDRs without an exact same-prefix BGP announcement (the latter two classes combined): %d", nonExactObservedPrefixes+noGlobalOverlapPrefixes),
		"Coverage classes are mutually exclusive per disjoint final output CIDR; partial CIDRs are counted in the partial bucket.",
		"Coverage is based on address-space intersection: a less-specific route can fully cover an output CIDR, and multiple more-specific routes can collectively cover it.",
		"Exact same-prefix announcement counts are separate from address-space observation; CIDRs with no exact route may still overlap covering or more-specific routes.",
		"ipverse is an up-to-90-day observation set, not a real-time global RIB; absent means not observed in this dataset, not proven unroutable.",
		"",
		"=== LOGICAL SOURCE GROUPS ===",
		statsLine("Correlated group: Grimbird + Digne", additionalGroups["grimbird+digne-correlation-group"]),
		statsLine("Independent group: Davoyan", additionalGroups["davoyan"]),
		statsLine("Independent group: Golukon", additionalGroups["golukon"]),
		"Two-feed acceptance is computed between these logical groups; Grimbird and Digne cannot self-confirm.",
		"",
		"=== ADDITIONAL PREFIX PROVENANCE ===",
		fmt.Sprintf("Accepted additional CIDR rows: %d", len(eligibleAdditional.toPrefixes())),
		"Per-prefix overlap evidence: geoip_RU_additional_provenance.tsv (source, logical group, two-group confirmation, RIR-RU/BY/KZ or company ASN BGP, RIR-RU resources, global BGP).",
		"The overlap columns are exact address intersections, independent, and may overlap; do not add them to calculate final coverage.",
		"",
		"=== BLOCKED DESTINATION EXCLUSIONS ===",
		"Sources: antifilter.download ip.lst + ipresolve.lst exact host IPs; subnet.lst bounded CIDRs; RunetFreedom's explicitly configured Telegram routes.",
		"RunetFreedom community.lst and Re-filter ipsum.lst are exported as review-only candidates and are never subtracted from DIRECT automatically.",
		fmt.Sprintf("Approved blocked prefix records loaded (unique CIDR entries): %d", blockedRawCount),
		statsLine("Blocked address space intersecting pre-carve DIRECT", blockedDirectOverlap),
		fmt.Sprintf("Approved blocked IPv4 address space: %s", countAddressSpace(blockedIPs.toPrefixes(), 32).String()),
		fmt.Sprintf("Approved blocked IPv6 address space: %s", countAddressSpace(blockedIPs.toPrefixes(), 128).String()),
		"ip.lst and ipresolve.lst are accepted only as individual host IPs (/32,/128). subnet.lst is auto-carved only at /16 IPv4 or /112 IPv6 or narrower (at most 65,536 addresses); broader entries are review-only.",
		"The explicitly configured RunetFreedom Telegram service prefixes are allowed as curated exceptions to the subnet-width threshold.",
		"This is a third-party RKN-derived snapshot, not an official API and not a comprehensive BY/KZ blocklist. PRIVATE remains in PRIVATE/DIRECT regardless of blocked-list membership.",
		"Community and Re-filter proposals do not create carve-outs. Telemetry/privacy-risk labels are informational only; confirmed telemetry stays DIRECT unless its exact IP is independently in an approved blocked source.",
		"=== DIRECT / WHITELIST SIGNALS (NO CARVE-OUT) ===",
		statsLine("Direct/whitelist candidate union", candidates),
		statsLine("Candidates overlapping regional RIR/company ASN BGP", candidateOnRUBGP),
		statsLine("Candidates overlapping RIR-RU allocations", candidateOnRIR),
		statsLine("Candidates overlapping trusted GeoIP layers", candidateOnTrusted),
		"",
		"=== BUILD COUNTERS ===",
		fmt.Sprintf("Geographic DIRECT source CIDR inputs (RU+BY+KZ trusted + additional): %d", coreRaw),
		fmt.Sprintf("Direct/whitelist candidate CIDR inputs: %d", candidateRaw),
		fmt.Sprintf("RU/BY/KZ RIR/company ASN BGP CIDR inputs: %d", bgpRaw),
		fmt.Sprintf("RIR-RU CIDR inputs: %d", rirRaw),
		fmt.Sprintf("Global ipverse BGP CIDR inputs: %d", globalRaw),
		fmt.Sprintf("Reconciled source role totals: RU=%d candidate=%d PRIVATE=%d other_evidence=%d total=%d", roleTotals.RU, roleTotals.Candidate, roleTotals.Private, roleTotals.Other, roleTotals.total()),
		"Source contribution report separates builder-assigned roles; geoip_RU_category_audit.tsv additionally counts valid CIDR rows by each raw GeoIP category and assigned role, including ignored categories.",
		fmt.Sprintf("Raw GeoIP category audit rows (category/role combinations): %d", len(categoryAudit)),
		fmt.Sprintf("IANA non-global CIDR inputs: %d", counts["iana-non-global"].Private),
		fmt.Sprintf("IANA globally-reachable exceptions: %d", counts["iana-global-exceptions"].Other),
		fmt.Sprintf("Approved blocked-prefix entries (other evidence role): %d", counts["blocked-direct-exclusions"].Other),
		"",
		"=== INTERPRETATION LIMITS ===",
		"- RIR country is resource registration country, not physical geolocation.",
		"- RIR RU/BY/KZ or company ASN origin identifies an operator network, not proof that every announced address or server is physically located in that country.",
		"- The unified RU output category is a DIRECT routing aggregate for RU+BY+KZ, not a claim that all included addresses are physically located in Russia.",
		"- RKN-derived blocked inputs are third-party snapshots; approved exact host IPs and bounded explicit network prefixes carve DIRECT, but these feeds are not comprehensive proof of every blocked domain or country-specific BY/KZ restriction.",
		"- ipverse global coverage is a 90-day observed-AS aggregate, not a real-time global BGP RIB.",
		"- CIDR counts are not address counts; IPv4/IPv6 address coverage above is calculated exactly from disjoint prefixes.",
		"- Grimbird and Digne are treated as one correlated group; other feeds may still share upstream data and are not guaranteed statistically independent.",
	)
	if err := writeQualityReport(qualityPath, quality); err != nil {
		panic(err)
	}

	fmt.Println("============================================================")
	fmt.Println("GEOIP DIRECT RU+BY+KZ CLIENT v37 — QUALITY EDITION")
	fmt.Println("============================================================")
	fmt.Println(statsLine("Final RU", finalRU))
	fmt.Println(statsLine("Final PRIVATE", privateTrie))
	fmt.Println(statsLine("Loyalsoldier RU", protectedLoyalsoldierRU))
	fmt.Println(statsLine("v2fly RU", protectedV2FlyRU))
	fmt.Println(statsLine("Additional accepted", eligibleAdditional))
	fmt.Println(statsLine("Not observed in global ipverse aggregate", notObservedGlobal))
	fmt.Printf("Final protobuf bytes: %d\n", len(data))
	fmt.Printf("Geographic DIRECT RU+BY+KZ source CIDR inputs: %d; candidate inputs: %d; RU/BY/KZ RIR/company ASN BGP inputs: %d; RIR-RU inputs: %d; global BGP prefixes: %d\n", coreRaw, candidateRaw, bgpRaw, rirRaw, globalRaw)
	fmt.Println("Loyalsoldier public coverage preservation: PASSED (subject to PRIVATE)")
	fmt.Println("v2fly public coverage preservation: PASSED (subject to PRIVATE)")
	fmt.Println("PRIVATE/RU disjointness invariant: PASSED")
	fmt.Println("Direct/whitelist carve-out: DISABLED")
	fmt.Println("Grimbird/Digne correlation grouping: PASSED")
	fmt.Println("Global BGP prefix-level coverage classification: COMPLETED")
}
