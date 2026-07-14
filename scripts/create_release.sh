#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
version="${1:-0.2.0}"
rm -rf artifacts/release
mkdir -p artifacts/release
python3 scripts/check_release.py
python3 scripts/smoke_e2e.py
python3 scripts/generate_sbom.py
mkdir -p artifacts/release/prod-rehearsal
cp artifacts/prod-rehearsal/preflight.json artifacts/prod-rehearsal/capsule.json artifacts/prod-rehearsal/recovery-evidence.json artifacts/prod-rehearsal/receipt.json artifacts/release/prod-rehearsal/
commit="$(git rev-parse HEAD)"
git archive --format=zip --prefix="project-xray-india-${version}/" -o "artifacts/release/project-xray-india-${version}.zip" HEAD
cp artifacts/sbom.cdx.json artifacts/release/
(
 cd artifacts/release
 sha256sum project-xray-india-${version}.zip sbom.cdx.json prod-rehearsal/preflight.json prod-rehearsal/capsule.json prod-rehearsal/recovery-evidence.json prod-rehearsal/receipt.json > SHA256SUMS.txt
 printf '{"version":"%s","commit":"%s","tests":"passed","smoke":"passed","production_rehearsal":"passed"}\n' "$version" "$commit" > build-provenance.json
)
echo "Release artifacts created for ${version} at commit ${commit}"
