import json

import pytest

from core import h1con_ai as H
from core.h1con_ai_policy import POLICY, H1ConAI, load_model
from data_feed.hybrid_feed import PERIODS
from data_feed.state_store import StateStore

NOW = 1800000030.0          # 15:00:30 Bangkok


def bars(tf, now, n=200, start=100.0, step=0.05):
    period = PERIODS[tf]
    last = int(now // period) * period - period
    out = []
    for i in range(n):
        c = start + i * step
        out.append(dict(time=last - (n - 1 - i) * period, open=c - 0.1, high=c + 0.6, low=c - 0.6, close=c, volume=100))
    return out


def payload(now=NOW, bid=110.0, ask=110.5, shift=0):
    p = dict(schema_version=2, symbol='XAUUSD', bar_clock='UTC', quote=dict(time=now, bid=bid, ask=ask),
             candles={tf: bars(tf, now) for tf in PERIODS})
    return p


class ConstModel:
    def __init__(self, p):
        self.p = p
        self.calls = []

    def proba(self, feats):
        assert list(feats) and set(H.FEATURES) <= set(feats)
        self.calls.append(feats)
        return self.p


def ready(p):
    state = H1ConAI.migrate({})
    state['signal']['last_m15'] = p['candles']['M15'][-2]['time']      # this payload brings a new M15 bar
    return state


def kinds(events):
    return [e['kind'] for e in events]


@pytest.fixture
def force_buy(monkeypatch):
    monkeypatch.setattr(H, 'signal', lambda h1, m15: 'BUY')


def test_signal_rules_follow_the_ea():
    h1 = [dict(time=i * 3600, open=100 + i * 0.1, high=100 + i * 0.1 + 0.3, low=100 + i * 0.1 - 0.3,
               close=100 + i * 0.1 + 0.05, volume=1) for i in range(200)]          # EMA50 > EMA100
    m15 = [dict(time=i * 900, open=200 - i * 0.05 + 0.02, high=200 - i * 0.05 + 0.3, low=200 - i * 0.05 - 0.3,
                close=200 - i * 0.05, volume=1) for i in range(197)]               # steady decline -> RSI low
    b2 = dict(time=197 * 900, open=190.2, high=190.3, low=189.6, close=189.7, volume=1)     # red pullback
    b1 = dict(time=198 * 900, open=189.7, high=190.6, low=189.6, close=190.5, volume=1)     # green, > b2 open
    m15_ok = m15 + [b2, b1]
    assert H.signal(h1, m15_ok) == 'BUY'
    weak = dict(b1, close=190.1)                                                     # does not close above b2 open
    assert H.signal(h1, m15 + [b2, weak]) is None
    h1_down = [dict(b, close=300 - i * 0.1, open=300 - i * 0.1 + 0.05, high=300 - i * 0.1 + 0.3, low=300 - i * 0.1 - 0.3)
               for i, b in enumerate(h1)]
    assert H.signal(h1_down, m15_ok) is None                                         # trend down: BUY setup ignored


def test_tree_model_evaluation():
    spec = dict(features=['x_side'], baseline=0.0,
                trees=[[[False, 0, 0, 0.5, True, 1, 2], [True, -1.0, 0, 0, False, 0, 0], [True, 1.0, 0, 0, False, 0, 0]]])
    m = H.TreeModel(spec)
    assert m.proba({'x_side': 0}) == pytest.approx(1 / (1 + 2.718281828 ** 1), rel=1e-6)
    assert m.proba({'x_side': 1}) == pytest.approx(1 / (1 + 2.718281828 ** -1), rel=1e-6)
    assert m.proba({'x_side': float('nan')}) < 0.5                                    # NaN follows missing_go_to_left


def test_shipped_model_loads_with_hash_check(tmp_path):
    m = load_model()
    assert m.features == H.FEATURES and len(m.trees) == 200
    bad = tmp_path / 'm.json'
    from core.h1con_ai_policy import MODEL_PATH
    spec = json.loads(MODEL_PATH.read_text(encoding='utf-8'))
    spec['baseline'] += 1
    bad.write_text(json.dumps(spec))
    with pytest.raises(RuntimeError):
        load_model(bad)


def test_entry_when_ai_probability_above_threshold_then_tp(force_buy):
    h = H1ConAI(model=ConstModel(0.70))
    p = payload()
    state, out, events = h.process(ready(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['policy'] == POLICY and entry['side'] == 'BUY' and entry['entry_price'] == 110.5
    assert entry['tp'] == pytest.approx(122.5) and entry['sl'] == pytest.approx(98.5)
    assert entry['selection']['ai_probability'] == 0.7 and entry['selection']['threshold'] == pytest.approx(0.55)
    assert out['state'] == 'ENTRY' and out['diagnostics']['policy'] == POLICY and out['execution_mode'] == 'PAPER_ONLY'
    later = payload(now=NOW + 5, bid=122.5, ask=123.0)
    later['candles'] = p['candles']
    state, out, events = h.process(state, later)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['id'] == entry['id'] and exit_['outcome'] == 'TP_TOUCHED' and exit_['exit_observed_price'] == 122.5
    assert state['book'] is None and state['trade'] is None and out['state'] == 'EXIT'


def test_stop_checked_first_on_sell_ask(monkeypatch):
    monkeypatch.setattr(H, 'signal', lambda h1, m15: 'SELL')
    h = H1ConAI(model=ConstModel(0.9))
    p = payload(bid=110.0, ask=110.5)
    state, out, events = h.process(ready(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['entry_price'] == 110.0 and entry['sl'] == pytest.approx(122.0)
    later = payload(now=NOW + 60, bid=121.6, ask=122.1)
    later['candles'] = p['candles']
    state, out, events = h.process(state, later)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['outcome'] == 'SL_TOUCHED' and exit_['exit_observed_price'] == 122.1 and exit_['coverage_gap'] is True


def test_ai_skips_low_probability_candidate(force_buy):
    h = H1ConAI(model=ConstModel(0.40))
    p = payload()
    state, out, events = h.process(ready(p), p)
    assert 'ENTRY' not in kinds(events) and state['book'] is None
    [skip] = [e for e in events if e['kind'] == 'H1CON_SIGNAL_SKIPPED']
    assert skip['p'] == 0.4 and skip['side'] == 'BUY'
    assert out['state'] == 'WAIT' and out['reason'] == 'H1CON_SIGNAL_SKIPPED_BY_AI'


def test_once_per_m15_bar_and_not_on_first_quote(force_buy):
    model = ConstModel(0.9)
    h = H1ConAI(model=model)
    p = payload()
    state, out, events = h.process(H1ConAI.migrate({}), p)            # first quote after install
    assert 'ENTRY' not in kinds(events) and not model.calls
    again = payload(now=NOW + 5)
    state, out, events = h.process(state, again)                        # same closed M15 bar
    assert 'ENTRY' not in kinds(events) and not model.calls


def test_insufficient_history_is_not_traded(force_buy):
    h = H1ConAI(model=ConstModel(0.9))
    p = payload()
    p['candles']['M15'] = p['candles']['M15'][-120:]
    state, out, events = h.process(ready(p), p)
    assert 'ENTRY' not in kinds(events) and out['diagnostics']['last_signal']['status'] == 'INSUFFICIENT_HISTORY'


def test_s5b_state_migrates_and_open_s5b_trade_exits_on_quotes():
    s5b_trade = dict(id='XAUUSD:S5B:1', side='BUY', entry_time=NOW - 600, entry_price=105.0, tp=108.0, sl=103.0, rr=1.5,
                     mfe_observed=0.0, mae_observed=0.1, coverage_gap=False, policy='SESSION_BIAS_S5B_V1',
                     component='S5B', component_id='XAUUSD:S5B:1', mode='H1_PULLBACK')
    s5b_state = {'s5b_version': 1, 'v5': {'last_quote_time': NOW - 5}, 'signal': {'last_m5': 123}, 'book': s5b_trade,
                 'trade': dict(s5b_trade), 'last_quote_time': NOW - 5, 'last_result': None}
    state = H1ConAI.migrate(s5b_state)
    assert state['book']['id'] == 'XAUUSD:S5B:1' and state['previous']['policy'] == 'SESSION_BIAS_S5B_V1'
    assert state['previous']['signal'] == {'last_m5': 123}
    h = H1ConAI(model=ConstModel(0.9))
    p = payload(bid=108.1, ask=108.6)
    state, out, events = h.process(state, p)
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['id'] == 'XAUUSD:S5B:1' and exit_['policy'] == 'SESSION_BIAS_S5B_V1' and exit_['outcome'] == 'TP_TOUCHED'
    assert H1ConAI.migrate(state) is state


class StubEngine:
    def __init__(self, script):
        self.script = script

    def process_hybrid(self, state, payload):
        events = [dict(e, time=payload['quote']['time']) for e in self.script.pop(0)]
        f = {'H1': {'direction_checks': dict(ema20_above_ema50=True, ema20_rising=False), 'ema20': 100, 'ema50': 100, 'atr14': 2.0},
             'M15': {'atr14': 2.0, 'ema20': 100.0, 'ema50': 100.0, 'direction_checks': dict(ema20_above_ema50=True, ema20_rising=False)}}
        value = {'decision': 'WAIT', 'state': 'WAIT', 'reason': 'X', 'diagnostics': {'policy': 'CONTEXTUAL_REACTION_V5'},
                 'timeframes': f, 'entry': {}, 'execution_mode': 'PAPER_ONLY'}
        events.append({'time': payload['quote']['time'], 'kind': 'EVALUATION', 'stage': 'WAIT', 'reason': 'X'})
        return dict(state, trade=None), value, events


def test_v5_open_trade_is_legacy_and_exits_with_v5():
    legacy = dict(id='XAUUSD:v5', side='BUY', entry_time=NOW - 60, entry_price=100.0, tp=108.0, sl=96.0, rr=2.0,
                  mfe_observed=0.0, mae_observed=0.1, coverage_gap=False, policy='CONTEXTUAL_REACTION_V5')
    state = H1ConAI.migrate({'trade': legacy, 'last_quote_time': NOW - 5})
    assert state['book']['component'] == 'LEGACY'
    h = H1ConAI(model=ConstModel(0.9))
    h.engine = StubEngine([[{'kind': 'EXIT', 'trade': dict(legacy, outcome='TP_TOUCHED', exit_time=NOW, exit_observed_price=108.1)}]])
    state, out, events = h.process(state, payload())
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['id'] == 'XAUUSD:v5' and exit_['policy'] == 'CONTEXTUAL_REACTION_V5'


def test_duplicate_tick_storable_state_and_daily_report(tmp_path, force_buy):
    from data_feed.trade_report import build_report
    h = H1ConAI(model=ConstModel(0.8))
    p = payload()
    store = StateStore(tmp_path / 'engine.sqlite3')
    first = store.process('XAUUSD', lambda s: h.process(ready(p) if not s else s, p))
    again = store.process('XAUUSD', lambda s: h.process(s, p))
    assert first['state'] == 'ENTRY' and again == first
    with store.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM events WHERE kind='ENTRY'").fetchone()[0] == 1
        assert json.loads(c.execute('SELECT value FROM engine_state').fetchone()[0])['h1con_version'] == 1
    report = build_report(store.path, NOW + 1)
    [row] = report['trades']
    assert row['status'] == 'OPEN' and row['policy'] == POLICY and report['counts']['open_positions'] == 1


def test_live_server_runs_h1con_policy(tmp_path, monkeypatch):
    from data_feed import hybrid_feed, live_server
    from tests.test_hybrid import NOW as FEED_NOW, feed
    monkeypatch.setattr(live_server, 'RUNTIME', tmp_path)
    monkeypatch.setattr(live_server, '_store', None)
    monkeypatch.setattr(hybrid_feed.time, 'time', lambda: FEED_NOW)
    output = live_server.analyze(feed())
    assert output['status'] == 'PROCESSED'
    assert output['decision']['diagnostics']['policy'] == POLICY
    assert output['decision']['diagnostics']['component_policy'] == 'CONTEXTUAL_REACTION_V5'
    assert output['decision']['execution_mode'] == 'PAPER_ONLY'
