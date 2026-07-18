#!/usr/bin/env python3
"""External evaluator for Project X-Ray India synthetic preview.

This script checks local package invariants and optionally probes a running
base URL for health and synthetic markers. It never claims production readiness.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = [
    "docs/KNOWN_LIMITATIONS.md",
    "docs/launch/POSITIONING.md",
    "docs/launch/GO_NO_GO.md",
    "docs/launch/STAKEHOLDER_REACTION_MATRIX.md",
    "docs/legal/DISCLAIMER.md",
    "docs/ops/KILL_SWITCH_RUNBOOK.md",
    "docs/metrics/TRACTION_DEFINITIONS.md",
    "ops/production-readiness.yaml",
    "ops/preview/monday-go-no-go.yaml",
]
FORBIDDEN_PHRASES_IN_POSITIONING = [
    "corruption detector",
    "guilt engine",
    "truth engine",
]


def check_docs() -> list[dict]:
    findings = []
    for rel in REQUIRED_DOCS:
        path = ROOT / rel
        ok = path.is_file() and path.stat().st_size > 0
        findings.append({"check": f"doc:{rel}", "pass": ok})
    positioning = (ROOT / "docs/launch/POSITIONING.md").read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES_IN_POSITIONING:
        findings.append(
            {
                "check": f"forbidden_phrase_absent:{phrase}",
                "pass": phrase not in positioning,
            }
        )
    readiness = (ROOT / "ops/production-readiness.yaml").read_text(encoding="utf-8")
    findings.append(
        {
            "check": "readiness_label_not_v1_production",
            "pass": "release_label: alpha" in readiness
            or "controlled_synthetic_preview" in readiness,
        }
    )
    sample = (ROOT / "scripts/fixtures/synthetic_evaluator_corpus/project.json").read_text(
        encoding="utf-8"
    )
    findings.append({"check": "synthetic_fixture_marked", "pass": "SYNTHETIC" in sample})
    return findings


def check_base_url(base_url: str) -> list[dict]:
    findings = []
    url = base_url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - operator-provided URL
            body = resp.read().decode("utf-8", errors="replace")
            findings.append(
                {
                    "check": "health_http",
                    "pass": 200 <= resp.status < 300,
                    "status": resp.status,
                    "body_preview": body[:200],
                }
            )
    except Exception as exc:  # noqa: BLE001 - evaluator should capture all probe failures
        findings.append({"check": "health_http", "pass": False, "error": str(exc)})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--out", default=str(ROOT / "artifacts/preview/external-evaluator.json"))
    args = parser.parse_args()

    findings = check_docs()
    if args.base_url:
        findings.extend(check_base_url(args.base_url))

    failed = [f for f in findings if not f.get("pass")]
    result = {
        "mode": "controlled_synthetic_technical_preview",
        "package_root": ".",
        "passed": len(failed) == 0,
        "pass_count": sum(1 for f in findings if f.get("pass")),
        "fail_count": len(failed),
        "findings": findings,
        "notes": [
            "This evaluator does not prove production readiness.",
            "Hosted auth/storage/restore receipts remain operator gates.",
            "Do not interpret a pass as high traction or impact.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "pass_count": result["pass_count"], "fail_count": result["fail_count"], "out": str(out)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
