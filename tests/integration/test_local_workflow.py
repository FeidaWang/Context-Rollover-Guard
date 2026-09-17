"""End-to-end CLI projection, estimate and advice workflow, no live runtime."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class LocalWorkflow(unittest.TestCase):
    def test_usage_quota_prediction_and_advice_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();db=root/'private/usage.sqlite'
            def run(*args):
                result=subprocess.run([sys.executable,'-m','crg',*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                return result.stdout
            def save(name,value,jsonl=False):
                path=root/name;path.write_text(json.dumps(value)+'\n');return path
            event={'source_event_id':'one','source_kind':'synthetic','source_scope':'local',
                   'observed_at':'2026-09-17T00:00:00Z','completion_state':'completed','counter_semantics':'per_event',
                   'total_tokens':64,'active_context_tokens':500000}
            feed=save('events.jsonl',event)
            run('ledger-import','--database',db,'--input',feed)
            run('ledger-import','--database',db,'--input',feed)
            usage=json.loads(run('usage','--database',db,'--scope','local','--start','2026-09-17T00:00:00Z','--end','2026-09-18T00:00:00Z'))
            self.assertEqual(usage['known_total_tokens'],64);self.assertEqual(usage['sample_count'],1)
            quota=save('quota.jsonl',{'source':'synthetic','account_fingerprint':'synthetic-account','bucket_id':'weekly',
                'source_snapshot_id':'one','observed_at':'2026-09-17T00:00:00Z','used_percent':25,'freshness_seconds':3600})
            run('quota-import','--database',db,'--input',quota)
            status=json.loads(run('quota-status','--database',db,'--account-fingerprint','synthetic-account','--bucket','weekly','--at','2026-09-17T00:00:01Z'))
            self.assertEqual(status['remaining_percent'],75);self.assertIsNone(status['tokens_remaining'])
            prediction=json.loads(run('predict','--database',db,'--task-class','docs','--model','fixture','--effort','custom','--runtime-version','v','--prediction-id','p'))
            self.assertIsNone(prediction['duration_interval_ms'])
            outcome=save('outcome.json',{'prediction_id':'p','status':'completed','duration_ms':1000,'success':True,
                'at':datetime.now(timezone.utc).isoformat()})
            run('complete-observation','--database',db,'--input',outcome)
            run('complete-observation','--database',db,'--input',outcome)
            catalog=save('catalog.json',{'status':'VERIFIED_CATALOG','observed_at':datetime.now(timezone.utc).isoformat(),
                'models':[{'id':'fixture','available':True,'reasoning_efforts':['custom']}]})
            features=save('features.json',{'is_docs_only':True})
            policy=save('policy.json',{'candidates':[{'model_id':'fixture','effort':'custom','approved_for':[],
                'cost_rank':1,'capability_rank':1}]})
            args=['advise','--catalog',catalog,'--features',features,'--policy',policy,'--database',db,'--runtime-version','v']
            advice=json.loads(run(*args));self.assertEqual(advice['selected']['model_id'],'fixture')
            self.assertEqual(advice['sample_count'],1);self.assertFalse(advice['automatic_switch'])
            rendered=run(*args,'--format','status','--estimate',save('estimate.json',prediction))
            self.assertIn('ETA: unknown',rendered);self.assertIn('samples: 0',rendered)
