"""CLI import/status/export and pre-execution forecast end to end, offline."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.unit.test_events import usage
from tests.unit.test_features import POLICY,INTENT


class AnalyticsWorkflow(unittest.TestCase):
    def call(self,*args):
        result=subprocess.run([sys.executable,'-m','crg',*map(str,args)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        return json.loads(result.stdout)

    def test_import_export_forecast_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'source.jsonl';db=root/'private/db'
            source.write_text('\n'.join(json.dumps(usage(i,total)) for i,total in [(1,100),(2,130)])+'\n')
            command=('analytics-import','--database',db,'--input',source,'--authorized-root',root,'--session','s','--runtime-version','synthetic')
            self.assertEqual(self.call(*command)['records'],2);self.assertEqual(self.call(*command)['records'],0)
            panel=self.call('analytics-status','--database',db,'--at','2026-09-18T00:00:00Z')
            self.assertEqual(panel['usage']['local']['known_total_tokens'],30)
            preview=self.call('export-preview','--database',db);preview_path=root/'preview.json';preview_path.write_text(json.dumps(preview))
            result=self.call('export-write','--preview',preview_path,'--output',root/'private/export.json','--approved-sha256',preview['sha256'])
            self.assertFalse(result['uploaded'])
            ip=root/'intent.json';pp=root/'policy.json';ip.write_text(json.dumps(INTENT));pp.write_text(json.dumps(POLICY))
            prediction=self.call('forecast-next','--database',db,'--intent',ip,'--policy',pp,'--at','2026-09-18T00:00:00Z')
            self.assertIsNone(prediction['interval'])
            outcome=root/'outcome.json';outcome.write_text(json.dumps(dict(ident=prediction['id'],at='2026-09-18T00:00:01Z',status='completed',value=1000)))
            self.assertTrue(self.call('forecast-outcome','--database',db,'--input',outcome)['recorded'])
