"""Runtime/account-bound registry tests with synthetic schema and no live calls."""
import copy
from crg.domain import now
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from crg.models import discover_models, normalize_model, resolve_action
from crg.advisor import recommend
from tests.support.model_registry import contract


class RegistryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.schema,self.binding,self.params=contract(self.root)
        self.at=now()
        self.model=asdict(normalize_model({'id':'returned-id','displayName':'Astra',
            'supportedReasoningEfforts':['custom','Ultra'],'serviceTiers':['fixture-tier']},observed_at=self.at))
        self.catalog=dict(status='VERIFIED_CATALOG',observed_at=self.at,source='synthetic',
                          binding=self.binding,models=[self.model])

    def resolve(self, **changes):
        kwargs=dict(model_id='returned-id',effort='custom',at=self.at,schema=self.schema,
                    binding=self.binding,authorized_params=self.params,permission_profile=':read-only')
        return resolve_action(self.catalog,**(kwargs|changes))

    def test_actual_ids_and_exact_prompt_not_labels(self):
        before=copy.deepcopy(self.params)
        result=self.resolve()
        self.assertEqual(result['status'],'RESOLVED')
        self.assertEqual(result['action'],dict(model_id='returned-id',reasoning_effort='custom',
            execution_mode='single_agent',service_tier=None,permission_profile=':read-only'))
        self.assertEqual(result['wire_params'],before|{'model':'returned-id','effort':'custom'})
        self.assertEqual(self.params,before)
        self.assertEqual(self.resolve(model_id='Astra')['status'],'UNAVAILABLE')
        self.assertEqual(self.resolve(model_id='GPT-6 Sol')['status'],'UNAVAILABLE')
        self.assertFalse(result['automatic_switch'])

    def test_exact_effort_must_be_both_exposed_and_schema_valid(self):
        self.assertEqual(self.resolve(effort='Ultra')['status'],'UNAVAILABLE')
        self.assertEqual(self.resolve(effort='low')['status'],'UNAVAILABLE')
        self.model['reasoning_efforts']=[]
        self.assertEqual(self.resolve()['reason'],'EFFORT_NOT_EXPOSED')

    def test_scope_changes_never_use_cached_catalog(self):
        for key in ('account_scope_id','auth_mode','client_surface','execution_runtime_version','binary_sha256','schema_sha256'):
            changed=self.binding|{key:'different'}
            with self.subTest(key=key):
                self.assertEqual(self.resolve(binding=changed)['status'],'UNAVAILABLE')
        for kwargs in ({'schema':None},{'binding':None},{'authorized_params':None}):
            self.assertEqual(self.resolve(**kwargs)['reason'],'CURRENT_EXECUTION_CONTRACT_REQUIRED')

    def test_missing_hidden_and_migration_hints(self):
        model=normalize_model({'id':'old','hidden':True,'upgrade':'new','displayName':'Sol',
            'newServerField':{'network':True,'agents':99}},observed_at=self.at)
        self.assertFalse(model.available)
        self.assertEqual(model.migration_hint,'new')
        self.catalog['models']=[asdict(model)]
        self.assertEqual(self.resolve(model_id='old')['status'],'UNAVAILABLE')
        self.assertEqual(self.resolve(model_id='new')['status'],'UNAVAILABLE')
        self.assertNotIn('newServerField',asdict(model))

    def test_catalog_or_api_window_never_becomes_active_window(self):
        model=normalize_model({'id':'x','contextWindow':999999,'publishedApiWindow':777777},observed_at=self.at)
        self.assertEqual(model.context_window,999999)
        self.assertIsNone(model.published_api_window)
        self.assertIsNone(model.context_window_runtime)
        self.assertIsNone(model.compact_limit_runtime)
        self.assertEqual(model.context_status,'UNKNOWN')
        self.assertEqual(model.compact_limit_scope,'UNKNOWN')

    def test_pagination_validates_each_request_and_binds_scope(self):
        calls=[]
        def request(method, params):
            calls.append((method,params))
            return {'data':[{'id':'a'}],'nextCursor':'next'} if not params else {'data':[{'id':'b','extra':True}]}
        catalog=discover_models(request,self.schema,binding=self.binding)
        self.assertEqual(catalog['status'],'VERIFIED_CATALOG')
        self.assertEqual(catalog['binding'],self.binding)
        self.assertEqual(calls,[('model/list',{}),('model/list',{'cursor':'next'})])
        self.assertEqual([m['id'] for m in catalog['models']],['a','b'])
        self.assertFalse(catalog['automatic_actions_allowed'])
        observed=discover_models(lambda *a:{'data':[]},self.schema)
        self.assertIsNone(observed['binding'])

    def test_pagination_failure_and_bad_metadata_drop_partial_results(self):
        for page in ({'data':[{'id':'a'}],'nextCursor':'repeat'}, {'data':[{'id':'a','supportedReasoningEfforts':'custom'}]},
                     {'data':[None]}, {'data':{}}, {'data':[{'id':''}]}, []):
            with self.subTest(page=page):
                result=discover_models(lambda *a:page,self.schema,binding=self.binding,max_pages=2)
                self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['models'],[])
        pages=iter([{'data':[{'id':'a'}],'nextCursor':'next'}, {'data':[{'id':'a','hidden':True}]}])
        self.assertEqual(discover_models(lambda *a:next(pages),self.schema)['status'],'UNKNOWN')

    def test_schema_missing_cursor_prevents_second_request(self):
        del self.schema.methods['model/list']['properties']['cursor']
        calls=[]
        def request(*args):calls.append(args);return {'data':[],'nextCursor':'next'}
        result=discover_models(request,self.schema)
        self.assertEqual(len(calls),1);self.assertEqual(result['status'],'UNKNOWN')

    def test_dimensions_cannot_expand_authorization(self):
        for args in ({'execution_mode':'multi_agent'}, {'permission_profile':':full-access'},
                     {'service_tier':'fixture-tier'}):
            self.assertEqual(self.resolve(**args)['status'],'UNAVAILABLE')
        authorized=self.params|{'serviceTier':'fixture-tier'}
        result=self.resolve(authorized_params=authorized,service_tier='fixture-tier')
        self.assertEqual(result['status'],'RESOLVED')
        self.assertEqual(result['wire_params']['permissions'],':read-only')
        self.assertEqual(result['wire_params']['approvalPolicy'],'on-request')
        self.assertNotIn('execution_mode',result['wire_params'])
        for field in ('tools','network','subagents'):
            self.assertNotIn(field,result['wire_params'])

    def test_unsupported_schema_constraints_refuse_action(self):
        self.schema.methods['turn/start']['properties']['effort']['const']='not-custom'
        self.assertEqual(self.resolve()['status'],'UNAVAILABLE')

    def test_advice_is_nonactionable_and_rejects_escalating_candidates(self):
        policy={'candidates':[dict(model_id='returned-id',effort='custom',cost_rank=1,capability_rank=1,approved_for=[])]}
        result=recommend(self.catalog,{},policy,at=self.at)
        self.assertFalse(result['actionable']);self.assertFalse(result['automatic_switch'])
        for field in ('tools','network','subagents','permission_profile','execution_mode'):
            candidate=policy['candidates'][0]|{field:'unauthorized'}
            self.assertIsNone(recommend(self.catalog,{}, {'candidates':[candidate]},at=self.at)['selected'])

    def test_service_tier_and_provider_must_match_exact_contract(self):
        self.model['service_tiers']='fixture-tier'
        self.assertEqual(self.resolve(authorized_params=self.params|{'serviceTier':'fixture'},
                                     service_tier='fixture')['reason'],'SERVICE_TIER_NOT_EXPOSED')
        self.model['provider']='foreign-provider'
        self.assertEqual(self.resolve()['reason'],'MODEL_PROVIDER_NOT_AUTHORIZED')
        self.assertEqual(self.resolve(authorized_params=self.params|{'modelProvider':'foreign-provider'})['status'],
                         'RESOLVED')

    def test_advisor_rejects_malformed_effort_metadata(self):
        self.model['reasoning_efforts']='custom'
        policy={'candidates':[dict(model_id='returned-id',effort='cust',cost_rank=1,capability_rank=1,approved_for=[])]}
        self.assertIsNone(recommend(self.catalog,{},policy,at=self.at)['selected'])

    def test_registry_response_is_detached_from_input_objects(self):
        result=self.resolve()
        result['wire_params']['input'][0]['text']='mutated prepared request'
        self.assertEqual(self.params['input'][0]['text'],'exact\r\n🙂')
        self.assertEqual(self.catalog['binding'],self.binding)

    def test_backdated_evaluation_cannot_reauthorize_stale_catalog(self):
        self.catalog['observed_at']='2000-01-01T00:00:00Z'
        self.assertEqual(self.resolve(at='2000-01-01T00:00:01Z')['reason'],'CATALOG_UNKNOWN_OR_STALE')
