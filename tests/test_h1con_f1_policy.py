import json

import pytest

from core import h1con_ai as H
from core import h1con_f1_policy as F
from core.h1con_f1_policy import POLICY, SHADOW_POLICY, H1ConF1, f1_check
from data_feed.state_store import StateStore
from tests.test_h1con_policy import NOW, ConstModel, payload


def ready(p):
    state = H1ConF1.migrate({})
    state['signal']['last_m15'] = p['candles']['M15'][-2]['time']      # this payload brings a new M15 bar
    return state


def kinds(events):
    return [e['kind'] for e in events]


def later(p, dt, bid, ask, new_bar=False):
    q = payload(now=NOW + dt, bid=bid, ask=ask)
    q['candles'] = json.loads(json.dumps(p['candles']))
    if new_bar:
        last = q['candles']['M15'][-1]
        q['candles']['M15'] = q['candles']['M15'][1:] + [dict(last, time=last['time'] + 900)]
    return q


@pytest.fixture
def force_buy(monkeypatch):
    monkeypatch.setattr(H, 'signal', lambda h1, m15: 'BUY')
    monkeypatch.setattr(F, 'f1_check', lambda side, h1: (True, 101.0, 100.0))


def test_names_and_distances():
    assert POLICY == 'H1CON_F1TP30_V1' and SHADOW_POLICY == 'H1CON_RAW_V1'
    assert (F.MAIN_TP, F.MAIN_SL, F.SHADOW_TP, F.SHADOW_SL) == (30.0, 12.0, 12.0, 12.0)
    assert F.SYSTEM_LABEL.isascii()


def test_f1_check_uses_last_closed_h1_close_against_ema50():
    up = [dict(close=100.0 + i) for i in range(200)]
    assert f1_check('BUY', up)[0] is True and f1_check('SELL', up)[0] is False
    drop = up[:-1] + [dict(close=150.0)]                       # last close falls under the rising EMA50
    ok, close, ema = f1_check('BUY', drop)
    assert ok is False and close == 150.0 and ema > 150.0
    assert ema == pytest.approx(H.ema_series([b['close'] for b in drop], 50)[-1])


