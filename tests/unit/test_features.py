import unittest
from crg.features import features,matches

POLICY=dict(model_id='fixture-model',effort='high',runtime_version='synthetic-v1',service_tier='standard',execution_mode='single_agent',tool_family='shell')
INTENT=dict(task_id='task',confirmed=True,kind='code',risk='medium',files=['src/a.py'],acceptance=['offline test'],description='inert description',input_bytes=10,headroom_tokens=100,retry_count=0)


class FeaturesTests(unittest.TestCase):
    def test_unknown_and_no_prose(self):
        self.assertEqual(features(None,POLICY,at='2026-01-01T00:00:00Z')['status'],'NEXT_TASK_UNKNOWN')
        row=features(INTENT|{'description':'$(never execute) private'},POLICY,at='2026-01-01T00:00:00Z')
        self.assertNotIn('private',str(row));self.assertNotIn('src/a.py',str(row))

    def test_changed_intent_invalidates(self):
        a=features(INTENT,POLICY,at='2026-01-01T00:00:00Z')
        for change in ({'kind':'docs'},{'files':['b']},{'acceptance':['new']}):
            self.assertFalse(matches(a,features(INTENT|change,POLICY,at='2026-01-01T00:00:00Z')))
