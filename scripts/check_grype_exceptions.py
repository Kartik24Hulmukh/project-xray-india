#!/usr/bin/env python3
"""CI guard for Grype exception file.

Fails if:
  - any expiry date is in the past
  - more than three CVE IDs are present without explicit review
  - any ignored CVE is not in the approved set

Approved CVE set: CVE-2026-11940, CVE-2026-15308, CVE-2026-11972
Expiry: 2026-08-18
"""
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

EXCEPTIONS_FILE = Path("security/grype-exceptions.yaml")
MAX_CVES = 3
APPROVED_CVES = {"CVE-2026-11940", "CVE-2026-15308", "CVE-2026-11972"}
EXPIRY_DATE = datetime(2026, 8, 18, 23, 59, 59, tzinfo=timezone.utc)

def main():
    if not EXCEPTIONS_FILE.exists():
        print("OK: no grype exception file found")
        return 0

    text = EXCEPTIONS_FILE.read_text()

    # Extract all CVE IDs from the file
    cves = set(re.findall(r'CVE-\d{4}-\d+', text))

    # Check count
    if len(cves) > MAX_CVES:
        print(f"FAIL: exception file contains {len(cves)} CVE IDs, max allowed is {MAX_CVES}")
        print(f"  CVEs: {sorted(cves)}")
        print("  Additional CVEs require explicit human review and a new expiry date.")
        return 1

    # Check all CVEs are in the approved set
    unapproved = cves - APPROVED_CVES
    if unapproved:
        print(f"FAIL: exception file contains unapproved CVE IDs: {sorted(unapproved)}")
        print(f"  Approved set: {sorted(APPROVED_CVES)}")
        return 1

    # Check expiry date
    now = datetime.now(timezone.utc)
    if now > EXPIRY_DATE:
        print(f"FAIL: exception expiry date {EXPIRY_DATE.isoformat()} has passed")
        print("  Rebuild and rescan with a fixed Python image, or renew the risk acceptance.")
        return 1

    days_remaining = (EXPIRY_DATE - now).days
    print(f"OK: {len(cves)} accepted CVEs, expiry in {days_remaining} days ({EXPIRY_DATE.date()})")
    print(f"  CVEs: {sorted(cves)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
