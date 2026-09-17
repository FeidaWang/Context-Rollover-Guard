import hashlib
import unittest
from crg.advice_render import presentation
from crg.features import features
from tests.unit.test_features import POLICY,INTENT


class AdviceRenderTests(unittest.TestCase):
    def test_exact_bytes_protocol_and_changed_intent(self):
        raw=b'{"conclusion":"``` conclusion ```"}\r\n# Conclusion\n# Conclusion'
        snapshot=features(INTENT,POLICY,at='2026-01-01T00:00:00Z')
        forecast=snapshot|{'target':'wall_ms','interval':[60000,120000],'status':'EMPIRICAL'}
        for protocol in ('json','markdown','owned_blocks'):
            result=presentation(raw,{'selected':{'model_id':'fixture-model','effort':'high'}},forecast,snapshot,at='2026-01-01T00:00:01Z',protocol=protocol)
            self.assertEqual(result['raw_sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(result['raw_answer'],raw)
            self.assertEqual(result['additional_model_calls'],0)
            self.assertIn('1.0–2.0',result['status_line'])
        changed=features(INTENT|{'kind':'docs'},POLICY,at='2026-01-01T00:00:00Z')
        self.assertIn('未校准',presentation(raw,{},forecast,changed,at='2026-01-01T00:00:01Z')['status_line'])

    def test_different_selected_model_suppresses_eta(self):
        snapshot=features(INTENT,POLICY,at='2026-01-01T00:00:00Z')
        forecast=snapshot|{'target':'wall_ms','interval':[60000,120000],'status':'EMPIRICAL'}
        result=presentation(b'exact',{'selected':{'model_id':'different','effort':'high'}},forecast,snapshot,at='2026-01-01T00:00:01Z')
        self.assertIn('未校准',result['status_line'])
