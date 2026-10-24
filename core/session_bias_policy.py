"""SESSION_BIAS_S5B_V1 — live PAPER_ONLY decision policy (no broker orders).

Signals are evaluated once, on the first quote that carries a newly closed M5 bar,
from the features of the closed bars known at that moment (first match wins):

  * H1_PULLBACK — H1 trend (EMA20 vs EMA50 and EMA20 slope agree). Within the last
    4 closed M5 bars price touched the closed-M15 EMA20; the last M5 closes back on
    the trend side of that EMA and beyond the previous M5 bar's extreme.
    Stop 1.0 x M15 ATR, target 1.5 x M15 ATR from the paper fill.
  * RANGE_MID — closed M15 has no trend and the previous 20 closed M15 bars (the
    latest closed M15 excluded) span at least 2 x ATR. The M5 bar wicks beyond that
    range and closes back inside against its open. Stop 0.3 x ATR beyond the wick,
    target = middle of the range.

Session filter (Asia/Bangkok, UTC+7, quote time):
    07:00-14:00 BUY only  |  19:30-02:00 SELL only  |  other hours: no new entry.
A signal on the wrong side is dropped (the next family is NOT tried instead).

Paper fill at this quote (BUY ask / SELL bid); exits only on later quotes
(BUY bid / SELL ask; stop checked before target). One position at a time;
signals that appear while a position is open are not taken later.

The V5 engine keeps running underneath on its own state for the audit trail
(CLOSED_CONTEXT, setup research) and to finish a V5 trade that was open at
install time (LEGACY). Its own entries/exits are recorded as V5_CANDIDATE_* only.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from core.market_state import MarketState

POLICY = 'SESSION_BIAS_S5B_V1'
VERSION = 1
BANGKOK = timezone(timedelta(hours=7))
CONFIG = dict(pullback_touch_bars=4, pullback_stop_atr=1.0, pullback_target_atr=1.5,
              range_bars=20, range_min_atr=2.0, range_stop_atr=0.3,
              asia=(7.0, 14.0, 'BUY'), ny=(19.5, 26.0, 'SELL'))


def trend(features, tf):
    c = features[tf]['direction_checks']
    if c['ema20_above_ema50'] and c['ema20_rising']:
        return 1
    if not c['ema20_above_ema50'] and not c['ema20_rising']:
        return -1
    return 0


def session_bias(now):
    """('ASIA'|'NY'|None, allowed side or None) for a quote time."""
    local = datetime.fromtimestamp(now, BANGKOK)
    x = local.hour + local.minute / 60 + local.second / 3600
    xx = x + 24 if x < 7 else x
    a0, a1, aside = CONFIG['asia']
    n0, n1, nside = CONFIG['ny']
    if a0 <= x < a1:
        return 'ASIA', aside
    if n0 <= xx < n1:
        return 'NY', nside
    return None, None


def pullback_signal(features, candles):
    """('BUY'|'SELL', stop_distance, target_distance, 'H1_PULLBACK') or None."""
    t = trend(features, 'H1')
    atr, ema = features['M15']['atr14'], features['M15']['ema20']
    m5 = candles['M5']
    n = CONFIG['pullback_touch_bars']
    if t == 0 or len(m5) < n:
        return None
    last, prev = m5[-1], m5[-2]
    touched = (min(x['low'] for x in m5[-n:]) <= ema if t == 1 else max(x['high'] for x in m5[-n:]) >= ema)
    if not touched:
        return None
    if t == 1 and last['close'] > ema and last['close'] > prev['high']:
        return 'BUY', CONFIG['pullback_stop_atr'] * atr, CONFIG['pullback_target_atr'] * atr, 'H1_PULLBACK'
    if t == -1 and last['close'] < ema and last['close'] < prev['low']:
        return 'SELL', CONFIG['pullback_stop_atr'] * atr, CONFIG['pullback_target_atr'] * atr, 'H1_PULLBACK'
    return None


def range_signal(features, candles):
    """('BUY'|'SELL', absolute stop, absolute target, 'RANGE_MID') or None."""
    m15 = candles['M15']
    n = CONFIG['range_bars']
    if trend(features, 'M15') != 0 or len(m15) < n + 1:
        return None
    atr = features['M15']['atr14']
    last = candles['M5'][-1]
    window = m15[-(n + 1):-1]
    hi = max(x['high'] for x in window)
    lo = min(x['low'] for x in window)
    mid = (hi + lo) / 2
    if hi - lo < CONFIG['range_min_atr'] * atr:
        return None
    if last['high'] > hi and last['close'] < hi and last['close'] < last['open']:
        return 'SELL', last['high'] + CONFIG['range_stop_atr'] * atr, mid, 'RANGE_MID'
    if last['low'] < lo and last['close'] > lo and last['close'] > last['open']:
        return 'BUY', last['low'] - CONFIG['range_stop_atr'] * atr, mid, 'RANGE_MID'
    return None


def first_signal(features, candles):
    for fn in (pullback_signal, range_signal):
        signal = fn(features, candles)
        if signal:
            return signal
    return None


class SessionBiasS5B:
    def __init__(self):
        self.engine = MarketState()
        self.feature_engine = self.engine.feature_engine

    # -- state ---------------------------------------------------------
    @staticmethod
    def migrate(state):
        """Wrap a V5 MarketState state. An open V5 trade keeps its id/TP/SL/policy (LEGACY)."""
        if state.get('s5b_version') == VERSION:
            return state
        v5 = deepcopy(state)
        v5['last_result'] = None
        book = None
        if v5.get('trade'):
            book = dict(deepcopy(v5['trade']), component='LEGACY', component_id=v5['trade']['id'])
        return {'s5b_version': VERSION, 'v5': v5,
                'signal': {'last_m5': None},
                'book': book,
                # Read-only mirror of the booked position for the daily report / tools reading state['trade'].
                'trade': deepcopy(book),
                'last_quote_time': state.get('last_quote_time', 0), 'last_result': state.get('last_result')}

    # -- main ----------------------------------------------------------
    def process(self, state, payload):
        state = self.migrate(deepcopy(state or {}))
        quote = payload['quote']
        now, bid, ask = quote['time'], quote['bid'], quote['ask']
        if now <= state.get('last_quote_time', 0):
            return state, deepcopy(state.get('last_result')), []
        previous_quote = state.get('last_quote_time', 0)
        v5_state, value, v5_events = self.engine.process_hybrid(state['v5'], payload)
        v5_state['last_result'] = None                       # bounded; duplicates are handled here
        state['v5'] = v5_state
        features = value['timeframes']
        events, v5_exits, evaluation = [], {}, None
        for e in v5_events:
            if e['kind'] == 'ENTRY':
                e = dict(e, kind='V5_CANDIDATE_ENTRY')
            elif e['kind'] == 'EXIT':
                e = dict(e, kind='V5_CANDIDATE_EXIT'); v5_exits[e['trade']['id']] = e['trade']
            elif e['kind'] == 'EVALUATION':
                evaluation = e
            events.append(e)

        book_events = []
        trade = state['book']
        if trade and trade['component'] == 'LEGACY':          # 1) exits first
            exit_ = v5_exits.get(trade['component_id'])
            if exit_:
                trade.update({k: exit_[k] for k in ('outcome', 'exit_time', 'exit_observed_price', 'mfe_observed',
                                                    'mae_observed', 'coverage_gap', 'outcome_evidence') if k in exit_})
                book_events.append({'time': now, 'kind': 'EXIT', 'trade': deepcopy(trade)})
                state['book'] = None
            else:
                live = v5_state.get('trade')
                if live and live.get('id') == trade['component_id']:
                    for k in ('mfe_observed', 'mae_observed', 'coverage_gap', 'unresolved'):
                        if k in live:
                            trade[k] = live[k]
        elif trade:
            s = 1 if trade['side'] == 'BUY' else -1
            px = bid if s == 1 else ask
            if now - previous_quote > 30:
                trade['coverage_gap'] = True
            trade['mfe_observed'] = max(trade['mfe_observed'], s * (px - trade['entry_price']))
            trade['mae_observed'] = max(trade['mae_observed'], -s * (px - trade['entry_price']))
            outcome = ('SL_TOUCHED' if s * (px - trade['sl']) <= 0 else
                       'TP_TOUCHED' if s * (px - trade['tp']) >= 0 else None)
            if outcome:
                trade.update(outcome=outcome, exit_time=now, exit_observed_price=px, outcome_evidence='OBSERVED_QUOTE')
                book_events.append({'time': now, 'kind': 'EXIT', 'trade': deepcopy(trade)})
                state['book'] = None

        # 2) a newly closed M5 bar is evaluated once; only when flat
        signal_info = None
        m5 = payload['candles']['M5']
        m5_time = m5[-1]['time'] if m5 else None
        gen = state['signal']
        if m5_time is not None and gen.get('last_m5') != m5_time:
            first_bar = gen.get('last_m5') is None              # first quote after install/restart of state
            gen['last_m5'] = m5_time
            if state['book'] is None and not first_bar and features['M15']['atr14'] > 0:
                signal_info = self._evaluate(state, payload, features, now, bid, ask, m5_time, book_events)
        events.extend(book_events)

        result = self._result(value, state, book_events, signal_info, now)
        if evaluation is not None:
            evaluation.update(component_stage=evaluation.get('stage'), component_reason=evaluation.get('reason'),
                              stage=result['state'], reason=result['reason'],
                              diagnostics=deepcopy(result['diagnostics']))
        state['trade'] = deepcopy(state['book'])              # mirror only; never read back as a decision
        state['last_quote_time'] = now
        state['last_result'] = deepcopy(result)
        return state, result, events

    def _evaluate(self, state, payload, features, now, bid, ask, m5_time, book_events):
        signal = first_signal(features, payload['candles'])
        session, allowed = session_bias(now)
        if not signal:
            return dict(status='NO_SIGNAL', session=session, allowed_side=allowed)
        side, a, c, name = signal
        info = dict(status='SIGNAL', signal=name, side=side, session=session, allowed_side=allowed, m5_bar_time=m5_time)
        if allowed is None:
            info['status'] = 'SKIPPED_OUTSIDE_SESSION'
            book_events.append({'time': now, 'kind': 'S5B_SIGNAL_SKIPPED', **info})
            return info
        if side != allowed:
            info['status'] = 'SKIPPED_AGAINST_SESSION_BIAS'
            book_events.append({'time': now, 'kind': 'S5B_SIGNAL_SKIPPED', **info})
            return info
        s = 1 if side == 'BUY' else -1
        entry = ask if s == 1 else bid
        if name == 'RANGE_MID':
            stop, target = a, c
        else:
            stop, target = entry - s * a, entry + s * c
        risk, reward = s * (entry - stop), s * (target - entry)
        if risk <= 0 or reward <= 0:
            info['status'] = 'SKIPPED_PRICE_ALREADY_BEYOND_LEVEL'
            book_events.append({'time': now, 'kind': 'S5B_SIGNAL_SKIPPED', **info})
            return info
        trade = {'id': f"{payload['symbol']}:S5B:{now}", 'side': side, 'entry_time': now, 'entry_price': entry,
                 'tp': target, 'sl': stop, 'rr': reward / risk, 'mfe_observed': 0.0, 'mae_observed': ask - bid,
                 'selection': {'selection_reason': name, 'session': session, 'm5_bar_time': m5_time,
                               'h1_trend': trend(features, 'H1'), 'm15_trend': trend(features, 'M15'),
                               'm15_atr14': features['M15']['atr14'], 'm15_ema20': features['M15']['ema20']},
                 'coverage_gap': False, 'basis': 'OBSERVED_QUOTE_PAPER_FILL', 'mode': name,
                 'component': 'S5B', 'component_id': f"{payload['symbol']}:S5B:{now}", 'policy': POLICY}
        state['book'] = trade
        book_events.append({'time': now, 'kind': 'ENTRY', 'trade': deepcopy(trade)})
        info['status'] = 'ENTERED'
        return info

    # -- output ----------------------------------------------------------
    @staticmethod
    def _result(value, state, book_events, signal_info, now):
        result = deepcopy(value)
        d = result.setdefault('diagnostics', {})
        session, allowed = session_bias(now)
        d.update(component_policy=d.get('policy'), policy=POLICY,
                 component_stage=value.get('state'), component_reason=value.get('reason'),
                 session=session or 'OUTSIDE', session_allowed_side=allowed,
                 h1_trend={1: 'UP_TREND', -1: 'DOWN_TREND', 0: 'NO_TREND'}[trend(value['timeframes'], 'H1')],
                 m15_trend={1: 'UP_TREND', -1: 'DOWN_TREND', 0: 'NO_TREND'}[trend(value['timeframes'], 'M15')],
                 last_signal=deepcopy(signal_info) if signal_info else None)
        target = lambda t: {'action': t['side'], 'target_price': t['tp'], 'invalid_price': t['sl']}
        trade = state['book']
        entry = next((e['trade'] for e in book_events if e['kind'] == 'ENTRY'), None)
        exit_ = next((e['trade'] for e in book_events if e['kind'] == 'EXIT'), None)
        if entry:
            result.update(decision=entry['side'], state='ENTRY', reason='S5B_' + entry['mode'] + '_ENTRY',
                          paper_trade=deepcopy(entry), target=target(entry), setup_direction=entry['side'],
                          setup_mode=entry['mode'])
        elif exit_:
            result.update(decision='EXIT', state='EXIT', reason=exit_.get('outcome'), paper_trade=deepcopy(exit_),
                          target=target(exit_), setup_mode=exit_.get('mode'))
        elif trade:
            result.update(decision='WAIT', state='MANAGE', reason='PAPER_POSITION_OPEN', paper_trade=deepcopy(trade),
                          target=target(trade), setup_direction=trade['side'], setup_mode=trade.get('mode'))
        else:
            reason = ('WAIT_SESSION_' + session + '_' + allowed + '_ONLY') if session else 'WAIT_OUTSIDE_SESSION'
            if signal_info and signal_info['status'].startswith('SKIPPED'):
                reason = signal_info['status']
            result.update(decision='WAIT', state='WAIT', reason=reason, paper_trade=None, target=None,
                          setup_direction=allowed, setup_mode='SESSION_BIAS')
        e = result.setdefault('entry', {})
        e['action'] = result.get('decision')
        return result
