# Explicit client allowlists. Only the RU MRS sidecar is mirrored to CDN.
readonly -a V41_LEGACY_CDN_FILES=(geoip_RU.dat geoip_RU.srs geoip_PRIVATE.srs)
readonly -a V41_CLIENT_BINARIES=(geoip_RU.dat geoip_RU.srs geoip_PRIVATE.srs geoip_RU.mrs)
readonly -a V41_CLIENT_ASSETS=(geoip_RU.dat geoip_RU.dat.sha256sum geoip_RU.srs geoip_RU.srs.sha256sum geoip_PRIVATE.srs geoip_PRIVATE.srs.sha256sum geoip_RU.mrs geoip_RU.mrs.sha256sum)
readonly -a V41_CDN_FILES=(geoip_RU.dat geoip_RU.srs geoip_PRIVATE.srs geoip_RU.mrs geoip_RU.mrs.sha256sum)
