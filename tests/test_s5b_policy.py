import json

import pytest

from core.session_bias_policy import (POLICY, SessionBiasS5B, pullback_signal, range_signal,
                                      session_bias)
from data_feed.state_store import StateStore
from tests.test_hybrid import NOW, feed

# NOW is 15:00:30 Bangkok (outside both sessions).
ASIA = NOW - 6 * 3600          # 09:00:30
NY = NOW + 5 * 3600            # 20:00:30
LATE = NOW + 13 * 3600         # 04:00:30


def test_session_windows_bangkok():
    assert session_bias(ASIA) == ('ASIA', 'BUY')
    assert session_bias(NY) == ('NY', 'SELL')
    assert session_bias(NOW) == (None, None) and session_bias(LATE) == (None, None)
    assert session_bias(NY + 5.5 * 3600) == ('NY', 'SELL')                     # 01:30 belongs to NY
    assert session_bias(NY + 6 * 3600 - 30) == (None, None)                     # 02:00 closes NY
    assert session_bias(ASIA - 2 * 3600 - 30) == ('ASIA', 'BUY')               # 07:00 opens Asia


def patch(policy, payload, h1=(True, True), m15=(True, False), ema=None, atr=None):
    """Real features from the payload, with chosen closed-bar trend checks / EMA / ATR."""
    original = policy.feature_engine.calculate_history
    c = payload['candles']

    def patched(bars):
        f = original(bars)
        if bars is c['H1']:
            f = dict(f, direction_checks=dict(f['direction_checks'], ema20_above_ema50=h1[0], ema20_rising=h1[1]))
        if bars is c['M15']:
            f = dict(f, direction_checks=dict(f['direction_checks'], ema20_above_ema50=m15[0], ema20_rising=m15[1]))
            if ema is not None:
                f['ema20'] = ema
            if atr is not None:
                f['atr14'] = atr
        return f
    policy.feature_engine.calculate_history = patched


def ready_state(payload):
    state = SessionBiasS5B.migrate({})
    state['signal']['last_m5'] = payload['candles']['M5'][-2]['time']        # this payload brings a new M5 bar
    return state


def buy_pullback_payload(now, bid=100.3, ask=100.4):
    p = feed(now=now, bid=bid, ask=ask)
    p['candles']['M5'][-1].update(open=99.8, high=100.5, low=99.6, close=100.3)
    return p


def sell_pullback_payload(now, bid=99.0, ask=99.1):
    p = feed(now=now, bid=bid, ask=ask)
    p['candles']['M5'][-1].update(open=99.9, high=100.6, low=98.8, close=98.9)
    return p


def kinds(events):
    return [e['kind'] for e in events]


def test_pullback_and_range_signal_rules():
    f = {'H1': {'direction_checks': dict(ema20_above_ema50=True, ema20_rising=True)},
         'M15': {'atr14': 2.0, 'ema20': 99.6, 'direction_checks': dict(ema20_above_ema50=True, ema20_rising=False)}}
    c = buy_pullback_payload(ASIA)['candles']
    assert pullback_signal(f, c) == ('BUY', 2.0, 3.0, 'H1_PULLBACK')
    f['M15']['ema20'] = 97.0                                                  # never touched in the last 4 M5
    assert pullback_signal(f, c) is None
    f['H1']['direction_checks'] = dict(ema20_above_ema50=True, ema20_rising=False)
    assert pullback_signal(f, c) is None                                      # no H1 trend
    m15 = [dict(open=105, high=110, low=100, close=105)] * 21
    rc = {'M15': m15, 'M5': [dict(open=110, high=111, low=108.5, close=109)]}
    assert range_signal(f, rc) == ('SELL', pytest.approx(111.6), 105.0, 'RANGE_MID')
    f['M15']['atr14'] = 6.0                                                   # range 10 < 2 x ATR
    assert range_signal(f, rc) is None
    f['M15'].update(atr14=2.0, direction_checks=dict(ema20_above_ema50=True, ema20_rising=True))
    assert range_signal(f, rc) is None                                        # M15 trends


