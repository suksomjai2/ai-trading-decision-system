"""H1CON_RAW_V1 — live PAPER_ONLY decision policy (no broker orders), with H1CON_AI_V1 as a shadow.

Main (H1CON_RAW_V1): every entry signal of the user's EA "H1_con_cool" (first entry only, no grid;
core.h1con_ai.signal, evaluated once on the first quote that carries a newly closed M15 bar) is taken
when no main position is open. TP = SL = 12.0 price units. No AI filter, no time-of-day filter.

Shadow (H1CON_AI_V1): the previous live policy keeps running on the same signals with its own paper
book: the exported gradient-boosted model (core/models/h1con_gbm_v1.json) must give
P(TP before SL) > 0.55. Shadow entries/exits are SHADOW_ENTRY / SHADOW_EXIT events; shadow skips are
H1CON_SIGNAL_SKIPPED (shadow=True). The shadow never changes the main decision.

The AI probability is recorded on every main entry as information only.
Paper fill at this quote (BUY ask / SELL bid); exits only on later quotes (BUY bid / SELL ask; stop
checked before target). The V5 engine keeps running underneath for the audit trail and research.
A main trade open at install (H1CON_AI_V1, S5B or V5) keeps its id / TP / SL / policy until it exits;
an open H1CON_AI_V1 trade is also copied to the shadow book so the shadow record is continuous.
"""
from copy import deepcopy

from core import h1con_ai as H
from core.h1con_ai_policy import H1ConAI, POLICY as SHADOW_POLICY

POLICY = 'H1CON_RAW_V1'
RAW_VERSION = 1
SYSTEM_LABEL = 'H1CON_RAW_V1 main (no AI) + H1CON_AI_V1 shadow'


def _quote_exit(trade, now, bid, ask, previous_quote):
    """Update MFE/MAE and return the exit outcome (or None) for a quote-managed paper trade."""
    s = 1 if trade['side'] == 'BUY' else -1
    px = bid if s == 1 else ask
    if now - previous_quote > 30:
        trade['coverage_gap'] = True
    trade['mfe_observed'] = max(trade.get('mfe_observed', 0.0), s * (px - trade['entry_price']))
    trade['mae_observed'] = max(trade.get('mae_observed', 0.0), -s * (px - trade['entry_price']))
    outcome = ('SL_TOUCHED' if s * (px - trade['sl']) <= 0 else
               'TP_TOUCHED' if s * (px - trade['tp']) >= 0 else None)
    if outcome:
        trade.update(outcome=outcome, exit_time=now, exit_observed_price=px, outcome_evidence='OBSERVED_QUOTE')
    return outcome


