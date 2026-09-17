"""Generate only synthetic timing aggregates; never reads user files or logs."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from crg.export import interchange


def rows():
    result=[]
    for project,values in enumerate(([100]*30,[0,1,2]*10,[100]*10+[1000]*10+[100]*10,list(range(30)),[100]*29+[100000])):
        for index,value in enumerate(values):
            result.append(dict(schema_version=1,kind='timing',observation_id=str(index),fact_id=str(index),revision=0,
                source='synthetic-generator',adapter_version='1',scope='local',account_id=None,workspace_id=None,
                thread_id=str(project),quality='synthetic',observed_at=f'2026-01-01T00:00:{index:02d}Z',
                received_at='2026-01-02T00:00:00Z',data={'wall_ms':value,'active_ms':None,'acceptance_ms':None,'complete':True}))
    # Preserve order; numeric ordinal is added to the typed interchange contract.
    records=[json.loads(line) for line in interchange(result).splitlines()]
    counters={}
    for row in records:
        cluster=row['cluster_id'];row['sequence_index']=counters.get(cluster,0);counters[cluster]=row['sequence_index']+1
    return records

if __name__=='__main__':
    for row in rows():print(json.dumps(row,sort_keys=True))
