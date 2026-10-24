"""V5.1 decision boundary, audit isolation, lifecycle and dated-export tests."""
import copy,json,sqlite3,unittest,zipfile
from unittest.mock import patch
from datetime import datetime,timezone
import test_v3_unittest as legacy
import test_v4_unittest as old
from core.market_state import MarketState
from data_feed.setup_lifecycle import export_history,build_lifecycle_report
from data_feed.audit_export import export_audit

class V5Tests(legacy.V3Tests):
    def eligible(self,side='BUY',trend='NEUTRAL',basis='M15_EMA_PULLBACK',candidate='BUY',reason='M15_EXISTING_SETUP'):
        eng,state,p=old.V4Tests.eligible(self,side,trend)
        state['setup']['zone_basis']=basis
        def select(f,h,q,m,e):
            e.update(m15_candidate=candidate,m5_candidate=side,selection_reason=reason)
            return side,'TRANSITION',100,basis
        eng.select_setup=select
        b=p['candles']['M5'][-1];trigger=b['high'] if side=='BUY' else b['low'];now=p['quote']['time']
        state['research_trigger_hold']=dict(key=('eligible',b['time'],trigger),first_time=now-5,last_time=now-5)
        return eng,state,p

    def test_v3_policy_and_chase(self):
        self.assertEqual(MarketState.HYBRID_CONFIG['max_chase_atr'],.45)
        _,r,_=MarketState().process_hybrid({},legacy.feed())
        self.assertEqual(r['diagnostics']['policy'],'CONTEXTUAL_REACTION_V5')

    def test_continuation_gate_matrix(self):
        for side in ('BUY','SELL'):
            for candidate in (None,'BUY','SELL'):
                eng,state,p=self.eligible(side,basis='BROKEN_M5_LEVEL_LIVE_CONFIRMED',candidate=candidate,reason='M5_BROKEN_LEVEL_HELD')
                after,r,ev=eng.process_hybrid(state,p)
                self.assertEqual(r['state']=='ENTRY',candidate==side)
                if candidate!=side:
                    self.assertEqual(r['reason'],'CONTINUATION_WITHOUT_M15_CANDIDATE')
                    self.assertIsNone(after['setup'])

    def test_price_reaction_without_m15_candidate_not_blanket_blocked(self):
        eng,state,p=self.eligible(basis='PRICE_REACTION',candidate=None,reason='SUPPORT_RECLAIM')
        after,r,ev=eng.process_hybrid(state,p)
        self.assertEqual(r['state'],'ENTRY')
        e=next(x for x in ev if x['kind']=='ENTRY')
        self.assertEqual(e['setup']['zone_basis'],'PRICE_REACTION')
        self.assertEqual(e['audit_evidence']['selection']['selection_reason'],'SUPPORT_RECLAIM')
        self.assertEqual(e['audit_evidence']['entry_checks']['stop_price'],after['trade']['sl'])
        self.assertNotIn('audit_evidence',after['trade'])

    def test_gate_runs_only_after_entry_checks(self):
        eng,state,p=self.eligible(basis='BROKEN_M5_LEVEL_LIVE_CONFIRMED',candidate=None,reason='M5_BROKEN_LEVEL_HELD')
        p['candles']['M5'][-1]['close']=98.95
        _,r,ev=eng.process_hybrid(state,p)
        self.assertEqual(r['reason'],'WAIT_FOR_LIVE_TRIGGER')
        self.assertFalse(any(x.get('reason')=='CONTINUATION_WITHOUT_M15_CANDIDATE' for x in ev))

    def test_requires_two_trigger_quotes(self):
        eng,state,p=self.eligible();state.pop('research_trigger_hold')
        state,r,ev=eng.process_hybrid(state,p);self.assertEqual(r['reason'],'WAIT_FOR_LIVE_TRIGGER')
        p['quote']['time']+=5
        state,r,ev=eng.process_hybrid(state,p);self.assertEqual(r['state'],'ENTRY')

    def test_two_quotes_survive_actual_sqlite_json_roundtrip(self):
        eng,state,p=self.eligible();state.pop('research_trigger_hold')
        with self.store.connect() as c:
            c.execute('INSERT INTO engine_state VALUES(?,?)',('XAUUSD',json.dumps(state)))
        first=self.store.process('XAUUSD',lambda persisted:eng.process_hybrid(persisted,p))
        self.assertEqual(first['reason'],'WAIT_FOR_LIVE_TRIGGER')
        with self.store.connect() as c:
            persisted=json.loads(c.execute('SELECT value FROM engine_state').fetchone()[0])
        self.assertIsInstance(persisted['research_trigger_hold']['key'],list)
        p['quote']['time']+=5
        second=self.store.process('XAUUSD',lambda persisted:eng.process_hybrid(persisted,p))
        self.assertEqual(second['state'],'ENTRY')

    def test_existing_v4_trade_not_repriced_or_blocked(self):
        eng,state,p=self.eligible(basis='BROKEN_M5_LEVEL_LIVE_CONFIRMED',candidate=None)
        state.pop('setup');state['trade']=dict(id='old',side='BUY',entry_time=p['quote']['time']-5,entry_price=100.1,tp=108.1,sl=95,mfe_observed=0,mae_observed=0,coverage_gap=False,policy='CONTEXTUAL_REACTION_V4')
        expected=copy.deepcopy(state['trade']);state,r,ev=eng.process_hybrid(state,p)
        self.assertEqual(r['state'],'MANAGE')
        for k in ['id','side','entry_price','tp','sl','policy']:self.assertEqual(state['trade'][k],expected[k])

    def lifecycle_events(self):
        audit=dict(release_policy='CONTEXTUAL_REACTION_V5',selection=dict(selection_reason='LIVE_FAILED_DOWN_BREAK'),known_at=1000)
        setup=dict(id='trace',side='BUY',zone_basis='PRICE_REACTION',zone_low=99,zone_high=101,sl=95)
        self.append('ARMED',1000,setup=setup,audit_evidence=audit)
        self.append('EVALUATION',1100,setup_id='trace',bid=100,ask=100.1,stage='ARMED',reason='WAIT_FOR_LIVE_TRIGGER',candidate_side='BUY',diagnostics=dict(policy='CONTEXTUAL_REACTION_V5',zone_basis='M15_EMA_PULLBACK',selection=dict(selection_reason='M15_EXISTING_SETUP')))
        self.append('ENTRY',2600,setup=setup,trade=dict(id='trace',side='BUY',entry_time=2600,entry_price=101,tp=109,sl=97),audit_evidence={**audit,'known_at':2600,'selection':dict(selection_reason='M15_EXISTING_SETUP')})
        self.append('CANCEL',4000,setup=setup,reason='test-future',audit_evidence=audit)
        self.observer.poll(now=5000)

    def test_origin_current_entry_separate_and_restart_safe(self):
        self.lifecycle_events()
        report=build_lifecycle_report(self.observer.path,5000)
        item=report['items'][0]
        self.assertEqual(item['origin']['evidence']['selection']['selection_reason'],'LIVE_FAILED_DOWN_BREAK')
        self.assertEqual(item['entry']['evidence']['selection']['selection_reason'],'M15_EXISTING_SETUP')
        with self.observer.connect() as c:before=c.execute('SELECT COUNT(*) FROM setup_lifecycle_events').fetchone()[0]
        self.observer.poll(now=5001)
        with self.observer.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM setup_lifecycle_events').fetchone()[0],before)

    def test_historical_export_keeps_origin_and_excludes_future(self):
        self.lifecycle_events()
        with self.observer.connect() as c:
            summaries,events=export_history(c,1050,3000)
        self.assertEqual(summaries[0]['status'],'OPEN')
        self.assertEqual(events[0]['time'],1000)
        self.assertTrue(all(e['time']<3000 for e in events))
        path=export_audit(self.root,'1970-01-01','1970-01-01',self.root/'out',now=datetime.fromtimestamp(3000,timezone.utc))
        with zipfile.ZipFile(path) as z:
            self.assertTrue(path.name.startswith('AITrading-S5B-Audit-'))
            self.assertEqual(json.loads(z.read('setup_lifecycle.json'))[0]['status'],'OPEN')
            self.assertIn('continuation_entry_vetoes.json',z.namelist())

    def test_lifecycle_failure_cannot_change_decisions(self):
        eng=MarketState();_,a,events=eng.process_hybrid({},legacy.feed())
        for e in events:self.append(e['kind'],e['time'],**{k:v for k,v in e.items() if k not in ('kind','time')})
        with patch('data_feed.setup_lifecycle.ingest',side_effect=RuntimeError('research fault')):
            with self.assertRaises(RuntimeError):self.observer.poll()
        _,b,_=eng.process_hybrid({},legacy.feed());self.assertEqual(a,b)

    def test_inherited_setup_origin_is_unknown(self):
        self.append('EVALUATION',1100,setup_id='inherited',bid=100,ask=100.1,stage='ARMED',reason='WAIT',candidate_side='BUY',diagnostics=dict(policy='CONTEXTUAL_REACTION_V5',selection={}))
        self.observer.poll(now=1101)
        item=build_lifecycle_report(self.observer.path,1101)['items'][0]
        self.assertIsNone(item['origin']);self.assertEqual(item['origin_status'],'UNKNOWN_PRE_V5')

if __name__=='__main__':unittest.main()
