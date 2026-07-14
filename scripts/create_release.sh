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
git bundle create "artifacts/release/project-xray-india-${version}.bundle" --all
cp artifacts/sbom.cdx.json artifacts/release/
cat > artifacts/release/GUMLOOP_HANDOFF.md <<EOF
# Gumloop handoff for v${version}

## Repo state
- Commit: ${commit}
- Version: ${version}
- Release verification: passed
- Production rehearsal: passed

## Included artifacts
- project-xray-india-${version}.zip
- project-xray-india-${version}.bundle
- sbom.cdx.json
- build-provenance.json
- prod-rehearsal/preflight.json
- prod-rehearsal/capsule.json
- prod-rehearsal/recovery-evidence.json
- prod-rehearsal/receipt.json

## What changed in this checkpoint
- Added production preflight validation for prod-required configuration.
- Added provider-neutral production rehearsal covering signed OIDC proxy auth, managed-storage verification, alert delivery, public publication, capsule verification, and recovery evidence.
- Integrated rehearsal receipts into release verification and packaging.

## Remaining honest blockers
- Managed PostgreSQL provider selection and non-SQLite migration
- Live staging/runtime access
- Real OIDC/MFA tenant and gateway
- Real object storage / IAM / bucket lifecycle
- Real monitoring recipient / on-call evidence
- Real destructive restore drill in target environment
- Governance, legal/editorial approvals, and launch-partner evidence
EOF
(
 cd artifacts/release
 sha256sum project-xray-india-${version}.zip project-xray-india-${version}.bundle sbom.cdx.json GUMLOOP_HANDOFF.md prod-rehearsal/preflight.json prod-rehearsal/capsule.json prod-rehearsal/recovery-evidence.json prod-rehearsal/receipt.json > SHA256SUMS.txt
 printf '{"version":"%s","commit":"%s","tests":"passed","smoke":"passed","production_rehearsal":"passed","bundle":"present"}\n' "$version" "$commit" > build-provenance.json
)
echo "Release artifacts created for ${version} at commit ${commit}"
