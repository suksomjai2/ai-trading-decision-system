import copy
import json
import math

import pytest

from core.feature_engine import FeatureEngine
from core.market_state import MarketState
from data_feed.hybrid_feed import PERIODS, validate
from data_feed.state_store import StateStore

NOW = 1800000030.0


def feed(now=NOW, bid=100.0, ask=100.1, rising=True):
    histories = {}
    for tf, period in PERIODS.items():
        last = int(now // period) * period - period
        bars = []
        for i in range(80):
            close = 80 + i * 0.25 if rising else 120 - i * 0.25
            bars.append(dict(time=last-(79-i)*period, open=close-0.1,
                             high=close+0.5, low=close-0.5, close=close, volume=100))
        histories[tf] = bars
    return dict(schema_version=2, symbol="XAUUSD", bar_clock="UTC",
                quote=dict(time=now, bid=bid, ask=ask), candles=histories)


def position(side="BUY", **updates):
    trade = dict(id="paper-1", side=side, entry_time=NOW-10, entry_price=100.1,
                 sl=95 if side=="BUY" else 105, tp=108 if side=="BUY" else 92,
                 mfe_observed=0, coverage_gap=False)
    trade.update(updates)
    return dict(last_quote_time=NOW-5, last_mid=100.0, trade=trade)


def test_actual_history_direction_not_latest_candle_midpoint():
    engine = FeatureEngine()
    bars = feed()["candles"]["H4"]
    bars[-1]["close"] = bars[-1]["low"] + 0.1  # latest close in lower part
    value = engine.calculate_history(bars)
    assert value["direction"] == "UP"
    assert value["atr14"] > 0
    assert engine.calculate_history(feed(rising=False)["candles"]["H4"])["direction"] == "DOWN"


@pytest.mark.parametrize("candidate", [True, float("nan"), float("inf"), -1])
def test_invalid_quotes_rejected(candidate):
    payload = feed()
    payload["quote"]["bid"] = candidate
    with pytest.raises(ValueError):
        validate(payload, now=NOW)


def test_closed_order_freshness_and_minimum_history():
    validate(feed(), now=NOW)
    for modify in (
        lambda p: p["candles"]["M5"][-1].update(time=NOW),
        lambda p: p["candles"]["H4"].reverse(),
        lambda p: p["candles"].update(H1=[]),
        lambda p: p["quote"].update(time=NOW-31),
        lambda p: p.update(bar_clock="BROKER"),
    ):
        payload = feed()
        modify(payload)
        with pytest.raises(ValueError):
            validate(payload, now=NOW)


def test_buy_wait_sell_sequence_cannot_open_opposing_trade():
    engine = MarketState()
    state = position()
    state, output, events = engine.process_hybrid(state, feed())
    assert output["state"] == "MANAGE"
    # Change the entire direction context to DOWN, not just one candle.
    state, output, events = engine.process_hybrid(state, feed(now=NOW+5, rising=False))
    assert output["state"] == "MANAGE"
    assert output["reason"] == "OPPOSING_BIAS_NO_REVERSE"
    assert output["decision"] == "WAIT"
    assert state["trade"]["side"] == "BUY"
    assert state["trade"]["tp"] == 108
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_exit_then_no_reverse_on_same_m15():
    engine = MarketState()
    state, output, _ = engine.process_hybrid(position(), feed(bid=94, ask=94.1, rising=False))
    assert output["state"] == "EXIT"
    assert output["reason"] == "SL_TOUCHED"
    assert state["trade"] is None
    state, output, _ = engine.process_hybrid(state, feed(now=NOW+1, bid=94, ask=94.1, rising=False))
    assert output["state"] == "WAIT"
    assert output["reason"] == "COOLDOWN_AFTER_EXIT_OR_CANCEL"


def test_bid_ask_used_for_paper_exits():
    engine = MarketState()
    state, output, _ = engine.process_hybrid(position("SELL"), feed(bid=91.99, ask=92.2))
    assert output["state"] == "MANAGE"  # bid hit SELL TP but ask did not
    state, output, _ = engine.process_hybrid(state, feed(now=NOW+1, bid=91.8, ask=91.9))
    assert output["state"] == "EXIT"
    assert output["reason"] == "TP_TOUCHED"


def test_prior_entry_candle_range_is_not_outcome():
    payload = feed()
    payload["candles"]["M5"][-1].update(high=110, low=90)
    _, output, _ = MarketState().process_hybrid(position(), payload)
    assert output["state"] == "MANAGE"


def test_both_levels_touched_cannot_invent_tp_first():
    payload = feed()
    payload["candles"]["M5"][-1].update(high=110, low=90)
    state = position(entry_time=payload["candles"]["M5"][-1]["time"]-1)
    state, output, events = MarketState().process_hybrid(state, payload)
    assert output["state"] == "MANAGE"
    assert state["trade"]["unresolved"] is True
    assert any(e["kind"] == "AMBIGUOUS_OUTCOME" for e in events)


def test_retry_and_restart_keep_one_trade(tmp_path):
    path = tmp_path / "engine.sqlite3"
    engine = MarketState()
    store = StateStore(path)
    store.process("XAUUSD", lambda _: (position(), {}, []))
    payload = feed()
    first = store.process("XAUUSD", lambda s: engine.process_hybrid(s, payload))
    # New store instance simulates process restart.
    second = StateStore(path).process("XAUUSD", lambda s: engine.process_hybrid(s, payload))
    assert first == second
    assert first["paper_trade"]["id"] == "paper-1"
    with store.connect() as connection:
        assert connection.execute("select count(*) from events where kind='ENTRY'").fetchone()[0] == 0


def test_database_failure_rolls_back(tmp_path):
    store = StateStore(tmp_path / "engine.sqlite3")
    store.process("XAUUSD", lambda _: ({"trade": "original"}, {}, []))
    with pytest.raises(ValueError):
        store.process("XAUUSD", lambda _: ({"trade": float("nan")}, {}, []))
    output = store.process("XAUUSD", lambda s: (s, s, []))
    assert output["trade"] == "original"


def armed(payload, side="BUY", zone_seen=False):
    return dict(last_quote_time=payload["quote"]["time"]-5, last_mid=100,
                setup=dict(id="armed-1", side=side, created=NOW-10, expires=NOW+3600,
                           source_bar=payload["candles"]["H1"][-1]["time"],
                           source_m15=payload["candles"]["M15"][-1]["time"], zone_low=98,
                           zone_high=100, sl=95, zone_seen=zone_seen,
                           zone_seen_time=NOW-400, confirmation_after=NOW-1000,
                           late_chase_recorded=False))


def test_no_chasing_overextended_move_and_audit():
    payload = feed(bid=103, ask=103.1)
    _, output, events = MarketState().process_hybrid(armed(payload), payload)
    assert output["state"] == "ARMED"
    assert output["reason"] == "NO_PRICE_CHASING"
    assert any(e["kind"] == "LATE_CHASE_REJECTED" for e in events)


def test_adverse_impulse_cancels_instead_of_dip_entry():
    payload = feed(bid=97, ask=97.1)
    _, output, events = MarketState().process_hybrid(armed(payload), payload)
    assert output["state"] == "CANCEL"
    assert output["reason"] == "IMPULSE_OVERRIDE"
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_structural_invalidation_cancels():
    payload = feed(bid=94, ask=94.1)
    _, output, _ = MarketState().process_hybrid(armed(payload), payload)
    assert output["reason"] == "STRUCTURAL_INVALIDATION"


def test_live_trigger_can_enter_between_m15_closes():
    payload = feed(bid=100.3, ask=100.4)
    payload["candles"]["M5"][-1].update(open=99, high=100.2, low=98.9, close=100.1)
    state = armed(payload, zone_seen=True)
    state["setup"]["sl"] = 99
    state, output, events = MarketState().process_hybrid(state, payload)
    assert output["state"] == "ENTRY"
    assert output["paper_trade"]["entry_price"] == 100.4
    assert output["execution_mode"] == "PAPER_ONLY"
    assert output["paper_trade"]["rr"] >= 1.5
    assert len([e for e in events if e["kind"] == "ENTRY"]) == 1
    state, again, events = MarketState().process_hybrid(state, feed(now=NOW+1, bid=100.3, ask=100.4))
    assert again["state"] == "MANAGE"
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_live_rr_can_reject_otherwise_confirmed_entry():
    payload = feed(bid=100.3, ask=100.4)
    payload["candles"]["M5"][-1].update(open=99, high=100.2, low=98.9, close=100.1)
    state = armed(payload, zone_seen=True)
    _, output, events = MarketState().process_hybrid(state, payload)
    assert output["reason"] == "INSUFFICIENT_RISK_REWARD"
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_full_server_feed_snapshot_and_restart(tmp_path, monkeypatch):
    from data_feed import live_server
    from data_feed import hybrid_feed
    monkeypatch.setattr(live_server, "RUNTIME", tmp_path)
    monkeypatch.setattr(live_server, "_store", None)
    monkeypatch.setattr(hybrid_feed.time, "time", lambda: NOW)
    payload = feed()
    output = live_server.analyze(payload)
    assert output["status"] == "PROCESSED"
    # Live policy is S5B; the V5 engine underneath still arms its research setup.
    assert output["decision"]["state"] == "WAIT"
    assert output["decision"]["diagnostics"]["component_stage"] == "ARMED"
    live_server.save_snapshot(payload, output)
    stored = json.loads((tmp_path / "latest.json").read_text())
    assert stored["market"]["symbol"] == "XAUUSD"
    assert stored["market"]["timeframe"] == "M15"
    assert stored["quote"]["ask"] == 100.1
    assert "candles" not in stored  # no full-history upload on each quote
    assert stored["analysis"]["decision"]["execution_mode"] == "PAPER_ONLY"
    monkeypatch.setattr(live_server, "_store", None)
    assert live_server.analyze(payload) == output


def test_old_feed_cannot_bypass_new_entry_requirements():
    from data_feed.live_server import analyze
    bar = feed()["candles"]["M15"][-1]
    result = analyze(dict(symbol="XAUUSD", timeframe="M15", timestamp="2026-10-16T00:00:00", **bar))
    assert result["status"] == "PROCESSED"
    assert result["decision"]["decision"] == "WAIT"
    assert result["decision"]["reason"] == "REQUIRES_MULTI_TIMEFRAME_AND_LIVE_FEED"


@pytest.mark.parametrize("shift", [0, 1000])
def test_chart_lesson_reject_low_short_wait_retest_then_cancel_impulse(shift):
    engine = MarketState()
    def chart(now, value):
        payload = feed(now=now, bid=value+shift, ask=value+shift+0.1, rising=False)
        for bars in payload["candles"].values():
            for bar in bars:
                for key in ("open", "high", "low", "close"):
                    bar[key] += 4045 + shift
        return payload
    payload = chart(NOW, 4134)
    state = armed(payload, side="SELL")
    state["last_mid"] = 4134 + shift
    state["setup"].update(zone_low=4144+shift, zone_high=4147+shift, sl=4152+shift)
    _, output, _ = engine.process_hybrid(state, payload)
    assert output["reason"] == "NO_PRICE_CHASING"
    # Independent observed retest, without fabricating intermediate quotes.
    payload = chart(NOW+5, 4145)
    state["last_mid"] = 4145 + shift
    state, output, _ = engine.process_hybrid(state, payload)
    assert output["state"] == "ARMED"
    assert output["reason"] == "PULLBACK_OBSERVED_WAIT_CONFIRMATION"
    state, output, _ = engine.process_hybrid(state, chart(NOW+10, 4149.5))
    assert output["state"] == "CANCEL"
    assert output["reason"] == "IMPULSE_OVERRIDE"
    assert state.get("trade") is None


def test_real_http_market_route(tmp_path, monkeypatch):
    import threading
    import time
    from http.server import HTTPServer
    from urllib.request import Request, urlopen
    from data_feed import live_server
    monkeypatch.setattr(live_server, "RUNTIME", tmp_path)
    monkeypatch.setattr(live_server, "_store", None)
    server = HTTPServer(("127.0.0.1", 0), live_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:" + str(server.server_port)
        with urlopen(url + "/health") as response:
            assert json.load(response)["mode"] == "READ_ONLY"
        payload = feed(now=time.time())
        request = Request(url + "/market", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request) as response:
            result = json.load(response)
        assert result["status"] == "PROCESSED"
        assert (tmp_path / "latest.json").exists()
        with StateStore(tmp_path / "engine.sqlite3").connect() as connection:
            assert connection.execute("select count(*) from events where kind='ARMED'").fetchone()[0] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_new_closed_structure_reassesses_without_discarding_setup():
    payload = feed()
    state = armed(payload)
    state["setup"]["source_m15"] = payload["candles"]["M15"][-1]["time"]-900
    state, output, events = MarketState().process_hybrid(state, payload)
    assert output["state"] == "ARMED"
    assert state["setup"]["source_m15"] == payload["candles"]["M15"][-1]["time"]
    assert any(e["kind"] == "SETUP_REASSESSED" for e in events)
    assert state["setup"]["id"] == "armed-1"
    assert not any(e["kind"] == "CANCEL" for e in events)
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_conflicting_h4_h1_does_not_veto_m15_candidate():
    payload = feed()
    payload["candles"]["H1"] = feed(rising=False)["candles"]["H1"]
    _, output, events = MarketState().process_hybrid({}, payload)
    assert output["state"] == "ARMED"
    assert output["setup"]["side"] == "BUY"
    assert output["setup_mode"] == "COUNTERTREND"
    assert output["decision"] == "WAIT"
    assert not any(e["kind"] == "ENTRY" for e in events)


def test_expired_setup_cancels_and_audits():
    payload = feed()
    state = armed(payload)
    state["setup"]["expires"] = NOW-1
    _, output, events = MarketState().process_hybrid(state, payload)
    assert output["reason"] == "SETUP_EXPIRED"
    assert any(e["kind"] == "CANCEL" for e in events)


def test_repeated_posts_close_connections_explicitly(tmp_path, monkeypatch):
    import http.client
    import threading
    import time
    from http.server import HTTPServer
    from data_feed import live_server
    monkeypatch.setattr(live_server, "RUNTIME", tmp_path)
    monkeypatch.setattr(live_server, "_store", None)
    server = HTTPServer(("127.0.0.1", 0), live_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        for _ in range(20):
            body = json.dumps(feed(now=time.time())).encode()
            connection.request("POST", "/market", body, {"Content-Type": "application/json", "Connection": "keep-alive"})
            response = connection.getresponse()
            assert response.version == 11
            assert response.status == 200
            assert response.getheader("Connection") == "close"
            assert response.will_close
            assert json.loads(response.read())["status"] == "PROCESSED"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_expect_continue_for_history_payload(tmp_path, monkeypatch):
    import socket
    import threading
    import time
    from http.server import HTTPServer
    from data_feed import live_server
    monkeypatch.setattr(live_server, "RUNTIME", tmp_path)
    monkeypatch.setattr(live_server, "_store", None)
    server = HTTPServer(("127.0.0.1", 0), live_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps(feed(now=time.time())).encode()
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
            headers = ("POST /market HTTP/1.1\r\nHost: localhost\r\n"
                       "Expect: 100-continue\r\nContent-Type: application/json\r\n"
                       f"Content-Length: {len(body)}\r\n\r\n").encode()
            connection.sendall(headers)
            stream = connection.makefile("rb")
            assert stream.readline().startswith(b"HTTP/1.1 100 ")
            assert stream.readline() == b"\r\n"
            connection.sendall(body)
            assert stream.readline().startswith(b"HTTP/1.1 200 ")
            response_headers = {}
            while True:
                line = stream.readline()
                if line == b"\r\n":
                    break
                key, value = line.decode().split(":", 1)
                response_headers[key.lower()] = value.strip()
            assert response_headers["connection"] == "close"
            data = stream.read(int(response_headers["content-length"]))
            assert json.loads(data)["status"] == "PROCESSED"
            stream.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_countertrend_can_enter_with_m5_confirmation_and_live_price(side):
    buy = side == 'BUY'
    payload = feed(bid=100.3 if buy else 99.7, ask=100.4 if buy else 99.8, rising=buy)
    opposite = feed(rising=not buy)
    for tf in ('H4', 'H1'):
        payload['candles'][tf] = opposite['candles'][tf]
    payload['candles']['M5'][-1].update(
        open=99 if buy else 101, high=100.2 if buy else 101.1,
        low=98.9 if buy else 99.8, close=100.1 if buy else 99.9)
    state = armed(payload, side=side, zone_seen=True)
    state['setup'].update(sl=99 if buy else 101,
                          zone_low=98 if buy else 100, zone_high=100 if buy else 102)
    _, output, events = MarketState().process_hybrid(state, payload)
    assert output['state'] == 'ENTRY'
    assert output['decision'] == side
    assert output['paper_trade']['mode'] == 'COUNTERTREND'
    assert output['diagnostics']['higher_timeframe_veto'] is False
    assert len([e for e in events if e['kind'] == 'ENTRY']) == 1


def test_higher_timeframe_bearish_does_not_sell_into_m15_bullish_impulse():
    payload = feed(bid=105, ask=105.1)
    opposite = feed(rising=False)
    for tf in ('H4', 'H1'):
        payload['candles'][tf] = opposite['candles'][tf]
    state, output, events = MarketState().process_hybrid({}, payload)
    assert output['setup']['side'] == 'BUY'
    assert output['decision'] == 'WAIT'
    state, output, events = MarketState().process_hybrid(state, {**payload, 'quote': dict(time=NOW+5, bid=105, ask=105.1)})
    assert output['reason'] == 'NO_PRICE_CHASING'
    assert not any(e['kind'] == 'ENTRY' for e in events)


def test_early_m15_breakout_does_not_require_ema50_crossover():
    payload = feed(rising=False)
    bar = payload['candles']['M15'][-1]
    bar.update(open=100, high=105.5, low=99.8, close=105)
    features = {tf: FeatureEngine().calculate_history(bars) for tf, bars in payload['candles'].items()}
    assert features['M15']['direction'] == 'NEUTRAL'
    side, mode, center, basis = MarketState.select_setup(features, payload['candles'])
    assert side == 'BUY'
    assert mode == 'COUNTERTREND'
    assert center == features['M15']['recent_high']
    assert basis == 'BROKEN_M15_LEVEL'


def test_m15_refresh_preserves_observed_pullback_and_confirmation():
    payload = feed(bid=100.3, ask=100.4)
    payload['candles']['M5'][-1].update(open=99, high=100.2, low=98.9, close=100.1)
    state = armed(payload, zone_seen=True)
    state['setup'].update(sl=99, source_m15=payload['candles']['M15'][-1]['time']-900)
    _, output, events = MarketState().process_hybrid(state, payload)
    assert output['state'] == 'ENTRY'
    assert output['paper_trade']['id'] == 'armed-1'
    assert not any(e['kind'] == 'CANCEL' for e in events)


def test_neutral_pullback_does_not_erase_existing_setup():
    payload = feed()
    for bar in payload['candles']['M15'][-10:]:
        bar.update(open=99, high=100, low=98, close=99)
    state = armed(payload)
    _, output, events = MarketState().process_hybrid(state, payload)
    assert output['state'] == 'ARMED'
    assert output['diagnostics']['retained_pending_setup'] is True
    assert not any(e['kind'] == 'CANCEL' for e in events)


def test_cumulative_adverse_quotes_cancel_even_when_each_step_is_small():
    engine = MarketState()
    payload = feed(bid=99.4, ask=99.5)
    state = armed(payload)
    state['last_mid'] = 100.05
    for i, bid in enumerate([99.4, 98.8, 98.2]):
        payload = feed(now=NOW+i*5, bid=bid, ask=bid+.1)
        state, output, events = engine.process_hybrid(state, payload)
    assert output['state'] == 'CANCEL'
    assert output['reason'] == 'IMPULSE_OVERRIDE'


def test_wait_has_forward_quote_audit_and_blocking_reason(tmp_path):
    store = StateStore(tmp_path / 'engine.sqlite3')
    payload = feed()
    for tf in ('H4', 'H1', 'M15', 'M5'):
        for bar in payload['candles'][tf]:
            bar.update(open=99, high=100, low=98, close=99)
    output = store.process('XAUUSD', lambda s: MarketState().process_hybrid(s, payload))
    assert output['reason'] == 'NO_M15_STRUCTURAL_SETUP'
    with store.connect() as connection:
        row = connection.execute("select value from events where kind='EVALUATION'").fetchone()
    event = json.loads(row[0])
    assert event['bid'] == payload['quote']['bid']
    assert event['reason'] == output['reason']
    assert output['timeframes']['H4']['direction_checks']


def test_observed_pullback_stop_is_structural_and_frozen_after_entry():
    engine = MarketState()
    payload = feed(bid=100.3, ask=100.4)
    payload['candles']['M5'][-1].update(open=99, high=100.2, low=98.9, close=100.1)
    state = armed(payload, zone_seen=True)
    state['setup']['pullback_extreme'] = 99
    state, output, _ = engine.process_hybrid(state, payload)
    assert output['state'] == 'ENTRY'
    stop = output['paper_trade']['sl']
    assert 95 < stop < 98.9
    state, output, _ = engine.process_hybrid(state, feed(now=NOW+5, bid=101, ask=101.1))
    assert output['paper_trade']['sl'] == stop


def test_new_buy_zone_is_above_its_invalidation():
    _, output, _ = MarketState().process_hybrid({}, feed())
    setup = output['setup']
    assert setup['sl'] < setup['zone_low'] < setup['zone_high']


def test_countertrend_full_forward_lifecycle_without_injected_setup():
    engine = MarketState()
    payload = feed(bid=97.3, ask=97.4)
    for tf in ('H4', 'H1'):
        payload['candles'][tf] = feed(rising=False)['candles'][tf]
    state, output, _ = engine.process_hybrid({}, payload)
    assert output['state'] == 'ARMED'
    assert output['setup_mode'] == 'COUNTERTREND'
    payload['quote']['time'] += 5
    state, output, _ = engine.process_hybrid(state, payload)
    assert output['reason'] == 'PULLBACK_OBSERVED_WAIT_CONFIRMATION'
    payload['quote'].update(time=NOW+310, bid=97.85, ask=97.95)
    payload['candles']['M5'][-1].update(
        time=payload['candles']['M5'][-1]['time']+300,
        open=97.3, high=97.8, low=97.2, close=97.65)
    state, output, _ = engine.process_hybrid(state, payload)
    assert output['state'] == 'ENTRY'
    assert output['decision'] == 'BUY'
    tp = state['trade']['tp']
    payload['quote'].update(time=NOW+315, bid=tp+.01, ask=tp+.11)
    state, output, _ = engine.process_hybrid(state, payload)
    assert output['state'] == 'EXIT'
    assert output['reason'] == 'TP_TOUCHED'
    assert state['trade'] is None


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_m5_live_reversal_can_oppose_all_slow_timeframes(side):
    buy = side == 'BUY'
    payload = feed(bid=100.4 if buy else 99.6, ask=100.5 if buy else 99.7, rising=not buy)
    # The last closed M15, H1 and H4 all still point the other way.
    bars = payload['candles']['M5']
    for bar in bars[-6:-1]:
        bar.update(open=100, high=100.2, low=99.8, close=100)
    bars[-1].update(open=99.8 if buy else 100.2, high=100.3,
                    low=99.7, close=100.25 if buy else 99.75)
    _, output, _ = MarketState().process_hybrid({}, payload)
    assert output['setup']['side'] == side
    assert output['setup']['zone_basis'] in ('BROKEN_M5_LEVEL_LIVE_CONFIRMED', 'PRICE_REACTION')
    assert output['setup_mode'] == 'COUNTERTREND'
    assert output['decision'] == 'WAIT'  # still needs a new retest/confirmation


def test_sell_reversal_cancels_pending_buy_without_hedging():
    payload = feed(bid=99.6, ask=99.7)
    for bar in payload['candles']['M5'][-6:-1]:
        bar.update(open=100, high=100.2, low=99.8, close=100)
    payload['candles']['M5'][-1].update(open=100.2, high=100.3, low=99.7, close=99.75)
    state = armed(payload, side='BUY')
    state, output, events = MarketState().process_hybrid(state, payload)
    assert output['state'] == 'CANCEL'
    assert output['reason'] == 'SHORT_TERM_STRUCTURE_CHANGED'
    assert state.get('trade') is None
    payload['quote']['time'] += 5
    state, output, events = MarketState().process_hybrid(state, payload)
    assert output['state'] == 'ARMED'
    assert output['setup']['side'] == 'SELL'
    assert not any(e['kind'] == 'ENTRY' for e in events)
