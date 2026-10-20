"""Read-only dated audit export; standard library only, never trades or stops MT5."""
import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime,timezone,timedelta
from pathlib import Path

THAI=timezone(timedelta(hours=7))

def desktop():
    if os.name=='nt':
        import ctypes
        buffer=ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,buffer)==0:
            return Path(buffer.value)
    p=Path.home()/'Desktop'
    if p.is_dir():return p
    raise RuntimeError('Desktop not found; specify --output DIRECTORY')

def snapshot(source,target):
    with closing(sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as a:
        with closing(sqlite3.connect(target)) as b:a.backup(b)

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def scrub(text):
    text=re.sub(r'(?:sb_secret_|ghp_|github_pat_)[A-Za-z0-9_\-.]+','[REDACTED]',text)
    text=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED_JWT]',text)
    return re.sub(r'''(?i)(secret_key|apikey|password|token)(["']?\s*[:=]\s*["']?)([^"'\s,}]+)''',r'\1\2[REDACTED]',text)

def export_audit(root,start_date,end_date,output=None,now=None):
    root=Path(root).resolve();now=datetime.now(timezone.utc) if now is None else now
    start=datetime.strptime(start_date,'%Y-%m-%d').replace(tzinfo=THAI)
    end=datetime.strptime(end_date,'%Y-%m-%d').replace(tzinfo=THAI)+timedelta(days=1)
    if start>=end:raise ValueError('Start date is after end date')
    end=min(end,now.astimezone(THAI))
    if start>=end:raise ValueError('No elapsed time in requested dates')
    context_start=start-timedelta(days=1)
    output=Path(output) if output else desktop();output.mkdir(parents=True,exist_ok=True)
    name='AITrading-V3-Audit-'+start_date+'_'+end_date+'-'+now.astimezone(THAI).strftime('%Y%m%d-%H%M%S-%f')+'.zip'
    destination=output/name
    with tempfile.TemporaryDirectory(prefix='AITrading-audit-') as tmp:
        folder=Path(tmp);db=folder/'audit-snapshot.sqlite3'
        snapshot(root/'runtime/engine.sqlite3',db)
        with closing(sqlite3.connect(db)) as c:
            values=c.execute('SELECT id,symbol,time,kind,value FROM events WHERE time>=? AND time<? ORDER BY id',
                             (context_start.timestamp(),end.timestamp())).fetchall()
            state={s:json.loads(v) for s,v in c.execute('SELECT symbol,value FROM engine_state')}
        db.unlink()
        with (folder/'events.jsonl').open('w',encoding='utf-8') as f:
            for event_id,symbol,t,kind,raw in values:
                f.write(json.dumps(dict(id=event_id,symbol=symbol,time=t,kind=kind,data=json.loads(raw)),ensure_ascii=False)+'\n')
        trades={}
        counts={}
        for _,_,t,kind,raw in values:
            if start.timestamp()<=t<end.timestamp():counts[kind]=counts.get(kind,0)+1
            if kind in ('ENTRY','EXIT'):
                tr=json.loads(raw)['trade'];trades[tr['id']]={**trades.get(tr['id'],{}),**tr}
        relevant=[t for t in trades.values() if start.timestamp()<=t['entry_time']<end.timestamp()
                  or start.timestamp()<=t.get('exit_time',-1)<end.timestamp()]
        dump(folder/'trades.json',relevant)
        fields=['id','side','entry_time','entry_price','tp','sl','exit_time','exit_observed_price','outcome',
                'mfe_observed','mae_observed','policy','coverage_gap','observed_price_move']
        with (folder/'trades.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader()
            for tr in relevant:
                move=(1 if tr['side']=='BUY' else -1)*(tr['exit_observed_price']-tr['entry_price']) if tr.get('exit_observed_price') is not None else None
                writer.writerow({**tr,'observed_price_move':move})
        dump(folder/'engine_state_at_export.json',state)
        research_status='NOT_FOUND'
        if (root/'runtime/research.sqlite3').exists():
            research_db=folder/'research-snapshot.sqlite3';snapshot(root/'runtime/research.sqlite3',research_db)
            with closing(sqlite3.connect(research_db)) as c:
                xs=c.execute('SELECT value FROM post_sl WHERE exit_time>=? AND exit_time<? ORDER BY exit_time',
                             (start.timestamp(),end.timestamp())).fetchall()
                dump(folder/'post_sl_research.json',[json.loads(x[0]) for x in xs])
                with (folder/'decision_explanations.jsonl').open('w',encoding='utf-8') as f:
                    for (raw,) in c.execute('SELECT value FROM decision_explanations WHERE time>=? AND time<? ORDER BY event_id',
                                           (context_start.timestamp(),end.timestamp())):f.write(raw+'\n')
                heartbeat=c.execute("SELECT value FROM observer_state WHERE key='heartbeat'").fetchone()
                dump(folder/'research_progress.json',json.loads(heartbeat[0]) if heartbeat else {})
            research_db.unlink();research_status='EXPORTED_CHECK_PROGRESS_FOR_BACKLOG'
        hashes={}
        paths=[]
        for part in ['core','data_feed']:
            paths.extend((root/part).glob('*.py'))
        paths.extend(root/p for p in ['run_vps_server.py','streamlit_app.py','v3_release.json'] if (root/p).exists())
        for p in paths:
            rel=p.relative_to(root);target=folder/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True)
            raw=p.read_bytes();target.write_bytes(raw);hashes[str(rel).replace('\\','/')]=hashlib.sha256(raw).hexdigest()
        # Bounded diagnostics only; never include credential/config directories.
        for log in sorted((root/'logs').glob('server-*.log'),key=lambda p:p.stat().st_mtime)[-3:]:
            target=folder/'logs'/log.name;target.parent.mkdir(exist_ok=True)
            with log.open('rb') as f:
                f.seek(max(0,log.stat().st_size-200_000));raw=f.read()
            target.write_text(scrub(raw.decode('utf-8',errors='replace')),encoding='utf-8')
        # Configuration lives in source; credential files are never exported.
        try:
            commit=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=5).stdout.strip()
        except (OSError,subprocess.TimeoutExpired):commit='UNAVAILABLE'
        dump(folder/'metadata.json',dict(export_version='AUDIT_V3_1',exported_utc=now.isoformat(),
             requested_start_thai=start.isoformat(),end_exclusive_thai=end.isoformat(),context_start_thai=context_start.isoformat(),
             git_commit=commit,source_sha256=hashes,event_counts_in_requested_window=counts,
             research_status=research_status,notes=[
                 'Decision and research databases captured separately using SQLite backup; see observer cursor.',
                 'engine_state_at_export is current state, not state at requested historical end.',
                 'events.jsonl includes one prior context day. Filter by requested window for trade counts.',
                 'All results PAPER_ONLY and sampled, not broker fills or monetary profit.',
                 'No credentials, raw runtime database, browser sessions or .env files included.']))
        (folder/'START_HERE_TH.txt').write_text('เริ่มที่ metadata.json แล้วอ่าน trades.csv / trades.json\n'
              'events.jsonl เป็นข้อมูลตัดสินใจ; post_sl_research.json และ decision_explanations.jsonl เป็นข้อมูลวิเคราะห์แยกส่วน\n'
              'ตรวจ research_progress.json ว่า observer ตามข้อมูลทันหรือไม่ ช่วงข้อมูลขาดไม่เท่ากับยืนยันว่าไม่แตะ TP\n'
              'มีข้อมูลประกอบก่อนวันเริ่มหนึ่งวัน ห้ามนำมานับรวมผลโดยไม่กรองเวลา\n',encoding='utf-8')
        with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob('*')):
                if p.is_file() and p.suffix not in ('.sqlite3','-wal','-shm'):z.write(p,p.relative_to(folder).as_posix())
        with zipfile.ZipFile(destination) as z:
            if z.testzip():raise RuntimeError('ZIP validation failed')
    return destination

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    today=datetime.now(THAI).strftime('%Y-%m-%d')
    parser.add_argument('--from',dest='start',default=today)
    parser.add_argument('--to',dest='end',default=today)
    parser.add_argument('--output',type=Path)
    a=parser.parse_args();print(export_audit(a.project,a.start,a.end,a.output))

if __name__=='__main__':main()
