from concurrent.futures import ThreadPoolExecutor
import unittest
from crg.presentation import RefreshCache,status,human


class PresentationTests(unittest.TestCase):
    def test_unknown_and_partial(self):
        value=status({'known_total_tokens':None,'coverage':'partial'})
        self.assertIn('UNKNOWN',human(value));self.assertEqual(value['schema_version'],1)
        self.assertFalse(value['background_polling']);self.assertIsNone(value['quota']['remaining_percent'])

    def test_coalescing_and_invalidation(self):
        clock=[0];calls=[];cache=RefreshCache(clock=lambda:clock[0])
        def read():calls.append(1);return {'n':len(calls)}
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _:cache.get('a',read,refresh=True,event_id='turn'),range(10)))
        self.assertEqual(len(calls),1)
        clock[0]=70;self.assertEqual(cache.get('a',read,event_id='turn')['age_seconds'],70)
        cache.get('b',read);cache.invalidate('a');cache.get('a',read)
        self.assertEqual(len(calls),3)
