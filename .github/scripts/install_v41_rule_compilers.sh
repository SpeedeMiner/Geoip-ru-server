#!/usr/bin/env bash
# Source from v41 jobs. Each tool is pinned to an official release archive.

v41_fetch_compiler() {
  local url="$1" archive="$2" digest="$3"
  curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --retry 3 --connect-timeout 15 --max-time 120 --max-filesize 30000000 \
    --output "$archive" "$url" || return
  printf '%s  %s\n' "$digest" "$archive" | sha256sum -c -
}

install_v41_sing_box() {
  local dest="$1" version=1.13.12 archive
  archive="sing-box-${version}-linux-amd64.tar.gz"
  v41_fetch_compiler "https://github.com/SagerNet/sing-box/releases/download/v${version}/$archive" \
    "$dest/$archive" 1540533adb3df24f5ad5f14b5c7ca3dbc2401b10a1c1eb278fcadcada47ec6c4 || return
  tar -xOzf "$dest/$archive" "sing-box-${version}-linux-amd64/sing-box" > "$dest/sing-box" || return
  chmod 0755 "$dest/sing-box"
}

install_v41_mihomo() {
  local dest="$1" version=v1.19.34 archive
  archive="mihomo-linux-amd64-compatible-${version}.gz"
  v41_fetch_compiler "https://github.com/MetaCubeX/mihomo/releases/download/${version}/$archive" \
    "$dest/$archive" 2763f5b414527f7baf6dc57e3f82f3ab561eedf34bfd7c2f2cde1f7e592efe06 || return
  gzip -dc "$dest/$archive" > "$dest/mihomo" || return
  chmod 0755 "$dest/mihomo"
}
