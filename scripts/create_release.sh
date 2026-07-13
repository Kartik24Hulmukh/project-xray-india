#!/bin/sh
set -eu
python3 scripts/check_release.py
version=${1:-v0.1.0}
mkdir -p dist
find . -type f ! -path './.git/*' ! -path './dist/*' ! -path './data/*.db' -print | sort | tar -czf "dist/project-xray-india-${version}.tar.gz" -T -
sha256sum "dist/project-xray-india-${version}.tar.gz" > "dist/project-xray-india-${version}.sha256"
echo "Created dist/project-xray-india-${version}.tar.gz"
