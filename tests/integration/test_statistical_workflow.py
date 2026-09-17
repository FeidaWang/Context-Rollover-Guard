import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.support.model_registry import contract
from crg.domain import now

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
            schema,binding,params=contract(Path(tmp).resolve())
            for name,value in [('binding',binding),('params',params)]:
                (Path(tmp)/(name+'.json')).write_text(json.dumps(value))
            catalog = Path(tmp)/'catalog.json'
            observed_at=now()
            catalog.write_text(json.dumps({'status':'VERIFIED_CATALOG','observed_at':observed_at,'binding':binding,
                'models':[{'id':'fixture-new-id', 'available':True, 'reasoning_efforts':['custom']}]}))
            command = [sys.executable, '-m', 'crg', 'resolve-model', '--catalog', str(catalog),
                '--model','fixture-new-id','--effort','custom','--at',observed_at]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['reason'], 'CURRENT_EXECUTION_CONTRACT_REQUIRED')
            command += ['--schema',str(schema.schema_root),'--binding',str(Path(tmp)/'binding.json'),
                        '--authorized-params',str(Path(tmp)/'params.json'),'--permission-profile',':read-only']
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
