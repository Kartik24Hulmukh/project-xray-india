import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.preflight_prod_env import collect


class TestRehearsal(unittest.TestCase):
    def test_preflight_passes_with_rehearsal_env(self):
        from scripts.preflight_prod_env import rehearsal_env_template
        env = rehearsal_env_template()
        report = collect(env)
        self.assertEqual(report['status'], 'ok')
        self.assertTrue(all(item['ok'] for item in report['checks']))

    def test_rehearsal_script_runs(self):
        result = subprocess.run(
            [sys.executable, 'scripts/rehearse_production.py'],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['project_status'], 'published')
        self.assertEqual(payload['claim_publication_state'], 'published')
        self.assertGreaterEqual(payload['monitor_event_count'], 1)
        self.assertTrue((ROOT / 'artifacts' / 'prod-rehearsal' / 'receipt.json').exists())
        self.assertTrue((ROOT / 'artifacts' / 'prod-rehearsal' / 'preflight.json').exists())
        self.assertTrue((ROOT / 'artifacts' / 'prod-rehearsal' / 'recovery-evidence.json').exists())


if __name__ == '__main__':
    unittest.main()
