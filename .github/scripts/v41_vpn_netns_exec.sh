#!/usr/bin/env bash
# A disposable namespace and userspace NAT: no host IP forwarding or iptables changes.
set -euo pipefail
if [[ $# -lt 2 || "$1" != -- || "$(id -u)" != 0 ]]; then
  echo "usage (root, isolated runner): v41_vpn_netns_exec.sh -- COMMAND [ARG ...]" >&2
  exit 2
fi
shift

for command_name in ip slirp4netns mktemp; do
  command -v "$command_name" >/dev/null || exit 2
done
runtime="$(mktemp -d /run/v41-vpn-XXXXXXXX)"
ns="${runtime##*/}"
config="/etc/netns/$ns"
created=0
config_created=0
slirp_pid=""
probe_pid=""
cleanup() {
  local rc=$? pids=""
  trap - EXIT
  trap '' INT TERM
  set +e
  if (( created )) || [[ -e "/run/netns/$ns" ]]; then
    created=1
    pids="$(ip netns pids "$ns" 2>/dev/null)" || rc=1
    if [[ -n "$pids" ]]; then
      while read -r pid; do
        [[ "$pid" =~ ^[1-9][0-9]+$ ]] && kill -TERM "$pid" 2>/dev/null
      done <<< "$pids"
      sleep 0.2
      while read -r pid; do
        [[ "$pid" =~ ^[1-9][0-9]+$ ]] && kill -KILL "$pid" 2>/dev/null
      done <<< "$pids"
    fi
  fi
  if [[ -n "$probe_pid" ]]; then
    if jobs -pr | grep -Fxq -- "$probe_pid"; then
      kill -TERM "$probe_pid" 2>/dev/null || true
      sleep 0.2
      kill -KILL "$probe_pid" 2>/dev/null || true
    fi
    wait "$probe_pid" 2>/dev/null
  fi
  if [[ -n "$slirp_pid" ]]; then
    kill -TERM "$slirp_pid" 2>/dev/null || true
    sleep 0.1
    kill -KILL "$slirp_pid" 2>/dev/null || true
    # slirp is also tied to this shell by --exit-fd=0.
    wait "$slirp_pid" 2>/dev/null || true
  fi
  if (( created )); then
    ip netns del "$ns" || rc=1
  fi
  if (( config_created )) || [[ -d "$config" ]]; then
    rm -rf -- "$config" || rc=1
  fi
  rm -rf -- "$runtime" || rc=1
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

ip netns add "$ns"
created=1
mkdir -m 700 -- "$config"
config_created=1
printf '%s\n' 'nameserver 1.1.1.1' 'nameserver 8.8.8.8' 'options timeout:2 attempts:1' > "$config/resolv.conf"
coproc V41_SLIRP {
  exec slirp4netns --configure --disable-host-loopback --netns-type=path \
    --ready-fd=3 --exit-fd=0 "/run/netns/$ns" tap0 3>&1 >/dev/null 2>&1
}
slirp_pid="$V41_SLIRP_PID"
if ! IFS= read -r -N 1 -t 12 -u "${V41_SLIRP[0]}" ready || [[ "$ready" != 1 ]]; then
  echo "v41 exact VPN: userspace network failed to initialize" >&2
  exit 2
fi
ip netns exec "$ns" env "V41_ISOLATED_NAMESPACE=$ns" "$@" &
probe_pid=$!
wait "$probe_pid"
