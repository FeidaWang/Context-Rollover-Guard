from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from tests.unit.test_observe import token,complete


class OfflineCli(unittest.TestCase):
    def test_multiturn_replay_and_status(self):
        project=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();workspace=root/'workspace';workspace.mkdir()
            feed=root/'events.jsonl'
            events=[]
            for turn,active in [('one',10000),('two',20000),('three',235000)]:
                events.extend([token(turn,active),complete(turn)])
            events.append({'method':'thread/compacted','params':{'threadId':'thread','turnId':'three'}})
            events.extend([token('four',30000),complete('four')])
            feed.write_text(''.join(json.dumps(e)+'\n' for e in events))
            common=['--workspace',str(workspace),'--session','session','--state-root',str(root/'state')]
            run=subprocess.run([sys.executable,'-m','crg','observe',*common,'--thread','thread',
                '--input',str(feed),'--scope','total'],cwd=project,capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            output=[json.loads(line) for line in run.stdout.splitlines()]
            self.assertTrue(all(item['state']=='NORMAL' for item in output))
            self.assertTrue(all(item['production_action'] is None for item in output))
            status=subprocess.run([sys.executable,'-m','crg','status',*common],cwd=project,
                                   capture_output=True,text=True,timeout=10)
            self.assertEqual(status.returncode,0,status.stdout+status.stderr)
            state=json.loads(status.stdout)
            self.assertEqual(state['last_active_context_tokens'],30000)
            self.assertEqual(state['telemetry']['positive_deltas'],[])
            self.assertEqual(len(state['telemetry']['samples']),4)
            self.assertFalse((workspace/'.codex/hooks.json').exists())

    def test_bad_input_returns_controlled_error(self):
        project=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            run=subprocess.run([sys.executable,'-m','crg','observe','--workspace',str(root),
                '--session','s','--thread','t','--state-root',str(root/'state')],
                input='{broken\n',cwd=project,capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,1)
            self.assertIn('error',json.loads(run.stdout))
            self.assertNotIn('Traceback',run.stderr)
