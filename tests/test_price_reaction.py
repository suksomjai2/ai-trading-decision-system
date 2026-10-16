"""Directional invariants, not profitability assertions."""
import pytest
from core.feature_engine import FeatureEngine
from core.market_state import MarketState
from test_hybrid import feed, position


def breakout(buy=False):
    p=feed(bid=99.4,ask=99.5)
    for b in p['candles']['M5'][-7:-1]:
        b.update(open=100,high=100.2,low=99.8,close=100)
    p['candles']['M5'][-1].update(open=100.1,high=100.15,low=99.5,close=99.55)
    if buy:
        for bars in p['candles'].values():
            for b in bars:
                o,h,l,c=[b[k] for k in ('open','high','low','close')]
                b.update(open=200-o,high=200-l,low=200-h,close=200-c)
        p['quote'].update(bid=100.6,ask=100.7)
    return p


def choose(p,memory=None):
    f={tf:FeatureEngine().calculate_history(bs) for tf,bs in p['candles'].items()}
    e={}
    result=MarketState.select_setup(f,p['candles'],p['quote'],memory,e)
    return result,e


@pytest.mark.parametrize('buy',[False,True])
def test_break_bias_survives_candle_extreme_recross_but_not_level_reclaim(buy):
    p=breakout(buy); memory={}
    assert choose(p,memory)[0][0]==('BUY' if buy else 'SELL')
    p['quote'].update(bid=100.3 if buy else 99.7,ask=100.4 if buy else 99.8)
    result,e=choose(p,memory)
    assert result[0]==('BUY' if buy else 'SELL')
    assert e['selection_reason']=='M5_BROKEN_LEVEL_HELD'
    p['quote'].update(bid=99.5 if buy else 100.5,ask=99.6 if buy else 100.6)
    result,e=choose(p,memory)
    assert result[0]==('SELL' if buy else 'BUY')
    assert e['selection_reason'].startswith('LIVE_FAILED_')


@pytest.mark.parametrize('buy',[False,True])
def test_large_candle_failure_needs_no_shrinking_candles_or_new_close(buy):
    p=breakout(buy); b=p['candles']['M5'][-1]
    if buy:
        b.update(open=99.8,low=99.7,high=106,close=105.9)
        p['quote'].update(bid=99.6,ask=99.7)
    else:
        b.update(open=100.2,high=100.3,low=94,close=94.1)
        p['quote'].update(bid=100.4,ask=100.5)
    result,e=choose(p)
    assert result[0]==('SELL' if buy else 'BUY')
    assert e['reaction_candidate'] and e['additional_wait'] is False


@pytest.mark.parametrize('buy',[False,True])
def test_level_rejection_adds_candidate_without_htf_agreement(buy):
    p=breakout(not buy); b=p['candles']['M5'][-1]
    if buy:
        b.update(open=99.9,low=98.8,high=100.2,close=100.15)
        p['quote'].update(bid=100.15,ask=100.25)
    else:
        b.update(open=100.1,low=99.8,high=101.2,close=99.85)
        p['quote'].update(bid=99.85,ask=99.95)
    result,e=choose(p)
    assert result[0]==('BUY' if buy else 'SELL')
    assert e['selection_reason']==('SUPPORT_RECLAIM' if buy else 'RESISTANCE_REJECTION')


def test_no_levels_or_nearby_resistance_does_not_veto_existing_buy():
    p=feed(); f={tf:FeatureEngine().calculate_history(bs) for tf,bs in p['candles'].items()}
    reference=MarketState.select_setup(f,p['candles'],p['quote'])
    for tf in ('M15','M5'):
        f[tf]['price_action']['support']=[]; f[tf]['price_action']['resistance']=[]
    assert MarketState.select_setup(f,p['candles'],p['quote'])==reference
    f['M5']['price_action']['resistance']=[{'price':100.4,'touches':4}]
    assert MarketState.select_setup(f,p['candles'],p['quote'])==reference


def test_contracting_green_candle_does_not_force_sell():
    p=feed(bid=101,ask=101.1)
    p['candles']['M5'][-2].update(open=98,low=97.9,high=100.3,close=100.2)
    p['candles']['M5'][-1].update(open=100.2,low=100.1,high=100.8,close=100.7)
    assert choose(p)[0][0]=='BUY'


def test_manage_uses_candidate_not_neutral_h4_and_preserves_open_trade():
    p=breakout()
    for b in p['candles']['H4']:
        b.update(open=100,high=100.5,low=99.5,close=100)
    s,out,events=MarketState().process_hybrid(position(sl=95,tp=108),p)
    assert out['direction']=='NEUTRAL'
    assert out['reason']=='OPPOSING_BIAS_NO_REVERSE'
    assert (s['trade']['side'],s['trade']['sl'],s['trade']['tp'])==('BUY',95,108)
    assert not any(e['kind']=='ENTRY' for e in events)
    assert s['trade']['mae_observed']>0


def test_equal_bases_and_pivots_use_only_already_closed_neighbours():
    bars=feed()['candles']['M5']
    for b in bars:b.update(open=100,high=101,low=99,close=100)
    for i in (-8,-4):bars[i]['low']=97
    p=FeatureEngine.price_action(bars,2)
    assert p['swing_low']=='EQUAL_LOW'
    assert any(x['touches']==2 for x in p['support'])
    bars[-1]['low']=90
    assert all(x['price']!=90 for x in FeatureEngine.price_action(bars,2)['support'])
