from pathlib import Path
import tempfile,unittest
from crg.ledger import Ledger

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ledger=Ledger(Path(self.temp.name).resolve()/'private/ledger.sqlite');self.addCleanup(self.ledger.close)
    def event(self,i,total,**kw):
        return dict(source_event_id=str(i),source_kind='fixture',source_scope='local',
            observed_at=f'2026-09-17T00:00:0{i}+00:00',completion_state='completed',
            counter_semantics='cumulative',total_tokens=total,active_context_tokens=500000,**kw)
    def test_dedup_deltas_and_resets(self):
        for e in [self.event(1,100),self.event(2,150),self.event(2,150),self.event(3,20),self.event(4,30)]:self.ledger.add(e)
        result=self.ledger.usage('local','2026-09-17T00:00:00Z','2026-09-18T00:00:00Z')
        self.assertEqual(result['known_total_tokens'],60);self.assertEqual(result['sample_count'],4)
        self.assertEqual(result['unknown_samples'],2)
    def test_conflict_order_privacy_and_unknown(self):
        self.ledger.add(self.event(2,150))
        for event in [self.event(2,151),self.event(1,100),self.event(3,100)|{'prompt':'private'}]:
            with self.assertRaises(ValueError):self.ledger.add(event)
        result=self.ledger.usage('absent','2026-09-17T00:00:00Z','2026-09-18T00:00:00Z')
        self.assertIsNone(result['known_total_tokens'])
    def test_accounts_have_independent_baselines(self):
        self.ledger.add(self.event(1,100,account_fingerprint='a'))
        self.ledger.add(self.event(2,200,account_fingerprint='b'))
        self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM ledger_event WHERE total_tokens IS NULL').fetchone()[0],2)

    def test_concurrent_duplicate_writers_and_future_schema(self):
        from concurrent.futures import ThreadPoolExecutor
        path=Path(self.temp.name).resolve()/'private/ledger.sqlite'
        def write(_):
            ledger=Ledger(path)
            try:return ledger.add(self.event(1,100)|{'counter_semantics':'per_event'})
            finally:ledger.close()
        with ThreadPoolExecutor(4) as pool:identities=list(pool.map(write,range(8)))
        self.assertEqual(len(set(identities)),1)
        self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM ledger_event').fetchone()[0],1)
        self.ledger.db.execute('PRAGMA user_version=99')
        with self.assertRaises(ValueError):Ledger(path)
