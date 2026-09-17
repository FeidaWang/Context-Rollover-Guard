import unittest
from crg.timing import summarize, union_ms


def milestone(kind,ms,process='p'):
    return {'id':kind,'kind':kind,'monotonic_ms':ms,'process_id':process,'at':'2026-09-17T00:00:00Z'}


class TimingTests(unittest.TestCase):
    def test_union_pauses_clock_rollback_and_replay(self):
        events=[milestone('submit',0),milestone('completed',100)]
        events[1]['at']='2025-01-01T00:00:00Z'
        result=summarize(events+events,approval_intervals=[(10,30),(20,40)],tool_intervals=[(40,80),(50,90)])
        self.assertEqual((result['wall_ms'],result['active_ms'],result['tool_union_ms']),(100,70,50))
        self.assertIsNone(result['accepted'])

    def test_restart_censoring_and_unknown_wait(self):
        result=summarize([milestone('submit',0),milestone('completed',100,'new')])
        self.assertIsNone(result['wall_ms'])
        result=summarize([milestone('submit',0),milestone('cancelled',10000)])
        self.assertTrue(result['censored']);self.assertIsNone(result['active_ms'])
        self.assertEqual(result['wall_ms'],10000)

    def test_no_self_rating_or_unrun_test_pass(self):
        events=[milestone('submit',0),milestone('completed',100)]
        for source,observed in [('model',True),('executed_tests',False)]:
            with self.assertRaises(ValueError):
                summarize(events,acceptance=dict(source=source,observed=observed,accepted=True,monotonic_ms=120,process_id='p'))
        self.assertFalse(summarize(events,acceptance=dict(source='maintainer',observed=True,accepted=False,monotonic_ms=120,process_id='p'))['accepted'])
