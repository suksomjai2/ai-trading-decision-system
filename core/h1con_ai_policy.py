"""H1CON_AI_V1 — live PAPER_ONLY decision policy (no broker orders).

Candidates: the entry setup of the user's EA "H1_con_cool" (first entry only, no grid), evaluated once
on the first quote that carries a newly closed M15 bar (core.h1con_ai.signal).
Decision: an exported gradient-boosted tree model (core/models/h1con_gbm_v1.json, pure Python) gives
P(TP 12.0 before SL 12.0); the candidate is taken when P > 1/(1+RR) + 0.05 (0.55 for RR 1).
No time-of-day filter. Paper fill at this quote (BUY ask / SELL bid), exits only on later quotes
(BUY bid / SELL ask; stop checked before target). One position at a time.

The V5 engine keeps running underneath for the audit trail and setup research; its own entries/exits
are recorded as V5_CANDIDATE_* only. An S5B (or V5) paper trade open at install keeps its id/TP/SL and
policy until it exits.
"""
import hashlib
from copy import deepcopy
from pathlib import Path

from core import h1con_ai as H
from core.market_state import MarketState

POLICY = 'H1CON_AI_V1'
VERSION = 1
MODEL_PATH = Path(__file__).resolve().parent / 'models' / 'h1con_gbm_v1.json'
MODEL_SHA256 = '5b743c91e14445cf8b51d4c69f161f3119d55d170f071a52e2266d418096887a'
NEED = {'M5': 49, 'M15': H.WINDOW, 'H1': 102, 'H4': 1}


def load_model(path=MODEL_PATH, expected=MODEL_SHA256):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f'H1CON model file changed: {digest}')
    return H.TreeModel.load(path)


