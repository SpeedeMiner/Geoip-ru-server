#!/usr/bin/env bash
# Run VPN measurements in a disposable network namespace. Host OUTPUT policy
# and default routes remain untouched; only namespace traffic is forwarded/NATed.
set -euo pipefail

if [[ "$#" -lt 2 || "$1" != "--" ]]; then
  echo "usage: $0 -- COMMAND [ARG ...]" >&2
  exit 2
fi
shift

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[vpn-netns] must_run_as_root=true" >&2
  exit 2
fi

for command_name in ip iptables iptables-save iptables-restore sysctl; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "[vpn-netns] missing_command=$command_name" >&2
    exit 2
  }
done

RUN_NUMBER="${GITHUB_RUN_ID:-$$}"
ATTEMPT="${GITHUB_RUN_ATTEMPT:-1}"
SUFFIX="$((RUN_NUMBER % 10000))"
OCTET="$((SUFFIX % 200 + 20))"
NAMESPACE="geoip-vpn-${RUN_NUMBER}-${ATTEMPT}"
HOST_IF="gvrh${SUFFIX}"
NS_IF="gvrn${SUFFIX}"
SUBNET="198.18.${OCTET}.0/30"
HOST_IP="198.18.${OCTET}.1"
NS_IP="198.18.${OCTET}.2"
NETNS_CONFIG="${GEOIP_VPN_NETNS_CONFIG_ROOT:-/etc/netns}/${NAMESPACE}"

EGRESS_IF=""
IPV4_FORWARD_OLD=""
NAMESPACE_CREATED=0
VETH_CREATED=0
FORWARD_OUT_CREATED=0
FORWARD_RETURN_CREATED=0
MASQUERADE_CREATED=0
CHILD_PID=""

cleanup() {
  local exit_status=$?
  local cleanup_failed=0
  local namespace_pids=""

  trap - EXIT INT TERM
  set +e
  echo "[vpn-netns] cleanup_started namespace=${NAMESPACE}"

  if [[ "$NAMESPACE_CREATED" == "1" ]]; then
    namespace_pids="$(ip netns pids "$NAMESPACE" 2>/dev/null)"
    if [[ -n "$namespace_pids" ]]; then
      while IFS= read -r pid; do
        [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null
      done <<< "$namespace_pids"
      sleep 0.2
      while IFS= read -r pid; do
        [[ -n "$pid" ]] && kill -KILL "$pid" 2>/dev/null
      done <<< "$namespace_pids"
    fi
    ip netns del "$NAMESPACE" 2>/dev/null || cleanup_failed=1
  fi

  if [[ "$VETH_CREATED" == "1" ]]; then
    ip link del "$HOST_IF" 2>/dev/null || true
  fi

  if [[ "$MASQUERADE_CREATED" == "1" ]]; then
    iptables -t nat -D POSTROUTING -s "$SUBNET" -o "$EGRESS_IF" -j MASQUERADE || cleanup_failed=1
  fi
  if [[ "$FORWARD_OUT_CREATED" == "1" ]]; then
    iptables -D FORWARD -i "$HOST_IF" -o "$EGRESS_IF" -s "$SUBNET" -j ACCEPT || cleanup_failed=1
  fi
  if [[ "$FORWARD_RETURN_CREATED" == "1" ]]; then
    iptables -D FORWARD -i "$EGRESS_IF" -o "$HOST_IF" -d "$SUBNET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || cleanup_failed=1
  fi

  if [[ -n "$IPV4_FORWARD_OLD" ]]; then
    sysctl -w "net.ipv4.ip_forward=$IPV4_FORWARD_OLD" >/dev/null || cleanup_failed=1
  fi

  rm -rf "$NETNS_CONFIG"
  echo "[vpn-netns] cleanup_completed namespace=${NAMESPACE} host_firewall_restored=true route_scope=namespace cleanup_failed=${cleanup_failed}"

  if [[ "$cleanup_failed" == "1" && "$exit_status" == "0" ]]; then
    exit_status=1
  fi
  exit "$exit_status"
}

forward_signal() {
  local sig="$1"
  local code="$2"
  if [[ -n "$CHILD_PID" ]]; then
    echo "[vpn-netns] child_signal_forwarded signal=${sig} pid=${CHILD_PID}"
    kill "-${sig}" "$CHILD_PID" 2>/dev/null || true
    # The child (GNU timeout -> Python -> report finally) must finish before
    # EXIT cleanup removes the namespace and its resolver configuration.
    wait "$CHILD_PID" 2>/dev/null || true
    echo "[vpn-netns] child_exit_observed_after_signal=true"
  fi
  exit "$code"
}

trap cleanup EXIT
trap 'forward_signal INT 130' INT
trap 'forward_signal TERM 143' TERM

ROUTE="$(ip -4 route get 1.1.1.1)"
EGRESS_IF="$(awk '{ for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit } }' <<< "$ROUTE")"
if [[ -z "$EGRESS_IF" ]]; then
  echo "[vpn-netns] unable_to_determine_host_ipv4_egress" >&2
  exit 1
fi
if ip route show "$SUBNET" | grep -q .; then
  echo "[vpn-netns] namespace_subnet_conflict subnet=$SUBNET" >&2
  exit 1
fi

IPV4_FORWARD_OLD="$(sysctl -n net.ipv4.ip_forward)"
mkdir -p "$NETNS_CONFIG"
cat > "$NETNS_CONFIG/resolv.conf" <<'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
options timeout:2 attempts:1
EOF

echo "[vpn-netns] setup_started namespace=${NAMESPACE} host_egress=${EGRESS_IF} subnet=${SUBNET}"
ip netns add "$NAMESPACE"
NAMESPACE_CREATED=1

ip link add "$HOST_IF" type veth peer name "$NS_IF"
VETH_CREATED=1
ip link set "$NS_IF" netns "$NAMESPACE"
ip address add "$HOST_IP/30" dev "$HOST_IF"
ip link set "$HOST_IF" up
ip -n "$NAMESPACE" address add "$NS_IP/30" dev "$NS_IF"
ip -n "$NAMESPACE" link set lo up
ip -n "$NAMESPACE" link set "$NS_IF" up
ip -n "$NAMESPACE" route add default via "$HOST_IP"

sysctl -w net.ipv4.ip_forward=1 >/dev/null
iptables -I FORWARD 1 -i "$HOST_IF" -o "$EGRESS_IF" -s "$SUBNET" -j ACCEPT
FORWARD_OUT_CREATED=1
iptables -I FORWARD 1 -i "$EGRESS_IF" -o "$HOST_IF" -d "$SUBNET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
FORWARD_RETURN_CREATED=1
iptables -t nat -I POSTROUTING 1 -s "$SUBNET" -o "$EGRESS_IF" -j MASQUERADE
MASQUERADE_CREATED=1

echo "[vpn-netns] setup_completed namespace=${NAMESPACE} host_output_policy_untouched=true host_default_route_untouched=true"
ip netns exec "$NAMESPACE" "$@" &
CHILD_PID=$!
wait "$CHILD_PID"
