"""Opt-in native owned-client test. Arms only its own diagnostic thread state."""
from pathlib import Path
from dataclasses import replace
import json
from crg.appserver import AppServerClient,ProtocolSchema
from crg.config import load_config
from crg.owned_client import OwnedSession
from crg.state_store import StateStore
from crg.domain import State


def main():
    from tests.support.live_policy import require_live_authorization
    require_live_authorization('live_owned_client')
    root=Path.cwd();schema=ProtocolSchema(root/'docs/context-rollover/evidence/schema')
    client=AppServerClient(schema.runtime_binary,schema,root,expected_version=schema.runtime_version,
        command=[schema.runtime_binary,'-c','features.hooks=true','app-server','--stdio'])
    config=load_config(root);report={'synthetic_arming':True,'production_threshold_changed':False,'trust_bypass':False}
    try:
        client.start();session=OwnedSession(client,config,timeout=90)
        session.start({'sandbox':'read-only'})
        first=session.submit('Reply exactly CRG_ROUTE_ONE. Do not use tools.');old=session.thread
        store=StateStore(config.paths(root)[1],root,old)
        store.update(lambda s:replace(s,state=State.ARMED.value))
        prompt='Reply exactly CRG_ROUTE_TWO. Do not use tools.\r\n  '
        second=session.submit(prompt);new=session.thread
        third=session.submit('Reply exactly CRG_ROUTE_THREE. Do not use tools.')
        assert first['text']=='CRG_ROUTE_ONE' and second['text']=='CRG_ROUTE_TWO' and third['text']=='CRG_ROUTE_THREE'
        assert old!=new and third['thread_id']==new
        response=client.request('thread/read',{'threadId':new,'includeTurns':True})['thread']
        messages=[i for t in response['turns'] for i in t['items'] if i['type']=='userMessage']
        assert len(messages)==2 and messages[0]['content'][0]['text']==prompt
        archived=client.request('thread/list',{'archived':True,'cwd':str(root),'limit':100})
        assert any(t['id']==old for t in archived['data'])
        report.update(status='PASS',fresh_thread=True,exact_prompt_once=True,third_turn_routed=True,
            old_archived=True,old_thread_id=old,new_thread_id=new,journal=str(session.root))
        client.request('thread/archive',{'threadId':new})
    finally:
        client.close()
        (root/'docs/context-rollover/evidence/owned-client-live.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
if __name__=='__main__':main()