class H1ConAI:
    def __init__(self, model=None):
        self.engine = MarketState()
        self.feature_engine = self.engine.feature_engine
        self.model = model or load_model()

    # -- state ---------------------------------------------------------
    @staticmethod
    def migrate(state):
        """Wrap an S5B or V5 state. An open paper trade keeps its id / TP / SL / policy."""
        if state.get('h1con_version') == VERSION:
            return state
        if state.get('s5b_version') is not None:
            v5 = deepcopy(state.get('v5') or {})
            book = deepcopy(state.get('book'))
            previous = {'policy': 'SESSION_BIAS_S5B_V1', 'signal': deepcopy(state.get('signal'))}
        else:
            v5 = deepcopy(state)
            book = None
            if v5.get('trade'):
                book = dict(deepcopy(v5['trade']), component='LEGACY', component_id=v5['trade']['id'])
            previous = {'policy': 'CONTEXTUAL_REACTION_V5'}
        v5['last_result'] = None
        return {'h1con_version': VERSION, 'v5': v5, 'signal': {'last_m15': None}, 'book': book,
                'previous': previous, 'trade': deepcopy(book),
                'last_quote_time': state.get('last_quote_time', 0), 'last_result': state.get('last_result')}

    # -- decision (pure; also used by the offline parity test) ----------
    def decide(self, candles, timeframes, now):
        """-> dict(status, side, p, threshold, features) for the closed bars in `candles`."""
        for tf, n in NEED.items():
            if len(candles.get(tf) or []) < n:
                return dict(status='INSUFFICIENT_HISTORY', side=None)
        w = {tf: candles[tf][-H.WINDOW:] for tf in ('M5', 'M15', 'H1', 'H4')}
        side = H.signal(w['H1'], w['M15'])
        if not side:
            return dict(status='NO_SIGNAL', side=None)
        feats = H.features(side, now, w['M5'], w['M15'], w['H1'], w['H4'], timeframes)
        p = self.model.proba(feats)
        threshold = 1 / (1 + H.TP_DISTANCE / H.SL_DISTANCE) + H.MARGIN
        return dict(status='TAKE' if p > threshold else 'SKIPPED_BY_AI', side=side, p=p, threshold=threshold,
                    features=feats)

    # -- main ----------------------------------------------------------
    def process(self, state, payload):
        state = self.migrate(deepcopy(state or {}))
        quote = payload['quote']
        now, bid, ask = quote['time'], quote['bid'], quote['ask']
        if now <= state.get('last_quote_time', 0):
            return state, deepcopy(state.get('last_result')), []
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
        trade = state['book']
        if trade and trade.get('component') == 'LEGACY':      # 1) exits first
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
        elif trade:                                            # own trades and S5B trades: quote TP/SL
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
                book_events.append({'time': now, 'kind': 'EXIT', 'trade': deepcopy(trade)})
                state['book'] = None

        info = None                                            # 2) a newly closed M15 bar, once, when flat
        m15 = payload['candles']['M15']
        m15_time = m15[-1]['time'] if m15 else None
        gen = state['signal']
        if m15_time is not None and gen.get('last_m15') != m15_time:
            first_bar = gen.get('last_m15') is None
            gen['last_m15'] = m15_time
            if state['book'] is None and not first_bar and value['timeframes']['M15']['atr14'] > 0:
                info = self._evaluate(state, payload, value['timeframes'], now, bid, ask, m15_time, book_events)
        events.extend(book_events)

        result = self._result(value, state, book_events, info)
        if evaluation is not None:
            evaluation.update(component_stage=evaluation.get('stage'), component_reason=evaluation.get('reason'),
                              stage=result['state'], reason=result['reason'],
                              diagnostics=deepcopy(result['diagnostics']))
        state['trade'] = deepcopy(state['book'])
        state['last_quote_time'] = now
        state['last_result'] = deepcopy(result)
        return state, result, events

    def _evaluate(self, state, payload, timeframes, now, bid, ask, m15_time, book_events):
        d = self.decide(payload['candles'], timeframes, now)
        info = {k: d.get(k) for k in ('status', 'side', 'p', 'threshold')}
        info['m15_bar_time'] = m15_time
        if d['status'] in ('NO_SIGNAL', 'INSUFFICIENT_HISTORY'):
            return info
        if d['status'] == 'SKIPPED_BY_AI':
            book_events.append({'time': now, 'kind': 'H1CON_SIGNAL_SKIPPED', **info})
            return info
        side = d['side']
        s = 1 if side == 'BUY' else -1
        entry = ask if s == 1 else bid
        tid = f"{payload['symbol']}:H1CON:{now}"
        trade = {'id': tid, 'side': side, 'entry_time': now, 'entry_price': entry,
                 'tp': entry + s * H.TP_DISTANCE, 'sl': entry - s * H.SL_DISTANCE, 'rr': H.TP_DISTANCE / H.SL_DISTANCE,
                 'mfe_observed': 0.0, 'mae_observed': ask - bid,
                 'selection': {'selection_reason': 'H1CON_RSI_AI', 'ai_probability': round(d['p'], 4),
                               'threshold': d['threshold'], 'm15_bar_time': m15_time,
                               'features': {k: round(v, 5) for k, v in d['features'].items()}},
                 'coverage_gap': False, 'basis': 'OBSERVED_QUOTE_PAPER_FILL', 'mode': 'H1CON_RSI_AI',
                 'component': 'H1CON', 'component_id': tid, 'policy': POLICY}
        state['book'] = trade
        book_events.append({'time': now, 'kind': 'ENTRY', 'trade': deepcopy(trade)})
        info['status'] = 'ENTERED'
        return info

    # -- output ----------------------------------------------------------
    @staticmethod
    def _result(value, state, book_events, info):
        result = deepcopy(value)
        d = result.setdefault('diagnostics', {})
        d.update(component_policy=d.get('policy'), policy=POLICY,
                 component_stage=value.get('state'), component_reason=value.get('reason'),
                 last_signal=deepcopy(info) if info else None)
        target = lambda t: {'action': t['side'], 'target_price': t['tp'], 'invalid_price': t['sl']}
        trade = state['book']
        entry = next((e['trade'] for e in book_events if e['kind'] == 'ENTRY'), None)
        exit_ = next((e['trade'] for e in book_events if e['kind'] == 'EXIT'), None)
        if entry:
            result.update(decision=entry['side'], state='ENTRY', reason='H1CON_AI_ENTRY', paper_trade=deepcopy(entry),
                          target=target(entry), setup_direction=entry['side'], setup_mode=entry['mode'])
        elif exit_:
            result.update(decision='EXIT', state='EXIT', reason=exit_.get('outcome'), paper_trade=deepcopy(exit_),
                          target=target(exit_), setup_mode=exit_.get('mode'))
        elif trade:
            result.update(decision='WAIT', state='MANAGE', reason='PAPER_POSITION_OPEN', paper_trade=deepcopy(trade),
                          target=target(trade), setup_direction=trade['side'], setup_mode=trade.get('mode'))
        else:
            reason = 'WAIT_H1CON_SETUP'
            if info and info['status'] == 'SKIPPED_BY_AI':
                reason = 'H1CON_SIGNAL_SKIPPED_BY_AI'
            result.update(decision='WAIT', state='WAIT', reason=reason, paper_trade=None, target=None,
                          setup_direction=(info or {}).get('side'), setup_mode='H1CON_RSI_AI')
        e = result.setdefault('entry', {})
        e['action'] = result.get('decision')
        return result
