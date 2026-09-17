from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from crg.capability_evidence import publish, validate, digest, binding_digest
from crg.appserver import ProtocolSchema, AppServerClient, ProtocolError
from tests.support.fixtures import fixture_path


class CapabilityEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.schema = self.root/'schema'; self.receipt = self.root/'capabilities.json'
        self.binary = self.root/'runtime'; self.binary.write_bytes(b'synthetic runtime')
        self.documents = {str(p.relative_to(fixture_path('protocol/schema'))):p.read_bytes()
                          for p in fixture_path('protocol/schema').rglob('*.json')}
        self.result = dict(binary=str(self.binary), binary_sha256=digest(self.binary.read_bytes()),
                           codex_version='test', surface='detached_cli', schema_generation_ok=True, errors=[])
        self.manifest = publish(self.receipt, self.schema, self.result, self.documents)

    def test_complete_generation_and_binding(self):
        self.assertEqual(validate(self.manifest,self.schema,binary=self.binary,for_action=True),
                         self.schema/self.manifest['generation'])
        ProtocolSchema(self.schema,manifest_path=self.receipt)
        for change in ({'codex_version':'upgrade'}, {'surface':'Desktop'}, {'binary':'elsewhere'},
                       {'checked_at':'corrupt'}, {'schema_sha256':{}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(self.manifest|change,self.schema)
        with self.assertRaises(ValueError):validate(self.manifest,self.schema,surface='Desktop')
        with self.assertRaises(ValueError):validate(self.manifest,self.root/'moved')

    def test_incomplete_corrupt_mixed_and_legacy_refused(self):
        for manifest in ({}, [], self.manifest|{'binding_sha256':'bad'}):
            with self.assertRaises(ValueError):validate(manifest,self.schema)
        root=self.schema/self.manifest['generation']
        extra=root/'old.json'; extra.write_text('{}')
        with self.assertRaises(ValueError):validate(self.manifest,self.schema)
        extra.unlink()
        (root/'ClientRequest.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):validate(self.manifest,self.schema)
        (root/'ClientRequest.json').unlink()
        with self.assertRaises(ValueError):validate(self.manifest,self.schema)

    def test_stale_future_and_runtime_replacement(self):
        for delta in (-2, 2):
            changed=self.manifest|{'checked_at':(datetime.now(timezone.utc)+timedelta(days=delta)).isoformat()}
            changed['binding_sha256']=binding_digest(changed)
            with self.assertRaises(ValueError):validate(changed,self.schema,for_action=True)
        self.binary.write_bytes(b'upgrade with same version label')
        with self.assertRaises(ValueError):validate(self.manifest,self.schema,binary=self.binary)

    def test_failed_publication_retains_previous_complete_generation(self):
        before=self.receipt.read_bytes()
        from crg.capability_probe import _write_private
        def fail_receipt(path, data):
            if path==self.receipt:raise OSError('simulated crash before publication')
            return _write_private(path,data)
        with patch('crg.capability_probe._write_private',side_effect=fail_receipt):
            with self.assertRaises(OSError):publish(self.receipt,self.schema,self.result,self.documents)
        self.assertEqual(self.receipt.read_bytes(),before)
        validate(json.loads(before),self.schema,binary=self.binary)

    def test_legacy_schema_can_parse_but_cannot_launch(self):
        schema=ProtocolSchema(fixture_path('protocol/schema'))
        schema.runtime_binary=sys.executable
        client=AppServerClient(sys.executable,schema,self.root,expected_version=schema.runtime_version)
        with patch('subprocess.Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaises(ProtocolError):client.start()

    def test_report_has_no_historical_boilerplate(self):
        from crg.capability_probe import render_report
        report=render_report({'surface':'unknown'})
        for phrase in ('workspace was empty','outputs/context-rollover-guard','IMPLEMENTATION_STATUS.md',
                       'INITIAL_ENVIRONMENT.md','Invalid-parameter requests'):
            self.assertNotIn(phrase,report)

    def test_unsafe_publication_path_is_refused_before_write(self):
        before=self.receipt.read_bytes()
        with self.assertRaises(ValueError):
            publish(self.receipt,self.schema,self.result,{'../escape.json':b'{}'})
        self.assertEqual(self.receipt.read_bytes(),before)

    def test_same_version_binary_replacement_blocks_client_before_launch(self):
        schema=ProtocolSchema(self.schema,manifest_path=self.receipt)
        client=AppServerClient(str(self.binary),schema,self.root,expected_version='test')
        self.binary.write_bytes(b'changed')
        with patch('subprocess.Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaises(ProtocolError):client.start()

    def test_probe_keeps_configuration_and_permissions_unchanged(self):
        from crg.capability_probe import probe
        from types import SimpleNamespace
        config=self.root/'config.toml'; config.write_text('approval_policy="never"\n')
        config.chmod(0o600); before=config.read_bytes(),config.stat().st_mode
        calls=[]
        def fake_run(argv, **kwargs):
            calls.append(argv)
            self.assertNotEqual(kwargs['env']['HOME'], str(Path.home()))
            self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
            if 'generate-json-schema' in argv:
                out=Path(argv[argv.index('--out')+1])
                for name,data in self.documents.items():
                    path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            return SimpleNamespace(returncode=0,stdout='test',stderr='')
        with patch('crg.capability_probe.inventory',return_value={}), \
             patch('crg.capability_probe.shutil.which',return_value=str(self.binary)), \
             patch('crg.capability_probe.subprocess.run',side_effect=fake_run), \
             patch('crg.capability_probe.isolated_rpc',return_value={'initialize_ok':True}):
            result=probe(self.root,self.root/'evidence',binary=str(self.binary),surface='Desktop')
        self.assertEqual((config.read_bytes(),config.stat().st_mode),before)
        self.assertEqual(len(calls),2)
        self.assertEqual(result['selected_mode'],'MODE_A')
        self.assertEqual(result['surface'],'detached_cli')
        self.assertEqual(result['requested_surface'],'Desktop')
        validate(result,self.root/'evidence/schema',binary=self.binary,for_action=True)

    def test_isolated_rpc_uses_read_only_methods_without_credentials(self):
        from crg.capability_probe import isolated_rpc
        binary=self.root/'fake-codex'; log=self.root/'calls.jsonl'
        binary.write_text('''#!/usr/bin/env python3
import sys,json,os
if '--version' in sys.argv:
 print('codex-cli test');raise SystemExit()
assert 'OPENAI_API_KEY' not in os.environ
assert 'CODEX_HOME' in os.environ
for line in sys.stdin:
 msg=json.loads(line)
 with open(LOG,'a') as out:out.write(json.dumps(msg)+'\\n')
 if 'id' not in msg:continue
 result={'data':[]} if msg['method'] in ('hooks/list','model/list') else {'config':{}}
 print(json.dumps({'id':msg['id'],'result':result}),flush=True)
'''.replace('LOG',repr(str(log))))
        binary.chmod(0o700)
        with patch.dict('os.environ',{'OPENAI_API_KEY':'synthetic-never-propagate'}):
            result=isolated_rpc(str(binary),self.root,
                                schema_document=json.loads(self.documents['ClientRequest.json']))
        calls=[json.loads(line) for line in log.read_text().splitlines()]
        self.assertTrue(result['initialize_ok'])
        self.assertLessEqual({c['method'] for c in calls},
                             {'initialize','initialized','hooks/list','config/read','model/list'})
        hooks=next(c for c in calls if c['method']=='hooks/list')
        self.assertNotIn(str(self.root),hooks['params']['cwds'])