def test_main_tp30_and_shadow_tp12_exit_independently(force_buy):
    h = H1ConF1(model=ConstModel(0.40))                         # AI value is information only
    p = payload()
    state, out, events = h.process(ready(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    [sentry] = [e['trade'] for e in events if e['kind'] == 'SHADOW_ENTRY']
    assert entry['policy'] == POLICY and entry['entry_price'] == 110.5
    assert entry['tp'] == pytest.approx(140.5) and entry['sl'] == pytest.approx(98.5) and entry['rr'] == 2.5
    assert entry['selection']['ai_probability'] == 0.4 and entry['selection']['selection_reason'] == 'H1CON_RSI_F1_TP30'
    assert sentry['policy'] == SHADOW_POLICY and sentry['tp'] == pytest.approx(122.5) and sentry['sl'] == pytest.approx(98.5)
    assert entry['id'] != sentry['id'] and 'H1CON_SIGNAL_SKIPPED' not in kinds(events)
    assert out['state'] == 'ENTRY' and out['reason'] == 'H1CON_F1_ENTRY'
    d = out['diagnostics']
    assert d['policy'] == POLICY and d['shadow_policy'] == SHADOW_POLICY and d['system_label'] == F.SYSTEM_LABEL
    assert out['execution_mode'] == 'PAPER_ONLY'
    state, out, events = h.process(state, later(p, 5, 122.5, 123.0))       # +12: shadow TP, main keeps running
    assert 'EXIT' not in kinds(events) and kinds(events).count('SHADOW_EXIT') == 1
    assert state['book']['id'] == entry['id'] and state['shadow']['book'] is None and out['state'] == 'MANAGE'
    state, out, events = h.process(state, later(p, 10, 140.5, 141.0))      # +30: main TP
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['outcome'] == 'TP_TOUCHED' and exit_['exit_observed_price'] == 140.5 and state['book'] is None


def test_main_sl12(force_buy):
    h = H1ConF1(model=ConstModel(0.9))
    p = payload()
    state, out, events = h.process(ready(p), p)
    state, out, events = h.process(state, later(p, 5, 98.5, 99.0))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    [sexit] = [e['trade'] for e in events if e['kind'] == 'SHADOW_EXIT']
    assert exit_['outcome'] == 'SL_TOUCHED' and sexit['outcome'] == 'SL_TOUCHED'


def test_f1_filter_blocks_main_but_shadow_takes_signal(force_buy, monkeypatch):
    monkeypatch.setattr(F, 'f1_check', lambda side, h1: (False, 99.0, 100.0))
    h = H1ConF1(model=ConstModel(0.9))
    p = payload()
    state, out, events = h.process(ready(p), p)
    assert 'ENTRY' not in kinds(events) and state['book'] is None
    [flt] = [e for e in events if e['kind'] == 'H1CON_SIGNAL_FILTERED']
    assert flt['filter'] == 'F1' and flt['side'] == 'BUY' and flt['h1_close'] == 99.0 and flt['h1_ema50'] == 100.0
    assert kinds(events).count('SHADOW_ENTRY') == 1
    assert out['state'] == 'WAIT' and out['reason'] == 'H1CON_SIGNAL_FILTERED_F1'
    sig = out['diagnostics']['last_signal']
    assert sig['status'] == 'FILTERED_F1' and sig['shadow_status'] == 'SHADOW_ENTERED' and sig['f1']['ok'] is False


def test_f1_receives_closed_h1_window(monkeypatch):
    monkeypatch.setattr(H, 'signal', lambda h1, m15: 'SELL')
    seen = {}
    monkeypatch.setattr(F, 'f1_check', lambda side, h1: seen.update(side=side, h1=h1) or (True, 1.0, 2.0))
    h = H1ConF1(model=ConstModel(0.2))
    p = payload()
    state, out, events = h.process(ready(p), p)
    assert seen['side'] == 'SELL' and seen['h1'] == p['candles']['H1'][-H.WINDOW:]
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['entry_price'] == 110.0 and entry['tp'] == pytest.approx(80.0) and entry['sl'] == pytest.approx(122.0)


def test_signal_while_main_open_is_busy_and_shadow_free(force_buy):
    h = H1ConF1(model=ConstModel(0.5))
    p = payload()
    state, out, events = h.process(ready(p), p)
    state, out, events = h.process(state, later(p, 5, 122.5, 123.0))       # shadow TP, main open
    state, out, events = h.process(state, later(p, 900, 111.0, 111.5, new_bar=True))
    assert 'ENTRY' not in kinds(events)
    [busy] = [e for e in events if e['kind'] == 'H1CON_SIGNAL_BUSY']
    assert busy['open_trade'] == state['book']['id']
    [sentry] = [e['trade'] for e in events if e['kind'] == 'SHADOW_ENTRY']
    assert sentry['entry_price'] == 111.5 and out['diagnostics']['last_signal']['status'] == 'MAIN_BUSY'


def test_once_per_m15_bar_and_not_on_first_quote(force_buy):
    model = ConstModel(0.9)
    h = H1ConF1(model=model)
    p = payload()
    state, out, events = h.process(H1ConF1.migrate({}), p)
    assert 'ENTRY' not in kinds(events) and not model.calls
    state, out, events = h.process(state, later(p, 5, 110.0, 110.5))
    assert 'ENTRY' not in kinds(events) and not model.calls


def test_migration_from_live_raw_state(force_buy):
    """Installed state: main H1CON_RAW_V1 trade open + H1CON_AI_V1 shadow trade open."""
    raw = dict(id='XAUUSD:H1RAW:1', side='BUY', entry_time=NOW - 600, entry_price=105.0, tp=117.0, sl=93.0, rr=1.0,
               mfe_observed=0.0, mae_observed=0.1, coverage_gap=False, policy='H1CON_RAW_V1',
               component='H1CON_RAW', component_id='XAUUSD:H1RAW:1', mode='H1CON_RSI_RAW')
    ai = dict(raw, id='XAUUSD:H1AI-SHADOW:1', component_id='XAUUSD:H1AI-SHADOW:1', policy='H1CON_AI_V1', component='SHADOW')
    live = {'h1con_version': 1, 'raw_version': 1, 'v5': {'last_quote_time': NOW - 5}, 'signal': {'last_m15': 1},
            'book': raw, 'trade': dict(raw), 'shadow': {'policy': 'H1CON_AI_V1', 'book': ai},
            'main_policy_since': NOW - 10 ** 6, 'previous': {'policy': 'H1CON_AI_V1'},
            'last_quote_time': NOW - 5, 'last_result': None}
    state = H1ConF1.migrate(json.loads(json.dumps(live)))
    assert state['f1_version'] == 1 and state['main_policy_since'] == NOW - 5
    assert state['book']['id'] == 'XAUUSD:H1RAW:1' and state['book']['tp'] == 117.0      # keeps its TP/SL
    assert state['shadow']['policy'] == SHADOW_POLICY
    assert state['shadow']['book']['id'] == 'XAUUSD:H1RAW:1' and state['shadow']['book']['component'] == 'SHADOW'
    assert state['retired_shadow']['policy'] == 'H1CON_AI_V1' and state['retired_shadow']['book']['id'] == ai['id']
    assert state['previous']['policy'] == SHADOW_POLICY
    assert H1ConF1.migrate(state) is state
    h = H1ConF1(model=ConstModel(0.9))
    state, out, events = h.process(state, payload(bid=117.1, ask=117.6))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    [sexit] = [e['trade'] for e in events if e['kind'] == 'SHADOW_EXIT']
    assert exit_['policy'] == 'H1CON_RAW_V1' and exit_['outcome'] == 'TP_TOUCHED' and sexit['outcome'] == 'TP_TOUCHED'
    assert out['diagnostics']['policy'] == POLICY


def test_migration_from_empty_and_old_states():
    for old in ({}, {'s5b_version': 1, 'v5': {'last_quote_time': NOW - 5}, 'signal': {'last_m5': 1}, 'book': None,
                     'trade': None, 'last_quote_time': NOW - 5, 'last_result': None}):
        state = H1ConF1.migrate(old)
        assert state['f1_version'] == 1 and state['shadow'] == {'policy': SHADOW_POLICY, 'book': None}


def test_store_reports_and_comparison(tmp_path, force_buy):
    from data_feed.trade_report import build_comparison, build_report
    h = H1ConF1(model=ConstModel(0.8))
    p = payload()
    store = StateStore(tmp_path / 'engine.sqlite3')
    first = store.process('XAUUSD', lambda s: h.process(ready(p) if not s else s, p))
    again = store.process('XAUUSD', lambda s: h.process(s, p))
    assert first['state'] == 'ENTRY' and again == first
    store.process('XAUUSD', lambda s: h.process(s, later(p, 30, 122.6, 123.1)))
    store.process('XAUUSD', lambda s: h.process(s, later(p, 40, 140.6, 141.1)))
    main = build_report(store.path, NOW + 60)
    shadow = build_report(store.path, NOW + 60, 'SHADOW_ENTRY', 'SHADOW_EXIT', shadow=True)
    assert [r['policy'] for r in main['trades']] == [POLICY] and main['counts']['tp_observed'] == 1
    assert [r['policy'] for r in shadow['trades']] == [SHADOW_POLICY] and shadow['counts']['tp_observed'] == 1
    cmp_ = build_comparison(store.path, NOW + 60)
    assert cmp_['status'] == 'OK'
    assert cmp_['systems']['main']['policy'] == POLICY and cmp_['systems']['main']['net_price_move'] == pytest.approx(30.1)
    assert cmp_['systems']['shadow']['policy'] == SHADOW_POLICY and cmp_['systems']['shadow']['net_price_move'] == pytest.approx(12.1)


def test_live_server_runs_f1_policy_with_raw_shadow(tmp_path, monkeypatch):
    from data_feed import hybrid_feed, live_server
    from tests.test_hybrid import NOW as FEED_NOW, feed
    monkeypatch.setattr(live_server, 'RUNTIME', tmp_path)
    monkeypatch.setattr(live_server, '_store', None)
    monkeypatch.setattr(hybrid_feed.time, 'time', lambda: FEED_NOW)
    output = live_server.analyze(feed())
    assert output['status'] == 'PROCESSED'
    d = output['decision']['diagnostics']
    assert d['policy'] == POLICY and d['shadow_policy'] == SHADOW_POLICY
    assert d['component_policy'] == 'CONTEXTUAL_REACTION_V5' and output['decision']['execution_mode'] == 'PAPER_ONLY'
    assert live_server.POLICY == POLICY and isinstance(live_server.session_policy, H1ConF1)


def test_dashboard_names():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / 'streamlit_app.py').read_text(encoding='utf-8')
    assert 'MAIN_POLICY = "H1CON_F1TP30_V1"' in src and 'SHADOW_POLICY = "H1CON_RAW_V1"' in src
    assert 'FILTERED_F1' in src


def test_export_names_f1(tmp_path, force_buy):
    import zipfile
    from datetime import datetime, timezone
    from data_feed.audit_export import THAI, export_audit
    root = tmp_path / 'proj'; (root / 'runtime').mkdir(parents=True)
    store = StateStore(root / 'runtime' / 'engine.sqlite3')
    h = H1ConF1(model=ConstModel(0.8))
    p = payload()
    store.process('XAUUSD', lambda s: h.process(ready(p) if not s else s, p))
    store.process('XAUUSD', lambda s: h.process(s, later(p, 30, 140.6, 141.1)))
    day = datetime.fromtimestamp(NOW, THAI).strftime('%Y-%m-%d')
    path = export_audit(root, day, day, tmp_path / 'out', now=datetime.fromtimestamp(NOW + 3600, timezone.utc))
    assert path.name.startswith('AITrading-H1CONF1-Audit-')
    with zipfile.ZipFile(path) as z:
        assert [t['policy'] for t in json.loads(z.read('shadow_trades.json'))] == [SHADOW_POLICY]
        assert [t['policy'] for t in json.loads(z.read('trades.json'))] == [POLICY]
        assert 'H1CON_F1TP30_V1' in z.read('START_HERE_TH.txt').decode('utf-8')
