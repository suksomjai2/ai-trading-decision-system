"""Research-only projection of committed facts; never imported by decision code.

Origin is immutable. A changed selector is logged separately from the frozen
setup zone. Legacy/in-flight origins are explicitly unknown, never invented.
"""
import json
import sqlite3
from pathlib import Path

VERSION = 'SETUP_LIFECYCLE_V1'

def ensure_schema(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS setup_lifecycle (
            setup_id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
            last_time REAL NOT NULL, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS setup_lifecycle_events (
            event_id INTEGER PRIMARY KEY, setup_id TEXT NOT NULL,
            symbol TEXT NOT NULL, time REAL NOT NULL, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS setup_lifecycle_time ON setup_lifecycle_events(time);
        CREATE INDEX IF NOT EXISTS setup_lifecycle_setup ON setup_lifecycle_events(setup_id,event_id);
    ''')

def summarize(current, event):
    """Pure fold, also used for historical exports cut at the requested end."""
    v = dict(current or dict(setup_id=event['setup_id'], symbol=event['symbol'],
             research_only=True, version=VERSION, origin=None, origin_status='UNKNOWN_PRE_V5',
             change_count=0, status='OBSERVING'))
    kind=event['kind'];e=event.get('evidence') or {};setup=event.get('setup')
    if kind=='ARMED' and v['origin'] is None:
        v['origin']=dict(time=event['time'],setup=setup,evidence=e)
        v['origin_status']='RECORDED_AT_CREATION'
    if kind=='WAIT_REASON_CHANGED':v['change_count']+=1
    if setup:v['latest_setup']=setup
    if e:v['last_evidence']=e
    if kind=='ENTRY':
        v['entry']=dict(time=event['time'],setup=setup,evidence=e,trade=event.get('trade'))
        v['status']='OPEN'
    elif kind in ('CANCEL','EXIT'):
        v['terminal']=dict(time=event['time'],kind=kind,reason=event.get('reason'),trade=event.get('trade'),evidence=e)
        v['status']=kind
    v.update(last_time=event['time'],last_event_id=event['source_event_id'])
    return v

def ingest(c, event_id, symbol, stamp, kind, raw):
    """Called only in the independent observer transaction; retry-safe by ID."""
    e=raw;details=e.get('audit_evidence')
    if kind=='EVALUATION':
        d=e.get('diagnostics') or {}
        if d.get('policy')!='CONTEXTUAL_REACTION_V5':return
        setup_id=e.get('setup_id')
        if not setup_id:return
        selection=d.get('selection') or {}
        # Prices are evidence at a change, never part of its changing signature.
        signature=json.dumps(dict(stage=e.get('stage'),reason=e.get('reason'),
            candidate=e.get('candidate_side'),selection=selection,
            selector_basis=d.get('zone_basis'),retained=d.get('retained_pending_setup',False)),sort_keys=True)
        row=c.execute('SELECT value FROM setup_lifecycle WHERE setup_id=?',(setup_id,)).fetchone()
        old=json.loads(row[0]) if row else {}
        if old.get('last_wait_signature')==signature:return
        details=dict(stage=e.get('stage'),reason=e.get('reason'),selection=selection,
            selector_basis=d.get('zone_basis'),retained_pending_setup=d.get('retained_pending_setup',False),
            bid=e.get('bid'),ask=e.get('ask'),candidate=e.get('candidate_side'),
            zone_low=d.get('zone_low'),zone_high=d.get('zone_high'),
            trigger=d.get('live_trigger'),trigger_passed=d.get('live_trigger_passed'),
            thesis_invalidation=d.get('thesis_invalidation'),stop_price=d.get('stop_price'))
        stage_kind='WAIT_REASON_CHANGED' if e.get('stage')=='ARMED' else 'DECISION_REASON_CHANGED'
    else:
        if not details or details.get('release_policy')!='CONTEXTUAL_REACTION_V5':return
        setup=e.get('setup') or {};trade=e.get('trade') or {}
        setup_id=setup.get('id') or trade.get('id') or e.get('setup_id')
        if not setup_id:return
        stage_kind=kind;signature=None
        row=c.execute('SELECT value FROM setup_lifecycle WHERE setup_id=?',(setup_id,)).fetchone()
        old=json.loads(row[0]) if row else {}
    record=dict(research_only=True,version=VERSION,source_event_id=event_id,
        setup_id=setup_id,symbol=symbol,time=stamp,kind=stage_kind,
        reason=e.get('reason'),setup=e.get('setup'),trade=e.get('trade'),evidence=details)
    inserted=c.execute('INSERT OR IGNORE INTO setup_lifecycle_events VALUES(?,?,?,?,?)',
        (event_id,setup_id,symbol,stamp,json.dumps(record,allow_nan=False))).rowcount
    if not inserted:return
    value=summarize(old,record)
    if signature:value['last_wait_signature']=signature
    c.execute('INSERT OR REPLACE INTO setup_lifecycle VALUES(?,?,?,?)',
        (setup_id,symbol,stamp,json.dumps(value,allow_nan=False)))

def export_history(c,start,end):
    ids=[r[0] for r in c.execute('SELECT DISTINCT setup_id FROM setup_lifecycle_events WHERE time>=? AND time<?',(start,end))]
    summaries=[];events=[]
    for setup_id in ids:
        value=None
        for (raw,) in c.execute('SELECT value FROM setup_lifecycle_events WHERE setup_id=? AND time<? ORDER BY event_id',(setup_id,end)):
            event=json.loads(raw);events.append(event);value=summarize(value,event)
        if value:summaries.append(value)
    events.sort(key=lambda e:e['source_event_id'])
    return summaries,events

def build_lifecycle_report(path,now,limit=3,event_limit=8):
    c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
    try:
        rows=c.execute('SELECT setup_id,value FROM setup_lifecycle ORDER BY last_time DESC LIMIT ?',(limit,)).fetchall()
        items=[]
        for setup_id,raw in rows:
            v=json.loads(raw);v.pop('last_wait_signature',None)
            count=c.execute('SELECT COUNT(*) FROM setup_lifecycle_events WHERE setup_id=?',(setup_id,)).fetchone()[0]
            latest=c.execute('SELECT value FROM setup_lifecycle_events WHERE setup_id=? ORDER BY event_id DESC LIMIT ?',(setup_id,event_limit)).fetchall()
            v['recent_changes']=[json.loads(x[0]) for x in reversed(latest)]
            v.update(total_events=count,display_truncated=count>event_limit)
            items.append(v)
        hb=c.execute("SELECT value FROM observer_state WHERE key='heartbeat'").fetchone()
        heartbeat=json.loads(hb[0]) if hb else None
        status=('STALE' if not heartbeat or now-heartbeat['time']>=30 else
                'OK' if heartbeat.get('caught_up') else 'BACKFILLING')
        return dict(research_only=True,version=VERSION,status=status,generated_at=now,items=items,heartbeat=heartbeat,
            note='Recent setups only; complete history is available in dated ZIP export.')
    finally:c.close()
