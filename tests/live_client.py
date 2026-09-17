"""Explicit native runtime client acceptance probe; fixture workspace only."""
import argparse,json,time
from pathlib import Path
from crg.appserver import AppServerClient,ProtocolSchema,ExecutionSettings
from tests.support.live_server import LiveServer

def main():
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--duplicate-test',action='store_true');a=p.parse_args()
    schema=ProtocolSchema(Path('docs/context-rollover/evidence/schema'))
    fixture=LiveServer(a.scratch,schema.runtime_binary,command_only=True)
    client=AppServerClient(schema.runtime_binary,schema,fixture.workspace,expected_version=schema.runtime_version,command=fixture.command)
    report={'runtime':schema.runtime_version,'production_enabled':False}
    a.out.mkdir(parents=True,exist_ok=True)
    try:
        client.start()
        config=client.request('config/read',{'cwd':str(fixture.workspace),'includeLayers':False})['config']
        assert config['features']['hooks'] is False
        assert not any(v.get('enabled',True) for v in config.get('mcp_servers',{}).values())
        original=client.request('thread/start',{'cwd':str(fixture.workspace),'model':'gpt-6-astra','approvalPolicy':'never','sandbox':'read-only','ephemeral':False})
        settings=ExecutionSettings.from_start(original)
        params=settings.thread_params('CRG isolated fixture. Reply with OK. Do not use tools.')
        params['ephemeral']=False
        fresh=client.request('thread/start',params)
        settings.verify_new_thread(fresh)
        tid=fresh['thread']['id'];assert tid!=original['thread']['id']
        assert fresh['thread']['turns']==[]
        prompt='CRG exact prompt fixture: 中文\r\nReply only OK.  '
        result=client.request('turn/start',settings.turn_params(tid,prompt,'crg-fixture-message-01'))
        turn=result['turn']['id'];usage=False;deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            e=client.next_event(1)
            if not e:continue
            if 'id' in e and 'method' in e:raise RuntimeError('Unexpected server request')
            if e.get('method')=='thread/tokenUsage/updated':usage=True
            if e.get('method')=='turn/completed' and e['params']['turn']['id']==turn:
                assert e['params']['turn']['status']=='completed';break
        else:raise TimeoutError('Fixture completion')
        read=client.request('thread/read',{'threadId':tid,'includeTurns':True})
        messages=[i for t in read['thread']['turns'] for i in t['items'] if i['type']=='userMessage']
        report.update(fresh=True,same_settings=True,same_cwd=True,usage_seen=usage,
                      user_messages=len(messages),client_id_retained=messages[0].get('clientId')=='crg-fixture-message-01',
                      prompt_exact=messages[0]['content'][0]['text']==prompt)
        assert report['client_id_retained'] and report['prompt_exact'] and len(messages)==1
        if a.duplicate_test:
            # Only synthetic text in an owned test thread: establish whether clientId deduplicates.
            again=client.request('turn/start',settings.turn_params(tid,prompt,'crg-fixture-message-01'))
            deadline=time.monotonic()+150
            while time.monotonic()<deadline:
                e=client.next_event(1)
                if e and e.get('method')=='turn/completed' and e['params']['turn']['id']==again['turn']['id']:break
            else:raise TimeoutError('Duplicate fixture completion')
            repeated=client.request('thread/read',{'threadId':tid,'includeTurns':True})
            copies=[i for t in repeated['thread']['turns'] for i in t['items'] if i['type']=='userMessage' and i.get('clientId')=='crg-fixture-message-01']
            report['duplicate_client_id_user_messages']=len(copies)
            report['client_id_is_idempotency_key']=len(copies)==1
        client.request('thread/archive',{'threadId':tid})
        report['test_new_thread_archived_after_acceptance']=True
        report['status']='PASS'
    except Exception as exc:
        report.update(status='BLOCKED',error_type=type(exc).__name__,error=str(exc)[:300]);raise
    finally:
        client.close();(a.out/'client-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
