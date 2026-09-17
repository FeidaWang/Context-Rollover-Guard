"""Synthetic registry contracts only; never launch the bound Python executable."""
import json
from pathlib import Path
import sys
from crg.appserver import ProtocolSchema
from crg.capability_evidence import publish, digest
from crg.models import runtime_binding
from tests.support.fixtures import fixture_path


def contract(root):
    schema_root=root/'schema'
    document=json.loads(fixture_path('protocol/schema/ClientRequest.json').read_bytes())
    document['oneOf'].append({'properties':{'method':{'enum':['model/list']}, 'params':{
        'type':'object','properties':{'cursor':{'type':'string'}},'additionalProperties':False}}})
    for variant in document['oneOf']:
        if variant['properties']['method']['enum']==['turn/start']:
            variant['properties']['params']['properties']['effort']={'enum':['custom','low']}
            variant['properties']['params']['properties']['serviceTier']={'enum':[None,'fixture-tier']}
    binary=Path(sys.executable).resolve()
    publish(root/'capabilities.json',schema_root,
            dict(binary=str(binary),binary_sha256=digest(binary.read_bytes()),codex_version='synthetic-runtime',
                 surface='detached_cli',schema_generation_ok=True,errors=[]),
            {'ClientRequest.json':json.dumps(document).encode()})
    schema=ProtocolSchema(schema_root)
    binding=runtime_binding(schema,auth_mode='synthetic',account_scope_id='synthetic-account',client_surface='detached_cli')
    params={'threadId':'synthetic-thread','input':[{'type':'text','text':'exact\r\n🙂'}],
            'permissions':':read-only','approvalPolicy':'on-request','serviceTier':None}
    return schema,binding,params
