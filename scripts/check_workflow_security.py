#!/usr/bin/env python3
"""Static fail-closed policy for GitHub Actions workflows.

Enforces:
  - all `uses:` actions pinned to full 40-char SHAs
  - no eval, || true, continue-on-error: true, :latest, or apply/destroy/import
  - no literal AWS credentials
  - deploy.yml contains required hardening tokens
  - infra-plan.yml:
      * no pull_request_target trigger
      * id-token: write exists only on speculative-plan (not tofu-validate)
      * tofu-validate job exists and has no id-token permission
      * speculative-plan is gated on AWS_BOOTSTRAPPED == 'true'
      * no apply/destroy/import commands
      * no binary plan artifact upload
"""
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github/workflows'
FULL_SHA = re.compile(r'^[0-9a-f]{40}$')
FORBIDDEN = (
    'eval ',
    '|| true',
    'continue-on-error: true',
    'tofu apply',
    'terraform apply',
    'tofu destroy',
    'terraform destroy',
    'tofu import',
    'terraform import',
    ':latest',
)


def main():
    errors = []
    files = sorted(WF.glob('*.yml')) + sorted(WF.glob('*.yaml'))

    for path in files:
        text = path.read_text()
        low = text.lower()

        # Check all action references are pinned to full SHAs
        for line_no, line in enumerate(text.splitlines(), 1):
            match = re.search(r'\buses:\s*([^\s#]+)', line)
            if match:
                value = match.group(1)
                if '@' not in value or not FULL_SHA.fullmatch(value.rsplit('@', 1)[1]):
                    errors.append(f'{path.name}:{line_no}: action not pinned to a full SHA: {value}')

        # Check for forbidden tokens
        for token in FORBIDDEN:
            if token in low:
                errors.append(f'{path.name}: forbidden token: {token}')

        # Check for literal AWS credentials
        if re.search(r'(?im)^\s*aws_(access_key_id|secret_access_key):\s*[A-Za-z0-9/+]{8,}\s*$', text):
            errors.append(f'{path.name}: literal AWS credential detected')

    if not files:
        errors.append('no workflows found')

    # deploy.yml hardening checks
    deploy = (WF / 'deploy.yml').read_text() if (WF / 'deploy.yml').exists() else ''
    for token in ('image_digest', 'git_sha', 'services-stable', 'imageDigest', 'id-token: write', 'environment:'):
        if token not in deploy:
            errors.append('deploy.yml missing ' + token)

    # infra-plan.yml contract checks
    plan_path = WF / 'infra-plan.yml'
    if plan_path.exists():
        plan = plan_path.read_text()

        if 'pull_request_target' in plan:
            errors.append('infra plan must not use pull_request_target')

        # tofu-validate job must exist
        if 'tofu-validate:' not in plan and 'name: tofu-validate' not in plan:
            errors.append('infra-plan.yml: missing tofu-validate job')

        # Extract job blocks to check permissions per-job
        # Simple approach: check that id-token: write does not appear in the
        # tofu-validate section and that speculative-plan has it
        job_blocks = re.split(r'^  (\S+):\s*$', plan, flags=re.MULTILINE)
        # job_blocks: ['header', 'job1name', 'job1body', 'job2name', 'job2body', ...]
        job_map = {}
        for i in range(1, len(job_blocks) - 1, 2):
            job_name = job_blocks[i]
            job_body = job_blocks[i + 1]
            job_map[job_name] = job_body

        # Check tofu-validate has no id-token permission
        tofu_body = job_map.get('tofu-validate', '')
        if tofu_body:
            if 'id-token: write' in tofu_body:
                errors.append('infra-plan.yml: tofu-validate must not have id-token: write')
            if 'id-token:' in tofu_body:
                errors.append('infra-plan.yml: tofu-validate must not declare id-token permission')
        else:
            errors.append('infra-plan.yml: tofu-validate job block not found')

        # Check speculative-plan has id-token: write
        spec_body = job_map.get('speculative-plan', '')
        if spec_body:
            if 'id-token: write' not in spec_body:
                errors.append('infra-plan.yml: speculative-plan must have id-token: write')
            # Check AWS_BOOTSTRAPPED gate
            if 'AWS_BOOTSTRAPPED' not in spec_body:
                errors.append('infra-plan.yml: speculative-plan must reference AWS_BOOTSTRAPPED')
            if '"true"' not in spec_body and "'true'" not in spec_body:
                errors.append('infra-plan.yml: speculative-plan must check AWS_BOOTSTRAPPED == true')
        else:
            errors.append('infra-plan.yml: speculative-plan job block not found')

        # No binary plan artifact upload in infra-plan
        if 'upload-artifact' in plan and '.tfplan' in plan:
            errors.append('infra-plan.yml: must not upload binary plan artifacts')

        # No apply/destroy/import (already checked via FORBIDDEN but double-check)
        for cmd in ('tofu apply', 'terraform apply', 'tofu destroy', 'terraform destroy', 'tofu import', 'terraform import'):
            if cmd in plan.lower():
                errors.append(f'infra-plan.yml: forbidden command: {cmd}')

    result = {
        'status': 'error' if errors else 'ok',
        'workflows': len(files),
        'errors': errors,
    }
    print(json.dumps(result, sort_keys=True))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
