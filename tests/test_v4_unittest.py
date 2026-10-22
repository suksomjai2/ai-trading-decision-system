"""V4 strategy and isolation tests; existing Python, no dependencies."""
import copy,json,unittest,zipfile
from datetime import datetime,timezone
from types import SimpleNamespace
import test_v3_unittest as legacy
from core.market_state import MarketState
from core.feature_engine import FeatureEngine
from data_feed.audit_export import export_audit

class V4Tests(legacy.V3Tests):
    def eligible(self,side,trend):
        p=legacy.feed(bid=100.3 if side=='BUY' else 99.7,ask=100.4 if side=='BUY' else 99.8)
        now=p['quote']['time'];buy=side=='BUY'
        p['candles']['M5'][-1].update(open=99 if buy else 101,high=100.2 if buy else 101.1,
                                    low=98.9 if buy else 99.8,close=100.1 if buy else 99.9)
        for b in p['candles']['H1']:b.update(high=max(b['high'],110),low=min(b['low'],90))
        features={tf:FeatureEngine().calculate_history(bs) for tf,bs in p['candles'].items()}
        features['M15'].update(direction=trend,atr14=2.)
        features['H4']['direction']=features['H1']['direction']='DOWN' if buy else 'UP'
        eng=MarketState();eng.feature_engine=SimpleNamespace(calculate_history=lambda bs:features[next(tf for tf,v in p['candles'].items() if v is bs)])
        eng.select_setup=lambda *a,**k:(side,'COUNTERTREND',100,'M15_EMA_PULLBACK')
        setup=dict(id='eligible',side=side,created=now-10,expires=now+3600,
                   source_bar=p['candles']['H1'][-1]['time'],source_m15=p['candles']['M15'][-1]['time'],
                   zone_low=98 if buy else 100,zone_high=100 if buy else 102,sl=99 if buy else 101,
                   zone_seen=True,zone_seen_time=now-400,confirmation_after=now-1000,
                   late_chase_recorded=False,zone_basis='M15_EMA_PULLBACK',mode='COUNTERTREND')
        state=dict(last_quote_time=now-5,last_mid=100,setup=setup)
        b=p['candles']['M5'][-1]
        state['research_trigger_hold']=dict(key=('eligible',b['time'],b['high'] if buy else b['low']),first_time=now-5,last_time=now-5)
        return eng,state,p

    def test_m15_matrix_both_sides(self):
        for side in ('BUY','SELL'):
            for trend in ('UP','DOWN','NEUTRAL'):
                with self.subTest(side=side,trend=trend):
                    eng,state,p=self.eligible(side,trend);after,result,events=eng.process_hybrid(state,p)
                    blocked=(side=='BUY' and trend=='DOWN') or (side=='SELL' and trend=='UP')
                    if blocked:
                        self.assertEqual(result['reason'],'M15_TREND_AGAINST_ENTRY')
                        self.assertIsNone(after['setup']);self.assertFalse(any(e['kind']=='ENTRY' for e in events))
                        cancel=next(e for e in events if e['kind']=='CANCEL')
                        self.assertEqual(cancel['m15_direction'],trend);self.assertEqual(cancel['candidate_side'],side)
                    else:
                        self.assertEqual(result['state'],'ENTRY');self.assertEqual(after['trade']['side'],side)
                        self.assertFalse(result['diagnostics']['higher_timeframe_veto'])

    def test_check_only_when_ready_to_enter(self):
        eng,state,p=self.eligible('BUY','DOWN');p['candles']['M5'][-1].update(open=100.1,close=99.9)
        _,result,events=eng.process_hybrid(state,p)
        self.assertEqual(result['reason'],'WAIT_FOR_LIVE_TRIGGER')
        self.assertFalse(any(e.get('reason')=='M15_TREND_AGAINST_ENTRY' for e in events))

    def test_v3_open_position_not_cancelled_by_new_veto(self):
        eng,_,p=self.eligible('BUY','DOWN');now=p['quote']['time']
        trade=dict(id='inherited',side='BUY',entry_time=now-10,entry_price=100.1,
                   sl=95,tp=108,mfe_observed=0,mae_observed=.1,coverage_gap=False,policy='CONTEXTUAL_REACTION_V3')
        updated,result,events=eng.process_hybrid(dict(last_quote_time=now-5,last_mid=100,trade=trade),p)
        self.assertEqual(result['state'],'MANAGE')
        for key in ('sl','tp','entry_price','entry_time','policy'):self.assertEqual(updated['trade'][key],trade[key])
        self.assertFalse(any(e.get('reason')=='M15_TREND_AGAINST_ENTRY' for e in events))

    def test_full_m15_direction_and_neutral(self):
        up=legacy.feed()['candles']['M15']
        down=[{**b,'open':200-b['open'],'high':200-b['low'],'low':200-b['high'],'close':200-b['close']} for b in up]
        neutral=copy.deepcopy(up)
        for b in neutral[-10:]:b.update(open=100,high=100.5,low=99.5,close=100)
        self.assertEqual(FeatureEngine().calculate_history(up)['direction'],'UP')
        self.assertEqual(FeatureEngine().calculate_history(down)['direction'],'DOWN')
        self.assertEqual(FeatureEngine().calculate_history(neutral)['direction'],'NEUTRAL')

    def test_v4_policy_and_chase(self):
        eng,state,p=self.eligible('BUY','NEUTRAL');_,result,_=eng.process_hybrid(state,p)
        self.assertIn(result['diagnostics']['policy'],('CONTEXTUAL_REACTION_V4','CONTEXTUAL_REACTION_V5'))
        self.assertIn(eng.HYBRID_CONFIG['max_chase_atr'],(.45,.50))

    def test_export_vetoes_and_preserves_db_and_photo(self):
        self.append('CANCEL',1980,reason='M15_TREND_AGAINST_ENTRY',candidate_side='SELL',m15_direction='UP')
        before=self.store.path.read_bytes()
        photo=self.root/'assets/dashboard_photo.jpeg';photo.parent.mkdir();photo.write_bytes(b'original-photo-test')
        path=export_audit(self.root,'1970-01-01','1970-01-01',self.root/'out',now=datetime.fromtimestamp(3600,timezone.utc))
        self.assertTrue(path.name.startswith('AITrading-V5-Audit-'))
        with zipfile.ZipFile(path) as z:
            self.assertEqual(len(json.loads(z.read('entry_vetoes.json'))),1)
            meta=json.loads(z.read('metadata.json'));self.assertEqual(meta['export_version'],'AUDIT_V5_1')
            self.assertEqual(meta['m15_entry_veto_count'],1)
        self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(photo.read_bytes(),b'original-photo-test')

if __name__=='__main__':unittest.main()
