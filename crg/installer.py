"""Explicit Hook merge/unmerge with private rollback receipts and compare-before-write.

No installation occurs on import. Existing Hook entries and root fields are preserved.
Hook trust and production mode activation are deliberately separate runtime decisions.
"""
import base64,copy,json,os,shlex,stat,tempfile
from pathlib import Path
from .archive import sha
from .durable import private_directory,exclusive_lock,immutable_write,read_private,sync_directory
from .state_store import canonical,_pairs

EVENTS=('Stop','UserPromptSubmit','PreCompact','SessionStart','PostCompact')

def _read(path):
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Symlink Hook path refused')
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return None
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid():raise ValueError('Unsafe Hook file')
        return f.read()

def _decode(raw):
    data=json.loads(raw,object_pairs_hook=_pairs) if raw is not None else {}
    if not isinstance(data,dict) or not isinstance(data.get('hooks',{}),dict):raise ValueError('Invalid Hook configuration')
    for event,entries in data.get('hooks',{}).items():
        if not isinstance(entries,list):raise ValueError('Invalid Hook entries')
    return data

def plan_hooks(path,argv):
    path=Path(path).absolute()
    if not argv or any(not isinstance(x,str) or not x for x in argv):raise ValueError('Explicit dispatcher argv required')
    before=_read(path);data=_decode(before);after=copy.deepcopy(data);hooks=after.setdefault('hooks',{})
    entry={'hooks':[{'type':'command','command':shlex.join(argv),'timeout':10}]}
    additions=[]
    for event in EVENTS:
        entries=hooks.setdefault(event,[])
        if entry not in entries:entries.append(copy.deepcopy(entry));additions.append(event)
    raw=(json.dumps(after,ensure_ascii=False,indent=2)+'\n').encode()
    if not additions:raw=before
    return {'path':str(path),'before_sha256':sha(before) if before is not None else None,
            'after_sha256':sha(raw),'before_base64':base64.b64encode(before).decode() if before is not None else None,
            'after_base64':base64.b64encode(raw).decode(),'entry':entry,'events_added':additions}

def _replace(path,data,expected):
    current=_read(path)
    if (sha(current) if current is not None else None)!=expected:raise ValueError('Hook file changed; re-plan before applying')
    path.parent.mkdir(parents=True,exist_ok=True)
    mode=stat.S_IMODE(path.stat().st_mode) if current is not None else 0o600
    fd,temp=tempfile.mkstemp(prefix='.crg-hooks-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:os.fchmod(f.fileno(),mode);f.write(data);f.flush();os.fsync(f.fileno())
        again=_read(path)
        if (sha(again) if again is not None else None)!=expected:raise ValueError('Concurrent Hook edit; apply aborted')
        os.replace(temp,path);sync_directory(path.parent)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def install_hooks(plan,receipt_root):
    if not plan['events_added']:return {'changed':False,'receipt':None}
    root=private_directory(Path(receipt_root));ident=sha(canonical(plan));directory=private_directory(root/ident)
    with exclusive_lock(root):
        path=Path(plan['path']);current=_read(path)
        if current is not None and sha(current)==plan['after_sha256']:
            if not (directory/'plan.json').exists():raise ValueError('Unowned existing install; do not claim it')
            return {'receipt':str(directory),'changed':False}
        immutable_write(directory/'plan.json',canonical(plan))
        data=base64.b64decode(plan['after_base64'])
        if sha(data)!=plan['after_sha256']:raise ValueError('Invalid installation plan')
        _replace(path,data,plan['before_sha256'])
        immutable_write(directory/'installed.json',canonical({'after_sha256':sha(data)}))
        return {'receipt':str(directory),'changed':True,'trust_modified':False,'production_enabled':False}

def uninstall_hooks(receipt):
    directory=Path(receipt).absolute();private_directory(directory)
    with exclusive_lock(directory.parent):
        plan=json.loads(read_private(directory/'plan.json'))
        if sha(canonical(plan))!=directory.name:raise ValueError('Receipt integrity mismatch')
        path=Path(plan['path']);current=_read(path)
        if current is None:return {'changed':False,'reason':'Hook file already absent'}
        if not (directory/'installed.json').exists() and sha(current)!=plan['after_sha256']:
            raise ValueError('Installation was not confirmed; preserve current Hook file')
        if (directory/'uninstalled.json').exists():return {'changed':False}
        before=base64.b64decode(plan['before_base64']) if plan['before_base64'] is not None else None
        if sha(current)==plan['after_sha256']:
            restored=before if before is not None else b'{"hooks":{}}\n'
        else:
            data=_decode(current)
            for event in plan['events_added']:
                entries=data.get('hooks',{}).get(event,[]);count=entries.count(plan['entry'])
                if count>1:raise ValueError('Ambiguous duplicate Hook ownership; leave unchanged')
                if count==1:entries.remove(plan['entry'])
            restored=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
        _replace(path,restored,sha(current))
        immutable_write(directory/'uninstalled.json',canonical({'sha256':sha(restored)}))
        return {'changed':True,'user_entries_preserved':True,'files_deleted':False}
