import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class StatisticalWorkflow(unittest.TestCase):
    def test_offline_audit_and_model_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = Path(tmp)/'observations.jsonl'
            rows.write_text('')
            completed = subprocess.run([sys.executable, '-m', 'crg', 'statistical-audit',
                '--input', str(rows), '--split-at', '2026-01-01T00:00:00Z'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(json.loads(completed.stdout)['production_ready'])
            catalog = Path(tmp)/'catalog.json'
            catalog.write_text(json.dumps({'status':'VERIFIED_CATALOG','observed_at':'2026-01-01T00:00:00Z',
                'models':[{'id':'fixture-new-id', 'available':True, 'reasoning_efforts':['custom']}]}))
            command = [sys.executable, '-m', 'crg', 'resolve-model', '--catalog', str(catalog),
                '--model','fixture-new-id','--effort','custom','--at','2026-01-01T00:00:00Z']
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['status'], 'RESOLVED')
            completed = subprocess.run(command+['--expected-revision','changed'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2)
            rows.write_text('{"chosen":false}\n')
            completed = subprocess.run([sys.executable, '-m', 'crg', 'statistical-audit',
                '--input',str(rows),'--split-at','2026-01-01T00:00:00Z'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(json.loads(completed.stdout)['production_enabled'])