def test_asia_buy_pullback_entry_then_tp_on_later_bid():
    h = SessionBiasS5B()
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    state, out, events = h.process(ready_state(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['policy'] == POLICY and entry['side'] == 'BUY' and entry['entry_price'] == 100.4
    assert entry['sl'] == pytest.approx(98.4) and entry['tp'] == pytest.approx(103.4)
    assert entry['selection']['session'] == 'ASIA' and entry['mode'] == 'H1_PULLBACK'
    assert out['state'] == 'ENTRY' and out['diagnostics']['policy'] == POLICY and out['execution_mode'] == 'PAPER_ONLY'
    later = buy_pullback_payload(ASIA + 5, bid=103.4, ask=103.5)
    patch(h, later, ema=99.6, atr=2.0)
    state, out, events = h.process(state, later)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['id'] == entry['id'] and exit_['outcome'] == 'TP_TOUCHED' and exit_['exit_observed_price'] == 103.4
    assert out['state'] == 'EXIT' and state['book'] is None and state['trade'] is None


def test_stop_checked_first_and_no_exit_on_entry_quote():
    h = SessionBiasS5B()
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    state, out, events = h.process(ready_state(p), p)
    assert 'EXIT' not in kinds(events)
    later = buy_pullback_payload(ASIA + 40, bid=98.3, ask=98.4)
    patch(h, later, ema=99.6, atr=2.0)
    state, out, events = h.process(state, later)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['outcome'] == 'SL_TOUCHED' and exit_['coverage_gap'] is True   # >30 s between quotes


@pytest.mark.parametrize('now,expected', [(ASIA, 'SKIPPED_AGAINST_SESSION_BIAS'), (NOW, 'SKIPPED_OUTSIDE_SESSION')])
def test_sell_signal_filtered_in_asia_and_outside_sessions(now, expected):
    h = SessionBiasS5B()
    p = sell_pullback_payload(now)
    patch(h, p, h1=(False, False), ema=100.4, atr=2.0)
    state, out, events = h.process(ready_state(p), p)
    assert 'ENTRY' not in kinds(events) and state['book'] is None
    [skip] = [e for e in events if e['kind'] == 'S5B_SIGNAL_SKIPPED']
    assert skip['status'] == expected and skip['side'] == 'SELL'
    assert out['state'] == 'WAIT' and out['reason'] == expected


def test_ny_sell_pullback_is_taken():
    h = SessionBiasS5B()
    p = sell_pullback_payload(NY)
    patch(h, p, h1=(False, False), ema=100.4, atr=2.0)
    state, out, events = h.process(ready_state(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['side'] == 'SELL' and entry['entry_price'] == 99.0 and entry['selection']['session'] == 'NY'


def test_ny_range_fade_to_middle_exits_on_ask():
    h = SessionBiasS5B()
    p = feed(now=NY, bid=108.9, ask=109.0)
    for b in p['candles']['M15']:
        b.update(open=105, high=110, low=100, close=105)
    p['candles']['M5'][-1].update(open=110, high=111, low=108.5, close=109)
    patch(h, p, h1=(True, False), m15=(True, False), atr=2.0)
    state, out, events = h.process(ready_state(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['mode'] == 'RANGE_MID' and entry['side'] == 'SELL' and entry['tp'] == 105.0
    later = feed(now=NY + 5, bid=104.9, ask=105.0)
    later['candles'] = p['candles']
    state, out, events = h.process(state, later)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['outcome'] == 'TP_TOUCHED' and exit_['exit_observed_price'] == 105.0


def test_one_bar_one_evaluation_busy_and_first_bar_after_install():
    h = SessionBiasS5B()
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    state, out, events = h.process(SessionBiasS5B.migrate({}), p)            # first quote after install
    assert 'ENTRY' not in kinds(events) and state['signal']['last_m5'] == p['candles']['M5'][-1]['time']
    again = buy_pullback_payload(ASIA + 5)
    patch(h, again, ema=99.6, atr=2.0)
    state, out, events = h.process(state, again)                             # same closed bar: not re-evaluated
    assert 'ENTRY' not in kinds(events)
    state, out, events = h.process(ready_state(p), p)
    assert 'ENTRY' in kinds(events)
    nxt = buy_pullback_payload(ASIA + 300)                                   # next bar while busy
    for tf, bars in nxt['candles'].items():
        bars[-1]['time'] += 300
    patch(h, nxt, ema=99.6, atr=2.0)
    state, out, events = h.process(state, nxt)
    assert kinds(events).count('ENTRY') == 0 and out['state'] == 'MANAGE'


class StubEngine:
    def __init__(self, script):
        self.script = script

    def process_hybrid(self, state, payload):
        events = [dict(e, time=payload['quote']['time']) for e in self.script.pop(0)]
        f = {'H1': {'direction_checks': dict(ema20_above_ema50=True, ema20_rising=False)},
             'M15': {'atr14': 2.0, 'ema20': 100.0, 'direction_checks': dict(ema20_above_ema50=True, ema20_rising=False)}}
        value = {'decision': 'WAIT', 'state': 'WAIT', 'reason': 'X', 'diagnostics': {'policy': 'CONTEXTUAL_REACTION_V5'},
                 'timeframes': f, 'entry': {}, 'execution_mode': 'PAPER_ONLY'}
        events.append({'time': payload['quote']['time'], 'kind': 'EVALUATION', 'stage': 'WAIT', 'reason': 'X'})
        return dict(state, trade=None), value, events


def test_v5_open_trade_migrates_as_legacy_and_exits_with_v5():
    legacy = dict(id='XAUUSD:v5-open', side='BUY', entry_time=ASIA - 60, entry_price=100.0, tp=108.0, sl=96.0, rr=2.0,
                  mfe_observed=0.0, mae_observed=0.1, coverage_gap=False, policy='CONTEXTUAL_REACTION_V5')
    state = SessionBiasS5B.migrate({'trade': legacy, 'last_quote_time': ASIA - 5})
    assert state['book']['component'] == 'LEGACY' and state['trade']['id'] == 'XAUUSD:v5-open'
    assert state['v5']['trade']['id'] == 'XAUUSD:v5-open'
    h = SessionBiasS5B()
    h.engine = StubEngine([
        [{'kind': 'ENTRY', 'trade': dict(legacy, id='XAUUSD:v5-new')}],        # V5's own new entry: research only
        [{'kind': 'EXIT', 'trade': dict(legacy, outcome='TP_TOUCHED', exit_time=ASIA, exit_observed_price=108.1)}],
    ])
    p = feed(now=ASIA - 2)
    state, out, events = h.process(state, p)
    assert 'V5_CANDIDATE_ENTRY' in kinds(events) and 'ENTRY' not in kinds(events) and out['state'] == 'MANAGE'
    state, out, events = h.process(state, feed(now=ASIA))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['id'] == 'XAUUSD:v5-open' and exit_['tp'] == 108.0 and exit_['policy'] == 'CONTEXTUAL_REACTION_V5'
    assert state['book'] is None and SessionBiasS5B.migrate(state) is state


def test_duplicate_tick_and_storable_state(tmp_path):
    h = SessionBiasS5B()
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    store = StateStore(tmp_path / 'engine.sqlite3')
    first = store.process('XAUUSD', lambda s: h.process(ready_state(p) if not s else s, p))
    again = store.process('XAUUSD', lambda s: h.process(s, p))
    assert first['state'] == 'ENTRY' and again == first
    with store.connect() as c:
        entries = c.execute("SELECT COUNT(*) FROM events WHERE kind='ENTRY'").fetchone()[0]
        raw = c.execute('SELECT value FROM engine_state').fetchone()[0]
    assert entries == 1 and json.loads(raw)['s5b_version'] == 1 and json.loads(raw)['trade']['policy'] == POLICY


def test_daily_report_reads_open_and_closed_s5b_trade(tmp_path):
    from data_feed.trade_report import build_report
    h = SessionBiasS5B()
    store = StateStore(tmp_path / 'engine.sqlite3')
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    store.process('XAUUSD', lambda s: h.process(ready_state(p), p))
    report = build_report(store.path, ASIA + 1)
    [row] = report['trades']
    assert row['status'] == 'OPEN' and row['policy'] == POLICY and report['counts']['open_positions'] == 1
    later = buy_pullback_payload(ASIA + 5, bid=103.4, ask=103.5)
    patch(h, later, ema=99.6, atr=2.0)
    store.process('XAUUSD', lambda s: h.process(s, later))
    report = build_report(store.path, ASIA + 6)
    [row] = report['trades']
    assert row['status'] == 'TP_TOUCHED' and report['counts']['tp_observed'] == 1 and report['counts']['open_positions'] == 0


def test_s5b_policy_still_runs_standalone_with_store(tmp_path):
    """S5B is no longer the live policy (H1CON_AI_V1 is); it must stay usable for rollback."""
    h = SessionBiasS5B()
    p = buy_pullback_payload(ASIA)
    patch(h, p, ema=99.6, atr=2.0)
    store = StateStore(tmp_path / 'engine.sqlite3')
    out = store.process('XAUUSD', lambda s: h.process(ready_state(p), p))
    assert out['diagnostics']['policy'] == POLICY and out['diagnostics']['component_policy'] == 'CONTEXTUAL_REACTION_V5'
