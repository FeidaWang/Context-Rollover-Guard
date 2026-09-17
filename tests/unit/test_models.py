import unittest
from crg.models import normalize_model, discover_models

class Models(unittest.TestCase):
    def test_no_name_inference(self):
        model = normalize_model({'id':'future-ultra-million'}, observed_at='fixture')
        self.assertIsNone(model.context_window)
        self.assertEqual(model.reasoning_efforts, ())
        self.assertIsNone(model.family)
    def test_projection(self):
        model = normalize_model({'id':'m','available':False,'contextWindow':True,
            'supportedReasoningEfforts':[{'reasoningEffort':'custom'},'low'],'serviceTiers':[{'id':'batch'}]}, observed_at='fixture')
        self.assertFalse(model.available);self.assertIsNone(model.context_window)
        self.assertEqual(model.reasoning_efforts, ('custom','low'))
        self.assertEqual(model.service_tiers,('batch',))
    def test_catalog_pages_and_drift(self):
        class Schema:
            methods={'model/list':{}}
            def validate_action(self,*args):pass
        pages=iter([{'data':[{'id':'a'}],'nextCursor':'next'},{'data':[{'id':'b'}],'nextCursor':None}])
        result=discover_models(lambda *args:next(pages),Schema())
        self.assertEqual(result['status'],'VERIFIED_CATALOG');self.assertEqual(len(result['models']),2)
        result=discover_models(lambda *args:{'data':[{'id':'a'}],'nextCursor':'same'},Schema())
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['models'],[])
    def test_unknown_method_never_calls_runtime(self):
        class Schema:methods={}
        self.assertEqual(discover_models(lambda *a: self.fail(),Schema())['status'],'UNKNOWN')
