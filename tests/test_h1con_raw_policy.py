import json

import pytest

from core import h1con_ai as H
from core.h1con_raw_policy import POLICY, SHADOW_POLICY, H1ConRaw
from data_feed.state_store import StateStore
from tests.test_h1con_policy import NOW, ConstModel, payload


def ready(p):
    state = H1ConRaw.migrate({})
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


def test_names():
    assert POLICY == 'H1CON_RAW_V1' and SHADOW_POLICY == 'H1CON_AI_V1'


def test_main_takes_signal_without_ai_and_shadow_skips_low_probability(force_buy):
    h = H1ConRaw(model=ConstModel(0.40))
    p = payload()
    state, out, events = h.process(ready(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['policy'] == POLICY and entry['side'] == 'BUY' and entry['entry_price'] == 110.5
    assert entry['tp'] == pytest.approx(122.5) and entry['sl'] == pytest.approx(98.5)
    assert entry['selection']['ai_probability'] == 0.4 and entry['selection']['selection_reason'] == 'H1CON_RSI_RAW'
    [skip] = [e for e in events if e['kind'] == 'H1CON_SIGNAL_SKIPPED']
    assert skip['shadow'] is True and skip['p'] == 0.4
    assert 'SHADOW_ENTRY' not in kinds(events) and state['shadow']['book'] is None
    assert out['state'] == 'ENTRY' and out['reason'] == 'H1CON_RAW_ENTRY'
    assert out['diagnostics']['policy'] == POLICY and out['diagnostics']['shadow_policy'] == SHADOW_POLICY
    assert out['execution_mode'] == 'PAPER_ONLY'


def test_both_enter_when_ai_agrees_and_exit_independently(force_buy):
    h = H1ConRaw(model=ConstModel(0.70))
    p = payload()
    state, out, events = h.process(ready(p), p)
    assert kinds(events).count('ENTRY') == 1 and kinds(events).count('SHADOW_ENTRY') == 1
    main_id, shadow_id = state['book']['id'], state['shadow']['book']['id']
    assert main_id != shadow_id and state['shadow']['book']['policy'] == SHADOW_POLICY
    state, out, events = h.process(state, later(p, 5, 122.5, 123.0))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    [sexit] = [e['trade'] for e in events if e['kind'] == 'SHADOW_EXIT']
    assert exit_['id'] == main_id and exit_['outcome'] == 'TP_TOUCHED'
    assert sexit['id'] == shadow_id and sexit['outcome'] == 'TP_TOUCHED'
    assert state['book'] is None and state['shadow']['book'] is None and out['state'] == 'EXIT'


def test_signal_while_main_open_is_logged_and_shadow_still_free(force_buy):
    model = ConstModel(0.40)
    h = H1ConRaw(model=model)
    p = payload()
    state, out, events = h.process(ready(p), p)                     # main enters, shadow skips
    model.p = 0.80
    state, out, events = h.process(state, later(p, 900, 111.0, 111.5, new_bar=True))
    assert 'ENTRY' not in kinds(events)
    [busy] = [e for e in events if e['kind'] == 'H1CON_SIGNAL_BUSY']
    assert busy['open_trade'] == state['book']['id']
    [sentry] = [e['trade'] for e in events if e['kind'] == 'SHADOW_ENTRY']
    assert sentry['policy'] == SHADOW_POLICY and sentry['entry_price'] == 111.5
    assert out['diagnostics']['last_signal']['status'] == 'MAIN_BUSY'


def test_stop_first_on_sell_ask_for_main(monkeypatch):
    monkeypatch.setattr(H, 'signal', lambda h1, m15: 'SELL')
    h = H1ConRaw(model=ConstModel(0.1))
    p = payload(bid=110.0, ask=110.5)
    state, out, events = h.process(ready(p), p)
    [entry] = [e['trade'] for e in events if e['kind'] == 'ENTRY']
    assert entry['entry_price'] == 110.0 and entry['sl'] == pytest.approx(122.0)
    state, out, events = h.process(state, later(p, 60, 121.6, 122.1))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    assert exit_['outcome'] == 'SL_TOUCHED' and exit_['exit_observed_price'] == 122.1 and exit_['coverage_gap'] is True


def test_migration_from_live_h1con_ai_keeps_open_trade_in_both_books(force_buy):
    old = dict(id='XAUUSD:H1CON:1', side='BUY', entry_time=NOW - 600, entry_price=105.0, tp=117.0, sl=93.0, rr=1.0,
               mfe_observed=0.0, mae_observed=0.1, coverage_gap=False, policy=SHADOW_POLICY,
               component='H1CON', component_id='XAUUSD:H1CON:1', mode='H1CON_RSI_AI')
    ai_state = {'h1con_version': 1, 'v5': {'last_quote_time': NOW - 5}, 'signal': {'last_m15': 1}, 'book': old,
                'previous': {'policy': 'SESSION_BIAS_S5B_V1'}, 'trade': dict(old), 'last_quote_time': NOW - 5,
                'last_result': None}
    state = H1ConRaw.migrate(json.loads(json.dumps(ai_state)))
    assert state['raw_version'] == 1 and state['book']['id'] == 'XAUUSD:H1CON:1'
    assert state['shadow']['book']['id'] == 'XAUUSD:H1CON:1' and state['shadow']['book']['component'] == 'SHADOW'
    assert state['previous']['policy'] == SHADOW_POLICY and state['main_policy_since'] == NOW - 5
    assert H1ConRaw.migrate(state) is state
    h = H1ConRaw(model=ConstModel(0.9))
    state, out, events = h.process(state, payload(bid=117.1, ask=117.6))
    [exit_] = [e['trade'] for e in events if e['kind'] == 'EXIT']
    [sexit] = [e['trade'] for e in events if e['kind'] == 'SHADOW_EXIT']
    assert exit_['policy'] == SHADOW_POLICY and exit_['outcome'] == 'TP_TOUCHED' and sexit['outcome'] == 'TP_TOUCHED'


def test_migration_from_s5b_state_still_works():
    s5b = {'s5b_version': 1, 'v5': {'last_quote_time': NOW - 5}, 'signal': {'last_m5': 1}, 'book': None,
           'trade': None, 'last_quote_time': NOW - 5, 'last_result': None}
    state = H1ConRaw.migrate(s5b)
    assert state['raw_version'] == 1 and state['shadow'] == {'policy': SHADOW_POLICY, 'book': None}


def test_once_per_m15_bar_and_not_on_first_quote(force_buy):
    model = ConstModel(0.9)
    h = H1ConRaw(model=model)
    p = payload()
    state, out, events = h.process(H1ConRaw.migrate({}), p)
    assert 'ENTRY' not in kinds(events) and not model.calls
    state, out, events = h.process(state, later(p, 5, 110.0, 110.5))
    assert 'ENTRY' not in kinds(events) and not model.calls


def test_store_reports_and_comparison(tmp_path, force_buy):
    from data_feed.trade_report import build_comparison, build_report
    h = H1ConRaw(model=ConstModel(0.8))
    p = payload()
    store = StateStore(tmp_path / 'engine.sqlite3')
    first = store.process('XAUUSD', lambda s: h.process(ready(p) if not s else s, p))
    again = store.process('XAUUSD', lambda s: h.process(s, p))
    assert first['state'] == 'ENTRY' and again == first
    store.process('XAUUSD', lambda s: h.process(s, later(p, 30, 122.6, 123.1)))
    main = build_report(store.path, NOW + 60)
    shadow = build_report(store.path, NOW + 60, 'SHADOW_ENTRY', 'SHADOW_EXIT', shadow=True)
    assert [r['policy'] for r in main['trades']] == [POLICY] and main['counts']['tp_observed'] == 1
    assert [r['policy'] for r in shadow['trades']] == [SHADOW_POLICY] and shadow['counts']['tp_observed'] == 1
    cmp_ = build_comparison(store.path, NOW + 60)
    assert cmp_['status'] == 'OK'
    assert cmp_['systems']['main']['tp'] == 1 and cmp_['systems']['main']['net_price_move'] == pytest.approx(12.1)
    assert cmp_['systems']['shadow']['tp'] == 1 and cmp_['systems']['shadow']['policy'] == SHADOW_POLICY


def test_live_server_runs_raw_policy_with_shadow(tmp_path, monkeypatch):
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


def test_dashboard_feed_hours_and_names():
    import ast, pathlib
    from datetime import datetime, timezone
    src = (pathlib.Path(__file__).resolve().parents[1] / 'streamlit_app.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in
            ('_nth_sunday', 'new_york_offset_hours', 'gold_market_open')]
    ns = {'datetime': datetime, 'timezone': timezone, 'timedelta': __import__('datetime').timedelta}
    exec(compile(ast.Module(body=keep, type_ignores=[]), 'dash', 'exec'), ns)
    open_ = ns['gold_market_open']
    utc = lambda *a: datetime(*a, tzinfo=timezone.utc)
    assert open_(utc(2026, 11, 4, 15, 0))            # Wed 10:00 New York
    assert not open_(utc(2026, 11, 4, 22, 30))       # Wed 17:30 New York, daily break
    assert open_(utc(2026, 11, 5, 0, 30))            # Wed 19:30 New York
    assert not open_(utc(2026, 11, 7, 12, 0))        # Saturday
    assert not open_(utc(2026, 11, 1, 23, 30))       # Sunday 18:30 New York (feed starts ~21:00)
    assert not open_(utc(2026, 10, 28, 21, 0))       # Wed 17:00 EDT (summer time) -> daily break
    assert open_(utc(2026, 10, 28, 23, 30))          # Wed 19:30 EDT -> open
    assert "MAIN_POLICY = \"H1CON_RAW_V1\"" in src and "SHADOW_POLICY = \"H1CON_AI_V1\"" in src


def test_store_uses_wal_and_export_includes_shadow_trades(tmp_path, force_buy):
    import sqlite3, zipfile
    from datetime import datetime, timezone
    from data_feed.audit_export import export_audit
    root = tmp_path / 'proj'; (root / 'runtime').mkdir(parents=True)
    store = StateStore(root / 'runtime' / 'engine.sqlite3')
    with sqlite3.connect(store.path) as c:
        assert c.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    h = H1ConRaw(model=ConstModel(0.8))
    p = payload()
    store.process('XAUUSD', lambda s: h.process(ready(p) if not s else s, p))
    store.process('XAUUSD', lambda s: h.process(s, later(p, 30, 122.6, 123.1)))
    from data_feed.audit_export import THAI
    day = datetime.fromtimestamp(NOW, THAI).strftime('%Y-%m-%d')
    path = export_audit(root, day, day, tmp_path / 'out', now=datetime.fromtimestamp(NOW + 3600, timezone.utc))
    with zipfile.ZipFile(path) as z:
        shadow = json.loads(z.read('shadow_trades.json'))
        main = json.loads(z.read('trades.json'))
        assert [t['policy'] for t in shadow] == [SHADOW_POLICY] and [t['policy'] for t in main] == [POLICY]
        assert 'H1CON_RAW_V1' in z.read('START_HERE_TH.txt').decode('utf-8')
