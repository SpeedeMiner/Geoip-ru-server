package main

import (
	"net/netip"
	"testing"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
)

func TestAddressCountSupportsIPv4AndIPv6(t *testing.T) {
	cases := []struct {
		prefix string
		want   string
	}{
		{"192.0.2.0/24", "256"},
		{"192.0.2.1/32", "1"},
		{"2001:db8::/32", "79228162514264337593543950336"},
		{"2001:db8::1/128", "1"},
	}
	for _, tc := range cases {
		prefix, err := netip.ParsePrefix(tc.prefix)
		if err != nil {
			t.Fatal(err)
		}
		if got := addressCount(prefix); got != tc.want {
			t.Errorf("addressCount(%s)=%s, want %s", tc.prefix, got, tc.want)
		}
	}
}

func TestCIDRPrefixRejectsNonCanonicalProtobuf(t *testing.T) {
	_, err := cidrPrefix(&router.CIDR{
		Ip: []byte{192, 0, 2, 1},
		Prefix: 24,
	})
	if err == nil {
		t.Fatal("expected non-canonical prefix error")
	}
}

func TestCIDRPrefixAcceptsCanonicalProtobuf(t *testing.T) {
	prefix, err := cidrPrefix(&router.CIDR{
		Ip: []byte{192, 0, 2, 0},
		Prefix: 24,
	})
	if err != nil {
		t.Fatal(err)
	}
	if prefix.String() != "192.0.2.0/24" {
		t.Fatalf("unexpected prefix: %s", prefix)
	}
}
