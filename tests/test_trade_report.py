import importlib
import json
from datetime import datetime

import pytest

from data_feed.state_store import StateStore
from data_feed.trade_report import build_report

NOW = datetime.fromisoformat('2026-10-16T01:00:00+00:00').timestamp()
BOUNDARY = NOW - 3600


def trade(identity='one', side='SELL', **updates):
    value = dict(id=identity, side=side, entry_time=NOW-600, entry_price=4164.11,
                 tp=4156.11, sl=4166.34, rr=3.59, mfe_observed=0,
                 coverage_gap=False, mode='COUNTERTREND')
    return dict(value, **updates)


def event(kind, value, when):
    return dict(kind=kind, time=when, trade=value)


def write(store, events, live=None):
    store.process('XAUUSD', lambda _: ({'trade': live}, {}, events))


def test_entry_exit_deduplicated_and_gap_is_not_confirmed_win(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    opened = trade()
    closed = dict(opened, exit_time=NOW-10, exit_observed_price=4156.06,
                  outcome='TP_TOUCHED', outcome_evidence='OBSERVED_QUOTE', coverage_gap=True)
    write(store, [event('ENTRY', opened, opened['entry_time']), event('EXIT', closed, closed['exit_time'])])
    report = build_report(store.path, NOW)
    assert report['counts']['sell_entries'] == 1
    assert report['counts']['tp_observed'] == 1
    assert report['counts']['exits_with_coverage_gap'] == 1
    assert len(report['trades']) == 1
    row = report['trades'][0]
    assert row['coverage_gap'] is True
    assert row['observed_price_move'] == pytest.approx(8.05)
    assert 'win_rate' not in report and 'profit' not in row


def test_open_before_reset_retained_not_counted_as_new(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    live = trade(entry_time=BOUNDARY-1800)
    write(store, [event('ENTRY', live, live['entry_time'])], live)
    report = build_report(store.path, NOW)
    assert report['counts']['sell_entries'] == 0
    assert report['counts']['open_positions'] == 1
    assert report['trades'][0]['status'] == 'OPEN'
    assert report['trades'][0]['entry_in_window'] is False


def test_exit_after_reset_without_inventing_new_entry(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    closed = trade(entry_time=BOUNDARY-100, exit_time=BOUNDARY+100,
                   exit_observed_price=4167, outcome='SL_TOUCHED')
    write(store, [event('EXIT', closed, closed['exit_time'])])
    report = build_report(store.path, NOW)
    assert report['counts']['sell_entries'] == 0
    assert report['counts']['sl_observed'] == 1
    assert report['trades'][0]['entry_in_window'] is False
    assert report['trades'][0]['observed_price_move'] < 0


def test_reset_at_0700_bangkok_does_not_erase_history(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    first = trade('old', 'BUY', entry_time=BOUNDARY-60,
                  exit_time=BOUNDARY-30, outcome='TP_TOUCHED', exit_observed_price=4172.11)
    second = trade('new', 'SELL', entry_time=BOUNDARY)
    write(store, [event('ENTRY', first, first['entry_time']), event('EXIT', first, first['exit_time']),
                  event('ENTRY', second, BOUNDARY)], second)
    before = build_report(store.path, BOUNDARY-1)
    after = build_report(store.path, BOUNDARY)
    assert before['counts']['buy_entries'] == 1
    assert before['counts']['sell_entries'] == 0
    assert after['counts']['buy_entries'] == 0
    assert after['counts']['sell_entries'] == 1
    assert after['counts']['tp_observed'] == 0
    assert after['window_start_utc'] == '2026-10-16T00:00:00+00:00'
    assert after['next_reset_utc'] == '2026-10-17T00:00:00+00:00'
    with store.connect() as connection:
        assert connection.execute('select count(*) from events').fetchone()[0] == 3


def test_ambiguous_trade_is_not_tp_or_sl(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    live = trade(unresolved=True)
    write(store, [event('ENTRY', live, live['entry_time']),
                  dict(kind='AMBIGUOUS_OUTCOME', time=NOW-10, trade_id=live['id'])], live)
    report = build_report(store.path, NOW)
    assert report['counts']['unresolved_positions'] == 1
    assert report['counts']['tp_observed'] == report['counts']['sl_observed'] == 0
    assert report['trades'][0]['status'] == 'UNRESOLVED_TP_SL'


def test_no_database_and_empty_database_do_not_invent_history(tmp_path):
    assert build_report(tmp_path/'missing.sqlite3', NOW)['status'] == 'NO_AUDIT_DATABASE'
    store = StateStore(tmp_path/'engine.sqlite3')
    report = build_report(store.path, NOW)
    assert report['status'] == 'OK'
    assert report['trades'] == []
    assert report['audit_started_at_utc'] is None


def setup_sync(tmp_path, monkeypatch):
    monkeypatch.setenv('ProgramData', str(tmp_path))
    from data_feed import supabase_sync
    sync = importlib.reload(supabase_sync)
    monkeypatch.setattr(sync, 'ROOT', tmp_path)
    monkeypatch.setattr(sync, 'CONFIG', tmp_path/'config.json')
    sync.CONFIG.write_text(json.dumps(dict(url='https://vowiwmgmevltuhnzyhcy.supabase.co', secret_key='test-only')))
    runtime = tmp_path/'runtime'
    runtime.mkdir()
    snapshot = dict(mode='READ_ONLY', received_at_utc='2026-10-15T20:30:00+00:00',
                    market=dict(symbol='XAUUSD', timeframe='M15'), analysis=dict(status='PROCESSED'))
    (runtime/'latest.json').write_text(json.dumps(snapshot))
    captured = []
    class Response:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def upload(request, timeout):
        captured.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(sync, 'urlopen', upload)
    monkeypatch.setattr(sync.time, 'time', lambda: NOW)
    return sync, captured, StateStore(runtime/'engine.sqlite3')


def test_new_trade_uploads_without_new_market_snapshot(tmp_path, monkeypatch):
    sync, captured, store = setup_sync(tmp_path, monkeypatch)
    previous = sync.upload_latest()
    sync.upload_latest(previous)
    assert len(captured) == 1
    live = trade()
    write(store, [event('ENTRY', live, live['entry_time'])], live)
    previous = sync.upload_latest(previous)
    assert len(captured) == 2
    assert captured[-1]['snapshot']['paper_report_session']['counts']['sell_entries'] == 1
    assert captured[-1]['received_at_utc'] == '2026-10-15T20:30:00+00:00'
    sync.upload_latest(previous)
    assert len(captured) == 2
    monkeypatch.setattr(sync.time, 'time', lambda: NOW+60)
    sync.upload_latest(previous)
    assert len(captured) == 3


def test_report_error_does_not_block_market_upload(tmp_path, monkeypatch):
    sync, captured, _ = setup_sync(tmp_path, monkeypatch)
    import data_feed.trade_report
    def fail(*args): raise ValueError('bad audit')
    monkeypatch.setattr(data_feed.trade_report, 'build_report', fail)
    sync.upload_latest()
    assert captured[0]['snapshot']['paper_report_session']['status'] == 'REPORT_UNAVAILABLE'
    assert captured[0]['snapshot']['analysis']['status'] == 'PROCESSED'


def test_restart_reconstructs_same_trades_and_fixed_daily_window(tmp_path):
    store = StateStore(tmp_path/'engine.sqlite3')
    live = trade()
    write(store, [event('ENTRY', live, live['entry_time'])], live)
    first = build_report(store.path, NOW)
    second = build_report(StateStore(store.path).path, NOW+100)
    assert first['window_start_utc'] == second['window_start_utc']
    assert first['trades'] == second['trades']


def test_sync_resets_counts_and_keeps_open_trade_without_new_quote(tmp_path, monkeypatch):
    sync, captured, store = setup_sync(tmp_path, monkeypatch)
    live = trade(entry_time=BOUNDARY-60)
    write(store, [event('ENTRY', live, live['entry_time'])], live)
    monkeypatch.setattr(sync.time, 'time', lambda: BOUNDARY-1)
    previous = sync.upload_latest()
    assert captured[-1]['snapshot']['paper_report_session']['counts']['sell_entries'] == 1
    monkeypatch.setattr(sync.time, 'time', lambda: BOUNDARY)
    sync.upload_latest(previous)
    report = captured[-1]['snapshot']['paper_report_session']
    assert report['counts']['sell_entries'] == 0
    assert report['counts']['open_positions'] == 1
    assert report['trades'][0]['id'] == live['id']
    with store.connect() as connection:
        assert connection.execute('select count(*) from events').fetchone()[0] == 1
