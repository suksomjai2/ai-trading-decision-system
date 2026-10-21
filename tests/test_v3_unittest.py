"""No dependency installation needed: python -m unittest discover -s tests -p test_v3_unittest.py"""
import copy
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import datetime,timezone
from core.market_state import MarketState
from data_feed.research_observer import ResearchObserver,build_research_report
from data_feed.audit_export import export_audit
from data_feed.state_store import StateStore

def feed(now=1800000030.0,bid=100.0,ask=100.1):
    histories={}
    for tf,period in dict(H4=14400,H1=3600,M15=900,M5=300).items():
        last=int(now//period)*period-period
        histories[tf]=[dict(time=last-(79-i)*period,open=80+i*.25-.1,
                            high=80+i*.25+.5,low=80+i*.25-.5,close=80+i*.25,volume=100) for i in range(80)]
    return dict(schema_version=2,symbol='XAUUSD',bar_clock='UTC',quote=dict(time=now,bid=bid,ask=ask),candles=histories)

class V3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=StateStore(self.root/'runtime/engine.sqlite3')
        self.observer=ResearchObserver(self.store.path,self.root/'runtime/research.sqlite3')
    def tearDown(self):self.tmp.cleanup()

    def append(self,kind,stamp,**e):
        event=dict(time=stamp,kind=kind,**e)
        with self.store.connect() as c:
            c.execute('INSERT INTO events(symbol,time,kind,value) VALUES(?,?,?,?)',('XAUUSD',stamp,kind,json.dumps(event)))

    def sl(self,side='BUY',stamp=1980,trade_id='t1'):
        t=dict(id=trade_id,side=side,entry_time=1900,entry_price=101 if side=='BUY' else 99,
               tp=108 if side=='BUY' else 92,sl=100,
               exit_time=stamp,exit_observed_price=99.9 if side=='BUY' else 100.1,
               outcome='SL_TOUCHED',policy='CONTEXTUAL_REACTION_V3')
        self.append('EXIT',stamp,trade=t);return t

    def read(self,trade_id='t1'):
        with self.observer.connect() as c:return json.loads(c.execute('SELECT value FROM post_sl WHERE trade_id=?',(trade_id,)).fetchone()[0])

    def test_buy_after_sl_tp_and_pre_exit_range_excluded(self):
        self.sl();self.append('EVALUATION',1980,bid=99.9,ask=100)
        for stamp in range(1985,2101,5):self.append('EVALUATION',stamp,bid=108.1 if stamp==2040 else 100.2,ask=108.2 if stamp==2040 else 100.3)
        self.append('CLOSED_CONTEXT',2100,recent_candles={'M5':[dict(time=1800,high=200,low=1,close=100.2)]})
        self.observer.poll(now=2140);v=self.read()
        self.assertAlmostEqual(v['mfe_after_exit'],8.2)
        self.assertEqual(v['mae_after_exit'],0)
        self.assertEqual(v['first_tp_time'],2040)
        self.assertEqual(v['exact_bid_candle_close'],100.2)
        self.assertEqual(v['classification'],'RETURNED_INSIDE_SL_AT_LAST_QUOTE')

    def test_sell_uses_ask_not_bid(self):
        self.sl('SELL')
        for stamp in range(1985,2101,5):self.append('EVALUATION',stamp,bid=91.9,ask=92.2)
        self.append('CLOSED_CONTEXT',2100,recent_candles={'M5':[dict(time=1800,close=91.9,high=120,low=80)]})
        self.observer.poll(now=2140);v=self.read()
        self.assertFalse(v['tp_observed_after_sl']);self.assertAlmostEqual(v['mfe_after_exit'],7.9)
        self.assertEqual(v['close_side_of_sl'],'UNKNOWN_HISTORICAL_ASK')

    def test_gap_does_not_claim_complete_or_tp_absence(self):
        self.sl();self.append('EVALUATION',2095,bid=99,ask=99.1)
        self.observer.poll(now=2140);v=self.read()
        self.assertEqual(v['coverage'],'INCOMPLETE')
        self.assertEqual(v['classification'],'INSUFFICIENT_DATA')
        self.assertEqual(v['tp_result'],'NOT_OBSERVED_NOT_PROVEN_ABSENT')

    def test_no_quote_after_deadline_is_included(self):
        self.sl();self.append('EVALUATION',2101,bid=110,ask=110.1)
        self.observer.poll(now=2140);v=self.read()
        self.assertFalse(v['tp_observed_after_sl']);self.assertEqual(v['quote_count'],0)

    def test_restart_duplicates_and_same_boundary(self):
        self.sl(stamp=2100);self.observer.poll(now=2101)
        self.assertEqual(self.read()['deadline'],2400)
        restart=ResearchObserver(self.store.path,self.observer.path);restart.poll(now=2101)
        self.append('EXIT',2100,trade=self.sl(stamp=2100))
        restart.poll(now=2101)
        with restart.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM post_sl').fetchone()[0],1)

    def test_overlapping_trades_independent(self):
        self.sl(trade_id='a');self.sl('SELL',stamp=1990,trade_id='b')
        self.append('EVALUATION',1995,bid=100.5,ask=100.7);self.observer.poll(now=2000)
        self.assertEqual(self.read('a')['quote_count'],1);self.assertEqual(self.read('b')['quote_count'],1)
        self.assertGreater(self.read('a')['mfe_after_exit'],0);self.assertGreater(self.read('b')['mae_after_exit'],0)

    def test_observer_never_changes_decision_database(self):
        self.sl();before=self.store.path.read_bytes();self.observer.poll(now=2140)
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_decision_with_observer_on_off_identical(self):
        engine=MarketState();without={};with_observer={}
        for i in range(8):
            payload=feed(now=1800000030+i*5,bid=100+i*.1,ask=100.1+i*.1)
            without,a,ae=engine.process_hybrid(without,copy.deepcopy(payload))
            with_observer,b,be=engine.process_hybrid(with_observer,copy.deepcopy(payload))
            for event in be:self.append(event['kind'],event['time'],**{k:v for k,v in event.items() if k not in ('kind','time')})
            self.observer.poll(now=payload['quote']['time'])
            self.assertEqual(without,with_observer);self.assertEqual(a,b);self.assertEqual(ae,be)

    def test_observer_failure_does_not_touch_decision(self):
        engine=MarketState();state,a,ae=engine.process_hybrid({},feed())
        self.observer.audit_path=self.root/'missing.sqlite3'
        with self.assertRaises(sqlite3.Error):self.observer.poll(now=2000)
        _,b,be=engine.process_hybrid({},feed())
        self.assertEqual(a,b);self.assertEqual(ae,be)

    def test_zip_export_is_readonly_and_contains_research(self):
        self.sl();self.observer.poll(now=2140)
        (self.root/'.env').write_text('SECRET=never-export')
        before=self.store.path.read_bytes()
        path=export_audit(self.root,'1970-01-01','1970-01-01',self.root/'exports',now=datetime.fromtimestamp(3600,timezone.utc))
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip());self.assertIn('post_sl_research.json',z.namelist())
            self.assertNotIn('.env',z.namelist());self.assertFalse(any(x.endswith('.sqlite3') for x in z.namelist()))
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_v3_policy_and_chase(self):
        self.assertIn(MarketState.HYBRID_CONFIG['max_chase_atr'],(0.40,0.50))
        _,result,_=MarketState().process_hybrid({},feed())
        self.assertIn(result['diagnostics']['policy'],('CONTEXTUAL_REACTION_V3','CONTEXTUAL_REACTION_V4'))

    def test_existing_v2_open_trade_keeps_original_tp_sl_and_policy(self):
        payload=feed();now=payload['quote']['time']
        trade=dict(id='existing-v2',side='BUY',entry_time=now-10,entry_price=100.1,
                   tp=108,sl=95,mfe_observed=0,coverage_gap=False,policy='CONTEXTUAL_REACTION_V2')
        state=dict(last_quote_time=now-5,last_mid=100,trade=trade)
        updated,result,_=MarketState().process_hybrid(state,payload)
        self.assertEqual(result['state'],'MANAGE')
        self.assertEqual(updated['trade']['tp'],108);self.assertEqual(updated['trade']['sl'],95)
        self.assertEqual(updated['trade']['policy'],'CONTEXTUAL_REACTION_V2')

    def test_only_price_reaction_pending_setup_loses_retention(self):
        payload=feed();now=payload['quote']['time']
        for basis,cancelled in [('PRICE_REACTION',True),('M15_EMA_PULLBACK',False)]:
            engine=MarketState()
            engine.select_setup=lambda *a,**k:(None,'NO_M15_STRUCTURAL_SETUP',None,'NONE')
            setup=dict(id='pending',side='BUY',created=now-20,expires=now+3600,
                       zone_low=99,zone_high=101,sl=95,zone_seen=False,late_chase_recorded=False,
                       confirmation_after=payload['candles']['M5'][-1]['time'],mode='TRANSITION',
                       zone_basis=basis,source_m15=payload['candles']['M15'][-1]['time'])
            state=dict(last_quote_time=now-5,last_mid=100,setup=setup)
            updated,result,_=engine.process_hybrid(state,payload)
            self.assertEqual(result['state']=='CANCEL',cancelled)
            self.assertEqual(updated.get('setup') is None,cancelled)

if __name__=='__main__':unittest.main()
