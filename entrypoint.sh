#!/bin/sh
# Run as the unprivileged `appuser`. Volumes (Railway, docker bind mounts and
# named volumes) are usually mounted root-owned, so fix that first while we
# still can, then drop privileges for good.
set -e
DATA_DIR="$(dirname "${DB_PATH:-data/followers.db}")"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown -R appuser:appuser "$DATA_DIR"
    exec setpriv --reuid=appuser --regid=appuser --init-groups "$@"
fi
exec "$@"
