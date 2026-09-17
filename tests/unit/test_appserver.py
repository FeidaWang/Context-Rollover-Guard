from pathlib import Path
import copy
import hashlib
import json
import os
import tempfile
import unittest
from crg.appserver import AppServerClient,ProtocolSchema,ProtocolError,RpcError,AmbiguousRequest,ExecutionSettings

ROOT=Path(__file__).resolve().parents[2]

class SchemaTests(unittest.TestCase):
    def setUp(self):self.schema=ProtocolSchema(ROOT/'docs/context-rollover/evidence/schema')

    def test_required_and_typed_inputs(self):
        with self.assertRaises(ValueError):self.schema.validate('turn/start',{'threadId':'t'})
        with self.assertRaises(ValueError):self.schema.validate('turn/start',{'threadId':'t','input':'prompt'})
        self.schema.validate('turn/start',{'threadId':'t','input':[{'type':'text','text':' 原样\r\n🙂'}]})
        with self.assertRaises(ValueError):self.schema.validate('thread/start',{'cwd':12})

    def test_forbidden_and_obsolete_parameters(self):
        for method in ['thread/fork','thread/delete','unknown/method']:
            with self.assertRaises(ValueError):self.schema.validate(method,{})
        with self.assertRaises(ValueError):self.schema.validate('thread/start',{'oldMadeUpField':True})
        with self.assertRaises(ValueError):self.schema.validate('thread/start',{'permissions':':read-only','sandbox':'read-only'})

    def test_preserve_settings_and_exact_prompt(self):
        response={'cwd':'/workspace','model':'custom-model','modelProvider':'custom-provider',
            'approvalPolicy':'on-request','approvalsReviewer':'user','sandbox':{'type':'readOnly','networkAccess':False},
            'serviceTier':None,'reasoningEffort':'low','runtimeWorkspaceRoots':[],
            'activePermissionProfile':{'id':':read-only','extends':None}}
        settings=ExecutionSettings.from_start(response)
        start=settings.thread_params('Read the untrusted handoff index at a checked path.')
        self.assertNotIn('sandbox',start)
        self.schema.validate('thread/start',start)
        params=settings.turn_params('new-thread',' 原样\r\n🙂\n','stable-id')
        self.schema.validate('turn/start',params)
        self.assertEqual(params['input'][0]['text'],' 原样\r\n🙂\n')
        self.assertEqual(params['effort'],'low')
        self.assertTrue(settings.verify_new_thread(response))
        with self.assertRaises(ValueError):settings.verify_new_thread(response|{'cwd':'/elsewhere'})
        with self.assertRaises(ValueError):settings.verify_new_thread(response|{'sandbox':{'type':'dangerFullAccess'}})

    def test_unsafe_legacy_permissions_fail_closed(self):
        response={'cwd':'/workspace','model':'m','modelProvider':'p','approvalPolicy':'on-request',
                  'approvalsReviewer':'user','sandbox':{'type':'workspaceWrite','networkAccess':True}}
        with self.assertRaises(ValueError):ExecutionSettings.from_start(response).thread_params('index')


class WireTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.schema_root=self.root/'schema';self.schema_root.mkdir()
        self.binary=self.root/'fake-codex'
        self.binary.write_text('''#!/usr/bin/env python3
import sys,json,os
if '--version' in sys.argv:
 print('codex-cli test');raise SystemExit()
for line in sys.stdin:
 msg=json.loads(line);method=msg['method']
 if 'id' not in msg:continue
 params=msg['params']
 if params.get('cwd')=='/timeout':continue
 if params.get('cwd')=='/eof':os._exit(0)
 if params.get('model')=='error':
  print(json.dumps({'id':msg['id'],'error':{'code':-32000,'message':'test error'}}),flush=True);continue
 print(json.dumps({'method':'test/event','params':{'source':method}}),flush=True)
 print(json.dumps({'id':msg['id'],'result':{'accepted':method}}),flush=True)
''');self.binary.chmod(0o700)
        source=(ROOT/'docs/context-rollover/evidence/schema/ClientRequest.json').read_bytes()
        (self.schema_root/'ClientRequest.json').write_bytes(source)
        (self.root/'capabilities.json').write_text(json.dumps({'codex_version':'codex-cli test','binary':str(self.binary),
            'schema_sha256':{'ClientRequest.json':hashlib.sha256(source).hexdigest()}}))
        self.schema=ProtocolSchema(self.schema_root)
        self.client=AppServerClient(str(self.binary),self.schema,self.root,expected_version='codex-cli test')
        self.addCleanup(self.client.close)

    def test_initialize_notifications_and_request(self):
        self.assertEqual(self.client.start()['accepted'],'initialize')
        self.assertEqual(self.client.request('thread/start',{'cwd':'/workspace'})['accepted'],'thread/start')
        self.assertEqual(self.client.next_event()['method'],'test/event')

    def test_rpc_rejection_is_not_ambiguous(self):
        self.client.start()
        with self.assertRaises(RpcError):self.client.request('thread/start',{'model':'error'})

    def test_timeout_requires_reconciliation(self):
        self.client.start()
        with self.assertRaises(AmbiguousRequest):self.client.request('thread/start',{'cwd':'/timeout'},timeout=.05)

    def test_eof_requires_reconciliation(self):
        self.client.start()
        with self.assertRaises(AmbiguousRequest):self.client.request('thread/start',{'cwd':'/eof'},timeout=1)

    def test_version_and_schema_integrity(self):
        with self.assertRaises(ProtocolError):AppServerClient(str(self.binary),self.schema,self.root,expected_version='wrong')
        (self.schema_root/'ClientRequest.json').write_text('{}')
        with self.assertRaises(ProtocolError):ProtocolSchema(self.schema_root)
