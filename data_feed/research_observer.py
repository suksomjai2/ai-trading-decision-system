"""RESEARCH ONLY. Reads committed audit; never imports or calls decision code.

Separate SQLite file, thread, state and cursor. Errors must not propagate to
the HTTP decision path. All post-SL extrema use quotes strictly AFTER exit.
"""
import json
import logging
import math
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

VERSION = 'POST_SL_M5_V1'
LOG = logging.getLogger(__name__)

@contextmanager
def connect_readonly(path):
    c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=0.2)
    try:yield c
    finally:c.close()

class ResearchObserver:
    def __init__(self, audit_path, research_path):
        self.audit_path = Path(audit_path)
        self.path = Path(research_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS progress (id INTEGER PRIMARY KEY CHECK(id=1), cursor INTEGER NOT NULL);
                INSERT OR IGNORE INTO progress VALUES(1,0);
                CREATE TABLE IF NOT EXISTS post_sl (
                    trade_id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
                    exit_time REAL NOT NULL, deadline REAL NOT NULL,
                    status TEXT NOT NULL, value TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS post_sl_window ON post_sl(symbol,status,deadline);
                CREATE TABLE IF NOT EXISTS decision_explanations (
                    event_id INTEGER PRIMARY KEY, symbol TEXT, time REAL, value TEXT);
                CREATE TABLE IF NOT EXISTS observer_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path, timeout=0.2)
        try:
            with c:yield c
        finally:c.close()

    def poll(self, now=None, limit=500):
        """One bounded batch; transactional cursor makes retries/restarts safe."""
        now = time.time() if now is None else now
        with self.connect() as c:
            cursor = c.execute('SELECT cursor FROM progress WHERE id=1').fetchone()[0]
            with connect_readonly(self.audit_path) as a:
                rows = a.execute('SELECT id,symbol,time,kind,value FROM events WHERE id>? ORDER BY id LIMIT ?',
                                 (cursor,limit)).fetchall()
                high_watermark=a.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
            for event_id,symbol,stamp,kind,raw in rows:
                e = json.loads(raw)
                if kind == 'EXIT' and e['trade'].get('outcome')=='SL_TOUCHED':
                    self._begin(c,symbol,e['trade'])
                elif kind == 'EVALUATION':
                    self._quote(c,symbol,stamp,e)
                    self._explain(c,event_id,symbol,stamp,e)
                elif kind == 'CLOSED_CONTEXT':
                    self._close(c,symbol,e)
            if rows:
                c.execute('UPDATE progress SET cursor=? WHERE id=1',(rows[-1][0],))
            # Expire only after draining committed events. Never skip an already
            # recorded TP touch just because a historical backfill takes time.
            if len(rows)<limit:
                for (raw,) in c.execute("SELECT value FROM post_sl WHERE status='ACTIVE' AND deadline<?",(now-30,)).fetchall():
                    v=json.loads(raw);self._finish(v);self._save(c,v)
            position=rows[-1][0] if rows else cursor
            c.execute("INSERT OR REPLACE INTO observer_state VALUES('heartbeat',?)",(json.dumps(dict(time=now,cursor=position,
                      source_high_watermark=high_watermark,caught_up=position>=high_watermark,version=VERSION)),))
        return len(rows)

    @staticmethod
    def _save(c,v):
        c.execute('INSERT OR REPLACE INTO post_sl VALUES(?,?,?,?,?,?)',
                  (v['trade_id'],v['symbol'],v['exit_time'],v['deadline'],v['status'],json.dumps(v,allow_nan=False)))

    def _begin(self,c,symbol,t):
        if c.execute('SELECT 1 FROM post_sl WHERE trade_id=?',(t['id'],)).fetchone():return
        end=(math.floor(t['exit_time']/300)+1)*300
        v=dict(trade_id=t['id'],symbol=symbol,side=t['side'],entry_price=t['entry_price'],
               original_tp=t['tp'],original_sl=t['sl'],exit_time=t['exit_time'],
               exit_observed_price=t['exit_observed_price'],deadline=end,
               bar_start=end-300,status='ACTIVE',research_version=VERSION,
               decision_policy=t.get('policy'),research_only=True,
               mfe_after_exit=0.0,mae_after_exit=0.0,tp_observed_after_sl=False,
               first_tp_time=None,quote_count=0,last_quote_time=t['exit_time'],
               last_exit_side_price=None,max_gap_seconds=0.0,
               exact_bid_candle_close=None,close_side_of_sl='UNKNOWN',
               coverage='SAMPLED_QUOTES_ONLY',classification='PENDING')
        self._save(c,v)

    def _quote(self,c,symbol,stamp,e):
        for (raw,) in c.execute("SELECT value FROM post_sl WHERE symbol=? AND status='ACTIVE'",(symbol,)).fetchall():
            v=json.loads(raw)
            if stamp<=v['last_quote_time']:continue
            if stamp>v['deadline']:
                self._finish(v);self._save(c,v);continue
            # The exit-triggering quote is excluded. SELL uses actual Ask.
            q=e['bid'] if v['side']=='BUY' else e.get('ask')
            if q is None:
                v['coverage']='ASK_UNAVAILABLE';self._save(c,v);continue
            sign=1 if v['side']=='BUY' else -1
            move=sign*(q-v['exit_observed_price'])
            v['mfe_after_exit']=max(v['mfe_after_exit'],move)
            v['mae_after_exit']=max(v['mae_after_exit'],-move)
            v['max_gap_seconds']=max(v['max_gap_seconds'],stamp-v['last_quote_time'])
            v.update(last_quote_time=stamp,last_exit_side_price=q,quote_count=v['quote_count']+1)
            if sign*(q-v['original_tp'])>=0 and not v['tp_observed_after_sl']:
                v.update(tp_observed_after_sl=True,first_tp_time=stamp)
            if stamp==v['deadline']:self._finish(v)
            self._save(c,v)

    @staticmethod
    def _finish(v):
        tail=v['deadline']-v['last_quote_time']
        v['max_gap_seconds']=max(v['max_gap_seconds'],tail)
        v['status']='WINDOW_FINISHED'
        if v['coverage']=='ASK_UNAVAILABLE' or not v['quote_count'] or v['max_gap_seconds']>30:
            v['coverage']='INCOMPLETE';v['classification']='INSUFFICIENT_DATA'
        else:
            v['coverage']='SAMPLED_QUOTES_ONLY'
            sign=1 if v['side']=='BUY' else -1
            back=sign*(v['last_exit_side_price']-v['original_sl'])>0
            v['classification']='RETURNED_INSIDE_SL_AT_LAST_QUOTE' if back else 'STILL_OUTSIDE_SL_AT_LAST_QUOTE'
        # A sampled non-touch is never a claim that TP was impossible/unhit.
        v['tp_result']='OBSERVED_TOUCH' if v['tp_observed_after_sl'] else 'NOT_OBSERVED_NOT_PROVEN_ABSENT'

    def _close(self,c,symbol,e):
        # Only the final CLOSE is safe; high/low also contain pre-SL prices.
        for b in (e.get('recent_candles') or {}).get('M5',[]):
            for (raw,) in c.execute('SELECT value FROM post_sl WHERE symbol=? AND deadline=?',(symbol,b['time']+300)).fetchall():
                v=json.loads(raw);v['exact_bid_candle_close']=b['close']
                if v['side']=='BUY':
                    v['close_side_of_sl']='INSIDE' if b['close']>v['original_sl'] else 'OUTSIDE'
                else:v['close_side_of_sl']='UNKNOWN_HISTORICAL_ASK'
                self._save(c,v)

    @staticmethod
    def _explain(c,event_id,symbol,stamp,e):
        d=e.get('diagnostics') or {}; s=d.get('selection') or {}
        signature=json.dumps([e.get('stage'),e.get('reason'),e.get('candidate_side'),s],sort_keys=True)
        key='explanation_signature:'+symbol
        old=c.execute('SELECT value FROM observer_state WHERE key=?',(key,)).fetchone()
        if old and old[0]==signature:return
        v=dict(research_only=True,source_event_id=event_id,decision_policy=d.get('policy'),
               stage=e.get('stage'),reason=e.get('reason'),candidate=e.get('candidate_side'),
               m15_candidate=s.get('m15_candidate'),m5_candidate=s.get('m5_candidate'),
               selection_reason=s.get('selection_reason'),reaction_level=s.get('reaction_level'),
               zone_basis=d.get('zone_basis'),retained_pending_setup=d.get('retained_pending_setup',False),
               source_selection=s,
               note='Recorded reasons actually emitted by decision; no new direction rule or inferred leg base.')
        c.execute('INSERT OR IGNORE INTO decision_explanations VALUES(?,?,?,?)',(event_id,symbol,stamp,json.dumps(v)))
        c.execute('INSERT OR REPLACE INTO observer_state VALUES(?,?)',(key,signature))

def build_research_report(path,now,limit=100):
    from datetime import datetime,timezone,timedelta
    local=datetime.fromtimestamp(now,timezone(timedelta(hours=7)))
    start=local.replace(hour=7,minute=0,second=0,microsecond=0)
    if local<start:start-=timedelta(days=1)
    with connect_readonly(path) as c:
        rows=c.execute("SELECT value FROM post_sl WHERE symbol='XAUUSD' AND (exit_time>=? OR status='ACTIVE') ORDER BY exit_time DESC LIMIT ?",(start.timestamp(),limit)).fetchall()
        heartbeat=c.execute("SELECT value FROM observer_state WHERE key='heartbeat'").fetchone()
    hb=json.loads(heartbeat[0]) if heartbeat else None
    status=('STALE' if not hb or now-hb['time']>=30 else 'OK' if hb.get('caught_up') else 'BACKFILLING')
    return dict(status=status,research_only=True,
                research_version=VERSION,heartbeat=hb,items=[json.loads(r[0]) for r in rows],
                limit=limit,scope='SL exits in current 07:00 reporting window, plus active observations')

def worker(root,stop=None):
    root=Path(root);observer=None
    while stop is None or not stop.is_set():
        try:
            if observer is None:
                observer=ResearchObserver(root/'runtime/engine.sqlite3',root/'runtime/research.sqlite3')
            count=observer.poll()
            delay=0.01 if count==500 else 1.0
        except Exception as exc:
            LOG.warning('RESEARCH_ONLY unavailable: %s',type(exc).__name__)
            delay=2.0
        if stop is not None:stop.wait(delay)
        else:time.sleep(delay)

def start(root):
    thread=threading.Thread(target=worker,args=(root,),name='research-only',daemon=True)
    thread.start()
    return thread