class H1ConRaw(H1ConAI):
    """Main = H1CON without AI; shadow = H1CON_AI_V1. Reuses H1ConAI.decide for signal + probability."""

    @staticmethod
    def migrate(state):
        if state.get('raw_version') == RAW_VERSION:
            return state
        before = state.get('h1con_version')
        state = H1ConAI.migrate(state)
        book = state.get('book')
        shadow_book = deepcopy(book) if book and book.get('policy') == SHADOW_POLICY else None
        if shadow_book:
            shadow_book['component'] = 'SHADOW'
        state['raw_version'] = RAW_VERSION
        state['shadow'] = {'policy': SHADOW_POLICY, 'book': shadow_book}
        state['main_policy_since'] = state.get('last_quote_time') or None
        if before is not None:
            state['previous'] = {'policy': SHADOW_POLICY}
        return state

    def process(self, state, payload):
        state = self.migrate(deepcopy(state or {}))
        quote = payload['quote']
        now, bid, ask = quote['time'], quote['bid'], quote['ask']
        if now <= state.get('last_quote_time', 0):
            return state, deepcopy(state.get('last_result')), []
        if not state.get('main_policy_since'):
            state['main_policy_since'] = now
        previous_quote = state.get('last_quote_time', 0)
        v5_state, value, v5_events = self.engine.process_hybrid(state['v5'], payload)
        v5_state['last_result'] = None
        state['v5'] = v5_state
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
        trade = state['book']                                  # 1) exits first: main
        if trade and trade.get('component') == 'LEGACY':
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
        elif trade and _quote_exit(trade, now, bid, ask, previous_quote):
            book_events.append({'time': now, 'kind': 'EXIT', 'trade': deepcopy(trade)})
            state['book'] = None
        shadow = state['shadow']                               # shadow exits
        if shadow['book'] and _quote_exit(shadow['book'], now, bid, ask, previous_quote):
            book_events.append({'time': now, 'kind': 'SHADOW_EXIT', 'trade': deepcopy(shadow['book'])})
            shadow['book'] = None

        info = None                                            # 2) a newly closed M15 bar, once
        m15 = payload['candles']['M15']
        m15_time = m15[-1]['time'] if m15 else None
        gen = state['signal']
        if m15_time is not None and gen.get('last_m15') != m15_time:
            first_bar = gen.get('last_m15') is None
            gen['last_m15'] = m15_time
            if not first_bar and value['timeframes']['M15']['atr14'] > 0 and (state['book'] is None or shadow['book'] is None):
                info = self._evaluate_both(state, payload, value['timeframes'], now, bid, ask, m15_time, book_events)
        events.extend(book_events)

        result = self._result(value, state, book_events, info)
        d = result['diagnostics']
        d.update(policy=POLICY, system_label=SYSTEM_LABEL, shadow_policy=SHADOW_POLICY,
                 main_policy_since=state.get('main_policy_since'),
                 shadow_position=deepcopy(shadow['book']))
        if result.get('reason') == 'H1CON_AI_ENTRY':
            result['reason'] = 'H1CON_RAW_ENTRY'
        if result.get('reason') == 'WAIT_H1CON_SETUP' and info and info.get('status') == 'MAIN_BUSY':
            result['reason'] = 'H1CON_SIGNAL_WHILE_POSITION_OPEN'
        if evaluation is not None:
            evaluation.update(component_stage=evaluation.get('stage'), component_reason=evaluation.get('reason'),
                              stage=result['state'], reason=result['reason'],
                              diagnostics=deepcopy(result['diagnostics']))
        state['trade'] = deepcopy(state['book'])
        state['last_quote_time'] = now
        state['last_result'] = deepcopy(result)
        return state, result, events

    def _new_trade(self, payload, now, bid, ask, side, d, m15_time, policy, component, reason):
        s = 1 if side == 'BUY' else -1
        entry = ask if s == 1 else bid
        tid = f"{payload['symbol']}:{'H1RAW' if component == 'H1CON_RAW' else 'H1AI-SHADOW'}:{now}"
        return {'id': tid, 'side': side, 'entry_time': now, 'entry_price': entry,
                'tp': entry + s * H.TP_DISTANCE, 'sl': entry - s * H.SL_DISTANCE, 'rr': H.TP_DISTANCE / H.SL_DISTANCE,
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
        # shadow: H1CON_AI_V1 rule (P above threshold), its own book
        info['shadow_status'] = 'SHADOW_BUSY'
        if shadow['book'] is None:
            if d['status'] == 'TAKE':
                shadow['book'] = self._new_trade(payload, now, bid, ask, side, d, m15_time, SHADOW_POLICY,
                                                 'SHADOW', 'H1CON_RSI_AI')
                book_events.append({'time': now, 'kind': 'SHADOW_ENTRY', 'trade': deepcopy(shadow['book'])})
                info['shadow_status'] = 'SHADOW_ENTERED'
            else:
                book_events.append({'time': now, 'kind': 'H1CON_SIGNAL_SKIPPED', 'shadow': True,
                                    **{k: info[k] for k in ('status', 'side', 'p', 'threshold', 'm15_bar_time')}})
                info['shadow_status'] = 'SKIPPED_BY_AI'
        # main: every signal when flat
        if state['book'] is None:
            trade = self._new_trade(payload, now, bid, ask, side, d, m15_time, POLICY, 'H1CON_RAW', 'H1CON_RSI_RAW')
            state['book'] = trade
            book_events.append({'time': now, 'kind': 'ENTRY', 'trade': deepcopy(trade)})
            info['status'] = 'ENTERED'
        else:
            book_events.append({'time': now, 'kind': 'H1CON_SIGNAL_BUSY', 'side': side, 'p': d['p'],
                                'm15_bar_time': m15_time, 'open_trade': state['book']['id']})
            info['status'] = 'MAIN_BUSY'
        return info
