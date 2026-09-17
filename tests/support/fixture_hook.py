"""Vetted fixture-only hook command; saves only test inputs. Never installed globally."""
import json
import os
from pathlib import Path
import sys
from dataclasses import replace

package=Path(__file__).resolve().parents[2];sys.path.insert(0,str(package))
from crg.config import Config,General,Emergency
from crg.state_store import StateStore
from crg.hooks import HookDispatcher
from crg.durable import immutable_write,private_directory
from crg.archive import sha

scratch=Path(sys.argv[1]).resolve()
event=json.load(sys.stdin)
name=event['hook_event_name'];turn=event.get('turn_id','session')
records=private_directory(scratch/'hook-inputs')
immutable_write(records/(name+'-'+sha(turn.encode())+'.json'),json.dumps(event,ensure_ascii=False).encode())
settings_file=scratch/'fixture-settings.json'
if name in {'Stop','UserPromptSubmit','PreCompact'} and settings_file.exists():
    settings=json.loads(settings_file.read_text())
    store=StateStore(scratch/'crg-state',Path(event['cwd']),settings['session_id'])
    config=Config(context_rollover=General(enabled=True,mode='MODE_B'),
                  emergency=Emergency(block_auto_compact=settings.get('precompact_block',False),force_rollover_on_next_prompt=True))
    result=HookDispatcher(store,config,allow_warning=True,configured_limit=20000,scope='total',
        allow_prompt_block=settings.get('prompt_block',False),allow_precompact_block=settings.get('precompact_block',False),
        archive_root=scratch/'archives').dispatch(event)
    print(json.dumps(result,ensure_ascii=False))
else:print('{}')
