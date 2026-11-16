"""H1CON_F1TP30_V1 — live PAPER_ONLY decision policy (no broker orders), with H1CON_RAW_V1 as a shadow.

Main (H1CON_F1TP30_V1): the entry signal of the user's EA "H1_con_cool" (core.h1con_ai.signal, evaluated
once on the first quote that carries a newly closed M15 bar), no AI, plus filter F1:
  BUY  only if the last CLOSED H1 bar closed above H1 EMA50,
  SELL only if the last CLOSED H1 bar closed below H1 EMA50.
TP = 30.0 / SL = 12.0 price units from the paper fill. One position at a time, no grid, no time filter.

Shadow (H1CON_RAW_V1): the previous main policy keeps running on the same signals in its own paper book:
every signal, TP = SL = 12.0. Shadow entries/exits are SHADOW_ENTRY / SHADOW_EXIT events.
A signal removed by F1 is logged as H1CON_SIGNAL_FILTERED (main only; the shadow still takes it).
The AI probability is still recorded on every entry as information only.

At install the H1CON_AI_V1 shadow is retired (kept under state['retired_shadow'] for the audit trail).
A main H1CON_RAW_V1 trade open at install keeps its id / TP / SL until it exits and is also copied to the
new shadow book so the H1CON_RAW_V1 record is continuous.
"""
from copy import deepcopy

from core import h1con_ai as H
from core.h1con_raw_policy import H1ConRaw, POLICY as SHADOW_POLICY

POLICY = 'H1CON_F1TP30_V1'
F1_VERSION = 1
SYSTEM_LABEL = 'H1CON_F1TP30_V1 main (no AI, F1, TP30/SL12) + H1CON_RAW_V1 shadow'
MAIN_TP, MAIN_SL = 30.0, 12.0
SHADOW_TP, SHADOW_SL = 12.0, 12.0
F1_EMA = 50


def f1_check(side, h1):
    """-> (ok, last_close, ema50) on closed H1 bars (oldest first)."""
    closes = [b['close'] for b in h1]
    ema = H.ema_series(closes, F1_EMA)[-1]
    ok = closes[-1] > ema if side == 'BUY' else closes[-1] < ema
    return ok, closes[-1], ema


class H1ConF1(H1ConRaw):
    MAIN = POLICY
    SHADOW = SHADOW_POLICY
    LABEL = SYSTEM_LABEL
    ENTRY_REASON = 'H1CON_F1_ENTRY'
    WAIT_REASONS = {'MAIN_BUSY': 'H1CON_SIGNAL_WHILE_POSITION_OPEN', 'FILTERED_F1': 'H1CON_SIGNAL_FILTERED_F1'}

    @staticmethod
    def migrate(state):
        if state.get('f1_version') == F1_VERSION:
            return state
        state = H1ConRaw.migrate(state)
        old_shadow = state.get('shadow') or {}
        book = state.get('book')
        shadow_book = deepcopy(book) if book and book.get('policy') == SHADOW_POLICY else None
        if shadow_book:
            shadow_book['component'] = 'SHADOW'
        state['retired_shadow'] = {'policy': old_shadow.get('policy'), 'book': deepcopy(old_shadow.get('book')),
                                   'retired_at': state.get('last_quote_time')}
        state['shadow'] = {'policy': SHADOW_POLICY, 'book': shadow_book}
        state['f1_version'] = F1_VERSION
        state['main_policy_since'] = state.get('last_quote_time') or None
        state['previous'] = {'policy': SHADOW_POLICY}
        return state

    def _trade(self, payload, now, bid, ask, side, d, m15_time, policy, component, reason, tp_d, sl_d, tag):
        s = 1 if side == 'BUY' else -1
        entry = ask if s == 1 else bid
        tid = f"{payload['symbol']}:{tag}:{now}"
        return {'id': tid, 'side': side, 'entry_time': now, 'entry_price': entry,
                'tp': entry + s * tp_d, 'sl': entry - s * sl_d, 'rr': tp_d / sl_d,
                'mfe_observed': 0.0, 'mae_observed': ask - bid,
                'selection': {'selection_reason': reason, 'ai_probability': round(d['p'], 4),
                              'threshold': d['threshold'], 'm15_bar_time': m15_time,
                              'features': {k: round(v, 5) for k, v in d['features'].items()}},
                'coverage_gap': False, 'basis': 'OBSERVED_QUOTE_PAPER_FILL', 'mode': reason,
                'component': component, 'component_id': tid, 'policy': policy}

    def _evaluate_both(self, state, payload, timeframes, now, bid, ask, m15_time, book_events):
        d = self.decide(payload['candles'], timeframes, now)
        info = {k: d.get(k) for k in ('status', 'side', 'p', 'threshold')}
        info['m15_bar_time'] = m15_time
        if d['status'] in ('NO_SIGNAL', 'INSUFFICIENT_HISTORY'):
            return info
        side = d['side']
        shadow = state['shadow']
        # shadow: H1CON_RAW_V1 rule (every signal, TP/SL 12), its own book
        info['shadow_status'] = 'SHADOW_BUSY'
        if shadow['book'] is None:
            shadow['book'] = self._trade(payload, now, bid, ask, side, d, m15_time, SHADOW_POLICY, 'SHADOW',
                                         'H1CON_RSI_RAW', SHADOW_TP, SHADOW_SL, 'H1RAW-SHADOW')
            book_events.append({'time': now, 'kind': 'SHADOW_ENTRY', 'trade': deepcopy(shadow['book'])})
            info['shadow_status'] = 'SHADOW_ENTERED'
        # main: F1 filter, then TP 30 / SL 12 when flat
        ok, close, ema = f1_check(side, payload['candles']['H1'][-H.WINDOW:])
        info['f1'] = {'ok': ok, 'h1_close': round(close, 2), 'h1_ema50': round(ema, 2)}
        if not ok:
            book_events.append({'time': now, 'kind': 'H1CON_SIGNAL_FILTERED', 'filter': 'F1', 'side': side,
                                'p': d['p'], 'h1_close': close, 'h1_ema50': ema, 'm15_bar_time': m15_time})
            info['status'] = 'FILTERED_F1'
        elif state['book'] is None:
            trade = self._trade(payload, now, bid, ask, side, d, m15_time, POLICY, 'H1CON_F1', 'H1CON_RSI_F1_TP30',
                                MAIN_TP, MAIN_SL, 'H1F1')
            state['book'] = trade
            book_events.append({'time': now, 'kind': 'ENTRY', 'trade': deepcopy(trade)})
            info['status'] = 'ENTERED'
        else:
            book_events.append({'time': now, 'kind': 'H1CON_SIGNAL_BUSY', 'side': side, 'p': d['p'],
                                'm15_bar_time': m15_time, 'open_trade': state['book']['id']})
            info['status'] = 'MAIN_BUSY'
        return info
