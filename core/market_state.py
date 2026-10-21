from core.feature_engine import FeatureEngine
from core.decision_engine import DecisionEngine
from core.risk_engine import RiskEngine
from core.feedback_engine import FeedbackEngine
from core.performance_engine import PerformanceEngine
from core.calibration_engine import CalibrationEngine
from core.risk_analysis_engine import RiskAnalysisEngine
from core.evaluation_engine import EvaluationEngine
from core.market_regime_engine import MarketRegimeEngine
from core.decision_filter import DecisionFilter
from core.setup_intelligence import SetupIntelligence
from core.setup_confidence import SetupConfidence
from core.entry_decision import EntryDecision
from core.target_engine import TargetEngine
from core.exit_engine import ExitEngine
from core.confidence_engine import ConfidenceEngine
from core.decision_reason import DecisionReason
from core.memory_engine import MemoryEngine
from core.historical_engine import HistoricalEngine
from core.context_engine import ContextEngine


class MarketState:

    def __init__(self):
        self.feature_engine = FeatureEngine()
        self.decision_engine = DecisionEngine()
        self.risk_engine = RiskEngine()
        self.feedback_engine = FeedbackEngine()
        self.performance_engine = PerformanceEngine()
        self.calibration_engine = CalibrationEngine()
        self.risk_analysis_engine = RiskAnalysisEngine()
        self.evaluation_engine = EvaluationEngine()
        self.market_regime_engine = MarketRegimeEngine()
        self.decision_filter = DecisionFilter()
        self.setup_engine = SetupIntelligence()
        self.setup_confidence = SetupConfidence()
        self.entry_engine = EntryDecision()
        self.target_engine = TargetEngine()
        self.exit_engine = ExitEngine()
        self.confidence_engine = ConfidenceEngine()
        self.reason_engine = DecisionReason()
        self.memory_engine = MemoryEngine()
        self.historical_engine = HistoricalEngine()
        self.context_engine = ContextEngine()


    def analyze_history(self, candles):
        if not candles:
            return {
                "context": "NEUTRAL",
                "risk": {}
            }

        first_close = candles[0]["close"]
        last_close = candles[-1]["close"]

        if last_close > first_close:
            context = "ALIGNED"
        elif last_close < first_close:
            context = "ALIGNED"
        else:
            context = "NEUTRAL"

        ranges = [
            candle["high"] - candle["low"]
            for candle in candles
        ]

        average_range = sum(ranges) / len(ranges)

        return {
            "context": context,
            "risk": {
                "average_range": average_range
            }
        }

    def analyze(self, market_data):

        features = self.feature_engine.calculate_features(
            market_data
        )

        decision = self.decision_engine.evaluate(
            features
        )

        risk = self.risk_engine.evaluate(
            decision,
            features
        )

        confidence = self.confidence_engine.evaluate(
            decision,
            features
        )

        reason = self.reason_engine.generate(
            decision,
            confidence,
            risk
        )

        result = {
            "features": features,
            "decision": decision,
            "risk": risk,
            "confidence": confidence,
            "reason": reason
        }

        self.memory_engine.store(
            result
        )

        history = self.historical_engine.analyze(
            self.memory_engine.get_history()
        )

        context = self.context_engine.analyze(
            features,
            history
        )

        result["history"] = history
        result["context"] = context

        return result


    def learn_from_result(self, decision, outcome):
        """
        Update adaptive weight from real market outcome.
        """
        self.feedback_engine.record(
            decision,
            outcome
        )

        return {
            "accuracy": self.feedback_engine.accuracy(),
            "weights": self.feedback_engine.get_weights()
        }


    def memory_status(self):

        return {
            "feedback_count": len(
                self.feedback_engine.history()
            ),
            "accuracy": self.feedback_engine.accuracy(),
            "weights": self.feedback_engine.get_weights()
        }


    def performance_status(self):

        return self.performance_engine.evaluate(
            self.feedback_engine.history()
        )


    def calibration_status(self):

        return self.calibration_engine.evaluate(
            self.feedback_engine.history()
        )


    def risk_analysis_status(self):

        return self.risk_analysis_engine.evaluate(
            self.feedback_engine.history()
        )


    def evaluation_status(self):

        return self.evaluation_engine.evaluate(
            self
        )


    def regime_status(self, features):

        return self.market_regime_engine.evaluate(
            features
        )


    def filtered_decision(self, decision, features):

        regime = self.market_regime_engine.evaluate(
            features
        )

        return self.decision_filter.evaluate(
            decision,
            regime
        )


    def setup_status(self, features):

        regime = self.market_regime_engine.evaluate(
            features
        )

        return self.setup_engine.evaluate(
            features,
            regime
        )


    def setup_confidence_status(self, features):

        setup = self.setup_status(
            features
        )

        return self.setup_confidence.evaluate(
            setup
        )


    def entry_status(self, features):

        setup = self.setup_status(
            features
        )

        confidence = self.setup_confidence.evaluate(
            setup
        )

        return self.entry_engine.evaluate(
            setup,
            confidence
        )


    def target_status(self, price, features, action):

        return self.target_engine.evaluate(
            price,
            features,
            action
        )


    def exit_status(self, price, target):

        return self.exit_engine.evaluate(
            price,
            target
        )


    def trading_decision(self, price, features):

        # 1. Entry analysis
        entry = self.entry_status(features)

        action = entry.get(
            "action",
            "WAIT"
        )

        # 2. No trade
        if action == "WAIT":
            return {
                "decision": "WAIT",
                "entry": entry,
                "target": None
            }

        # 3. Generate target / invalidation
        target = self.target_status(
            price,
            features,
            action
        )

        return {
            "decision": action,
            "entry": entry,
            "target": target
        }


    def monitor_position(self, current_price, trade):

        target = trade.get(
            "target"
        )

        if not target:
            return {
                "status": "NO_POSITION",
                "current_price": current_price
            }

        return self.exit_status(
            current_price,
            target
        )

    # Initial research parameters, not calibrated probabilities or proven trading rules.
    HYBRID_CONFIG = {
        "min_rr": 1.5, "target_distance": 8.0, "zone_atr": 0.25,
        "max_chase_atr": 0.5, "max_spread_atr": 0.15,
        "impulse_atr": 1.5, "setup_lifetime": 3600,
    }

    @staticmethod
    def select_setup(features, histories, quote=None, memory=None, evidence=None):
        """H4/H1 describe context; closed M15 structure selects the candidate.

        This permits a short-term countertrend candidate, never an immediate
        trade. Pullback, a subsequent closed M5 confirmation, live trigger,
        invalidation, spread and actual-price RR still govern entry.
        """
        f = features["M15"]
        checks = f["direction_checks"]
        up = (f["breakout_up"] or
              (f["structure"] == "HIGHER" and checks["close_above_ema20"]
               and checks["ema20_rising"]))
        down = (f["breakout_down"] or
                (f["structure"] == "LOWER" and not checks["close_above_ema20"]
                 and not checks["ema20_rising"]))
        # Local swing progression can change before the two five-bar windows.
        # Equal bases/tops alone do not force a trade or a reversal.
        action = f.get('price_action') or {}
        previous, latest = histories['M15'][-2:]
        if (not up and not down and action.get('swing_high') == 'HH' and action.get('swing_low') == 'HL'
                and latest['close'] > previous['close']):
            up, down = True, False
        elif (not up and not down and action.get('swing_high') == 'LH' and action.get('swing_low') == 'LL'
              and latest['close'] < previous['close']):
            up, down = False, True
        base_side = "BUY" if up and not down else "SELL" if down and not up else None
        evidence = evidence if evidence is not None else {}
        evidence.update(m15_candidate=base_side, m5_candidate=None,
                        selection_reason="M15_EXISTING_SETUP", level_role="ADVISORY_ONLY",
                        level_proximity_penalty=False, additional_wait=False)
        reversal_side, reversal_center = None, None
        if quote:
            short = features["M5"]
            bars = histories["M5"]
            bar = bars[-1]
            size = bar["high"] - bar["low"]
            location = (bar["close"] - bar["low"]) / size if size else 0.5
            buffer = max(0.1 * short['atr14'], 1e-9)
            action = short.get('price_action') or {}
            medium = features['M15'].get('price_action') or {}
            support = action.get('support', []) + medium.get('support', [])
            resistance = action.get('resistance', []) + medium.get('resistance', [])
            # Include existing recent extrema even when a pivot is not yet confirmed.
            lows = [short['recent_low']] + [x['price'] for x in support]
            highs = [short['recent_high']] + [x['price'] for x in resistance]
            bid = quote['bid']
            reaction_side, reaction_level, reason = None, None, None
            # A level matters only after an observed rejection/reclaim. Being near
            # (or far from) it never subtracts points or prevents a normal entry.
            rejected_lows = [x for x in lows if bar['low'] < x-buffer
                             and bar['close'] > x+buffer and location >= 0.65
                             and bid >= x+buffer]
            rejected_highs = [x for x in highs if bar['high'] > x+buffer
                              and bar['close'] < x-buffer and location <= 0.35
                              and bid <= x-buffer]
            if rejected_lows and not rejected_highs:
                reaction_side, reaction_level, reason = 'BUY', max(rejected_lows), 'SUPPORT_RECLAIM'
            elif rejected_highs and not rejected_lows:
                reaction_side, reaction_level, reason = 'SELL', min(rejected_highs), 'RESISTANCE_REJECTION'
            # A large candle can fail immediately: no requirement for shrinking
            # candles, another M15 close, or HTF agreement.
            if short['breakout_up'] and bid < short['recent_high']-buffer:
                reaction_side, reaction_level, reason = 'SELL', short['recent_high'], 'LIVE_FAILED_UP_BREAK'
            elif short['breakout_down'] and bid > short['recent_low']+buffer:
                reaction_side, reaction_level, reason = 'BUY', short['recent_low'], 'LIVE_FAILED_DOWN_BREAK'

            memory = memory if memory is not None else {}
            clock = bar['time']
            if memory.get('source_m5') != clock:
                memory.clear()
            if reaction_side:
                reversal_side, reversal_center = reaction_side, reaction_level
                memory.update(source_m5=clock, side=reversal_side, level=reversal_center,
                              reason=reason, reaction=True)
            else:
                # Preserve a live-confirmed break while its BROKEN LEVEL holds.
                # The old code switched sides whenever bid crossed one candle low.
                saved = memory.get('side')
                holds = (bid >= memory.get('level', bid)-buffer if saved == 'BUY'
                         else bid <= memory.get('level', bid)+buffer)
                if saved and holds:
                    reversal_side, reversal_center = saved, memory['level']
                    reason = memory['reason']
                else:
                    memory.clear()
                    if (short['breakout_down'] and bar['close'] < bar['open']
                            and location <= 0.35 and bid <= bar['low']):
                        reversal_side, reversal_center = 'SELL', short['recent_low']
                    elif (short['breakout_up'] and bar['close'] > bar['open']
                            and location >= 0.65 and bid >= bar['high']):
                        reversal_side, reversal_center = 'BUY', short['recent_high']
                    reason = 'M5_BROKEN_LEVEL_HELD'
                    if reversal_side:
                        memory.update(source_m5=clock, side=reversal_side, level=reversal_center,
                                      reason=reason, reaction=False)
            if reversal_side:
                up, down = reversal_side == 'BUY', reversal_side == 'SELL'
                evidence.update(m5_candidate=reversal_side, selection_reason=reason,
                                reaction_level=reversal_center,
                                reaction_candidate=bool(memory.get('reaction')))
        side = "BUY" if up and not down else "SELL" if down and not up else None
        if side is None:
            return None, "NO_M15_STRUCTURAL_SETUP", None, "NONE"
        sign = 1 if side == "BUY" else -1
        expected = "UP" if sign == 1 else "DOWN"
        contexts = [features[tf]["direction"] for tf in ("H4", "H1")]
        opposing = "DOWN" if sign == 1 else "UP"
        mode = ("COUNTERTREND" if opposing in contexts else
                "TREND_CONTINUATION" if expected in contexts else "TRANSITION")
        if reversal_side:
            basis = "PRICE_REACTION" if evidence.get("reaction_candidate") else "BROKEN_M5_LEVEL_LIVE_CONFIRMED"
            return side, mode, reversal_center, basis
        breakout = f["breakout_up"] if sign == 1 else f["breakout_down"]
        center = (f["recent_high"] if sign == 1 else f["recent_low"]) if breakout else f["ema20"]
        return side, mode, center, "BROKEN_M15_LEVEL" if breakout else "M15_EMA_PULLBACK"

    def process_hybrid(self, state, payload):
        """One paper lifecycle per symbol. No broker orders are sent by this method.

        Caller validates the envelope and commits state + events in one transaction.
        Entry is an observed bid/ask paper fill, NOT an assertion about MT5 orders.
        """
        from copy import deepcopy
        state = deepcopy(state)
        events = []
        quote = payload["quote"]
        now, bid, ask = quote["time"], quote["bid"], quote["ask"]
        histories = payload["candles"]
        config = self.HYBRID_CONFIG
        features = {tf: self.feature_engine.calculate_history(bars)
                    for tf, bars in histories.items()}
        direction = features["H4"]["direction"]
        selection = {}
        setup_side, setup_mode, zone_center, zone_basis = self.select_setup(
            features, histories, quote, state.setdefault("direction_memory", {}), selection)
        diagnostics = {"policy": "CONTEXTUAL_REACTION_V4", "selection": selection, "h4_context": direction,
                       "h1_context": features["H1"]["direction"],
                       "candidate_side": setup_side, "candidate_mode": setup_mode,
                       "zone_basis": zone_basis, "higher_timeframe_veto": False}
        # An ordinary M15 pullback may turn the strict label neutral. It does
        # not by itself invalidate an already armed structural hypothesis.
        if (setup_side is None and state.get("setup")
                and state["setup"].get("zone_basis") != "PRICE_REACTION"):
            setup_side = state["setup"]["side"]
            setup_mode = state["setup"].get("mode", "TRANSITION")
            zone_center = (state["setup"]["zone_low"] + state["setup"]["zone_high"]) / 2
            zone_basis = state["setup"].get("zone_basis", "EXISTING_STRUCTURE")
            diagnostics["retained_pending_setup"] = True
        m15, m5 = histories["M15"], histories["M5"]
        atr = features["M15"]["atr14"]
        cycle = m15[-1]["time"]
        previous_time = state.get("last_quote_time", 0)
        if now <= previous_time:
            # Retries and older ticks never create a second entry or outcome.
            return state, deepcopy(state["last_result"]), []

        def record(kind, **details):
            events.append({"time": now, "kind": kind, **details})

        def result(stage, reason, decision="WAIT", trade=None, setup=None):
            target = None
            if trade:
                target = {"action": trade["side"], "target_price": trade["tp"],
                          "invalid_price": trade["sl"]}
            value = {
                "decision": decision, "state": stage, "reason": reason,
                "direction": direction, "setup_direction": setup_side,
                "execution_mode": "PAPER_ONLY", "broker_position_status": "NOT_CONNECTED",
                "entry": {"action": decision, "setup": (setup or {}).get("side", "NO_SETUP"),
                          "quality": "NOT_CALIBRATED"},
                "target": target, "paper_trade": deepcopy(trade),
                "setup": deepcopy(setup), "timeframes": features,
                "setup_mode": (setup or trade or {}).get("mode", setup_mode),
                "diagnostics": deepcopy(diagnostics),
            }
            # Forward evidence from observed quotes, including rejected entries.
            # Stored locally by StateStore, not uploaded as a growing cloud table.
            record("EVALUATION", bid=bid, ask=ask, stage=stage, reason=reason,
                   candidate_side=setup_side, candidate_mode=setup_mode,
                   setup_id=(setup or trade or {}).get("id"),
                   diagnostics=deepcopy(diagnostics))
            context_clock = {tf: bars[-1]["time"] for tf, bars in histories.items()}
            if state.get("audit_context_clock") != context_clock:
                record("CLOSED_CONTEXT", timeframes=deepcopy(features),
                       recent_candles={tf: deepcopy(bars[-10:]) for tf, bars in histories.items()})
                state["audit_context_clock"] = context_clock
            state["last_quote_time"] = now
            state["last_mid"] = (bid + ask) / 2
            state["last_result"] = deepcopy(value)
            return state, value, events

        trade = state.get("trade")
        if trade:
            sign = 1 if trade["side"] == "BUY" else -1
            exit_quote = bid if sign == 1 else ask
            trade["mfe_observed"] = max(trade["mfe_observed"], sign * (exit_quote - trade["entry_price"]))
            trade["mae_observed"] = max(trade.get("mae_observed", 0.0),
                                        -sign * (exit_quote - trade["entry_price"]))
            if now - previous_time > 30:
                trade["coverage_gap"] = True
            # Only complete M5 bars which started AFTER entry can establish a touch.
            # Never use pre-entry highs/lows from the entry candle.
            closed = [b for b in m5 if b["time"] >= trade["entry_time"]
                      and b["time"] > trade.get("last_checked_bar", 0)]
            outcome, evidence = None, None
            for bar in closed:
                # MT5 candle OHLC is bid-based. For SELL ask-based exits a past
                # spread is unknown: do not infer ask TP/SL touches from bid bars.
                if sign == -1:
                    trade["coverage_gap"] = True
                    trade["last_checked_bar"] = bar["time"]
                    continue
                trade["mfe_observed"] = max(trade["mfe_observed"], bar["high"] - trade["entry_price"])
                tp_hit, sl_hit = bar["high"] >= trade["tp"], bar["low"] <= trade["sl"]
                trade["last_checked_bar"] = bar["time"]
                if tp_hit and sl_hit:
                    trade["unresolved"] = True
                    record("AMBIGUOUS_OUTCOME", trade_id=trade["id"], bar_time=bar["time"])
                    break
                if tp_hit or sl_hit:
                    outcome = "TP_TOUCHED" if tp_hit else "SL_TOUCHED"
                    evidence = "CLOSED_M5_RANGE_ORDER_WITHIN_BAR_UNKNOWN"
                    break
            if trade.get("unresolved"):
                return result("MANAGE", "AMBIGUOUS_TP_SL_REQUIRES_REVIEW", trade=trade)
            if not outcome:
                if (sign == 1 and exit_quote <= trade["sl"]) or (sign == -1 and exit_quote >= trade["sl"]):
                    outcome = "SL_TOUCHED"
                elif (sign == 1 and exit_quote >= trade["tp"]) or (sign == -1 and exit_quote <= trade["tp"]):
                    outcome = "TP_TOUCHED"
                evidence = "OBSERVED_QUOTE"
            if outcome:
                trade.update(outcome=outcome, exit_time=now, exit_observed_price=exit_quote,
                             outcome_evidence=evidence)
                record("EXIT", trade=deepcopy(trade))
                state["last_trade"] = deepcopy(trade)
                state["trade"] = None
                state["blocked_cycle"] = cycle
                # Exit and reverse are always separate evaluations, never same tick/bar.
                return result("EXIT", outcome, decision="EXIT", trade=trade)
            opposing = setup_side is not None and setup_side != trade["side"]
            record_needed = opposing and not trade.get("opposing_bias", False)
            trade["opposing_bias"] = opposing
            if record_needed:
                record("OPPOSING_BIAS_WHILE_MANAGING", trade_id=trade["id"],
                       direction=setup_side, selection=deepcopy(selection))
            return result("MANAGE", "OPPOSING_BIAS_NO_REVERSE" if opposing else "PAPER_POSITION_OPEN",
                          trade=trade)

        if state.get("blocked_cycle") == cycle:
            return result("WAIT", "COOLDOWN_AFTER_EXIT_OR_CANCEL")
        if now <= state.get("cancel_quote_time", 0):
            return result("WAIT", "WAIT_NEW_QUOTE_AFTER_CANCEL")
        if atr <= 0:
            return result("WAIT", "NO_VOLATILITY")
        setup = state.get("setup")
        midpoint = (bid + ask) / 2
        # Detect adverse movement both across observed quotes and across closed M5 bars.
        impulse = False
        if setup:
            sign = 1 if setup["side"] == "BUY" else -1
            adverse_tick = -sign * (midpoint - state.get("last_mid", midpoint))
            reference = setup.get("favorable_reference", state.get("last_mid", midpoint))
            reference = max(reference, midpoint) if sign == 1 else min(reference, midpoint)
            setup["favorable_reference"] = reference
            adverse_path = -sign * (midpoint - reference)
            new_bars = [b for b in m5 if b["time"] >= setup["created"]]
            adverse_bar = any(-sign * (b["close"] - b["open"]) >= config["impulse_atr"] * atr
                              for b in new_bars)
            impulse = max(adverse_tick, adverse_path) >= config["impulse_atr"] * atr or adverse_bar
            invalid = bid <= setup["sl"] if sign == 1 else ask >= setup["sl"]
            reason = ("STRUCTURAL_INVALIDATION" if invalid else "IMPULSE_OVERRIDE" if impulse
                      else "SHORT_TERM_STRUCTURE_CHANGED" if setup_side != setup["side"]
                      else "SETUP_EXPIRED" if now >= setup["expires"] else None)
            if reason:
                record("CANCEL", reason=reason, setup=deepcopy(setup))
                if not setup.get("zone_seen"):
                    record("MISSED_ENTRY_REVIEW", reason="ZONE_NOT_OBSERVED_BEFORE_CANCEL", setup_id=setup["id"])
                state["setup"] = None
                state["cancel_quote_time"] = now
                return result("CANCEL", reason)
        if setup_side is None:
            return result("WAIT", "NO_M15_STRUCTURAL_SETUP")
        diagnostics["spread"] = ask - bid
        diagnostics["spread_limit"] = config["max_spread_atr"] * atr
        if (ask - bid) > config["max_spread_atr"] * atr:
            return result("ARMED" if setup else "WAIT", "SPREAD_TOO_WIDE", setup=setup)
        if setup is None:
            center = zone_center
            low_zone, high_zone = center - config["zone_atr"] * atr, center + config["zone_atr"] * atr
            sl = (min(low_zone, min(b["low"] for b in m15[-5:])) - 0.1 * atr if setup_side == "BUY"
                  else max(high_zone, max(b["high"] for b in m15[-5:])) + 0.1 * atr)
            setup = {"id": f"{payload['symbol']}:{now}", "side": setup_side,
                     "created": now, "expires": now + config["setup_lifetime"],
                     "source_bar": histories["H1"][-1]["time"], "source_m15": cycle,
                     "zone_low": low_zone, "zone_high": high_zone, "sl": sl,
                     "zone_seen": False, "late_chase_recorded": False,
                     "confirmation_after": m5[-1]["time"],
                     "mode": setup_mode, "zone_basis": zone_basis,
                     "favorable_reference": midpoint}
            state["setup"] = setup
            record("ARMED", setup=deepcopy(setup))
            return result("ARMED", "WAIT_FOR_PULLBACK_AND_NEW_CONFIRMATION", setup=setup)
        # A new candle is information, not a reason to discard a valid pullback.
        # Before a touch, adapt the waiting zone to a new closed M15 structure;
        # after a touch preserve its evidence and invalidation until cancelled.
        if setup.get("source_m15", cycle) != cycle:
            if not setup["zone_seen"]:
                new_low = zone_center - config["zone_atr"] * atr
                new_high = zone_center + config["zone_atr"] * atr
                # Do not move the waiting zone through its frozen thesis stop.
                # A fresh setup after cancellation must establish new risk.
                valid_zone = new_low > setup["sl"] if setup_side == "BUY" else new_high < setup["sl"]
                if valid_zone:
                    setup["zone_low"], setup["zone_high"] = new_low, new_high
                    setup["zone_basis"] = zone_basis
                    record("SETUP_REASSESSED", setup=deepcopy(setup))
            setup["source_m15"] = cycle
            setup["source_bar"] = histories["H1"][-1]["time"]
        setup["mode"] = setup_mode
        executable = ask if setup_side == "BUY" else bid
        in_zone = setup["zone_low"] <= executable <= setup["zone_high"]
        diagnostics.update(zone_low=setup["zone_low"], zone_high=setup["zone_high"],
                           executable=executable, in_zone=in_zone)
        if in_zone and not setup["zone_seen"]:
            setup["zone_seen"] = True
            setup["zone_seen_time"] = now
            setup["confirmation_after"] = m5[-1]["time"]
            setup["pullback_extreme"] = bid if setup_side == "BUY" else ask
            record("PULLBACK_OBSERVED", setup_id=setup["id"], price=executable)
            return result("ARMED", "PULLBACK_OBSERVED_WAIT_CONFIRMATION", setup=setup)
        if setup.get("zone_seen") and "pullback_extreme" in setup:
            setup["pullback_extreme"] = (min(setup["pullback_extreme"], bid) if setup_side == "BUY"
                                         else max(setup["pullback_extreme"], ask))
        chase_distance = (executable - setup["zone_high"] if setup_side == "BUY"
                          else setup["zone_low"] - executable)
        diagnostics.update(chase_distance=chase_distance,
                           chase_limit=config["max_chase_atr"] * atr,
                           pullback_observed=setup["zone_seen"])
        if chase_distance > config["max_chase_atr"] * atr:
            if not setup["late_chase_recorded"]:
                record("LATE_CHASE_REJECTED", setup_id=setup["id"], distance=chase_distance)
                setup["late_chase_recorded"] = True
            return result("ARMED", "NO_PRICE_CHASING", setup=setup)
        if not setup["zone_seen"]:
            return result("ARMED", "WAIT_FOR_PULLBACK", setup=setup)
        confirmation = m5[-1]
        if (confirmation["time"] <= setup["confirmation_after"]
                or confirmation["time"] + 300 <= setup["zone_seen_time"]):
            return result("ARMED", "WAIT_FOR_NEW_M5_CONFIRMATION", setup=setup)
        sign = 1 if setup_side == "BUY" else -1
        body = sign * (confirmation["close"] - confirmation["open"])
        size = confirmation["high"] - confirmation["low"]
        position = ((confirmation["close"] - confirmation["low"]) / size if size else 0.5)
        confirms = body > 0 and (position >= 0.65 if sign == 1 else position <= 0.35)
        trigger = confirmation["high"] if sign == 1 else confirmation["low"]
        # Bid drives BUY breakout too, preventing a wide ask spread from faking it.
        trigger_quote = bid
        triggered = trigger_quote >= trigger if sign == 1 else trigger_quote <= trigger
        diagnostics.update(m5_confirms=confirms, live_trigger=trigger,
                           live_trigger_passed=triggered)
        if not confirms or not triggered:
            return result("ARMED", "WAIT_FOR_LIVE_TRIGGER", setup=setup)
        # Reject a live short-term impulse against the thesis even before M15 close.
        if -sign * (midpoint - confirmation["close"]) >= config["impulse_atr"] * atr:
            state["setup"] = None
            state["cancel_quote_time"] = now
            record("CANCEL", reason="LIVE_IMPULSE_OVERRIDE", setup=deepcopy(setup))
            return result("CANCEL", "LIVE_IMPULSE_OVERRIDE")
        entry_sl = setup["sl"]
        if "pullback_extreme" in setup:
            # Entry risk uses the observed pullback and its confirming M5,
            # not a distant five-M15 extreme. Never change an open trade's SL.
            extreme = (min(setup["pullback_extreme"], confirmation["low"]) if sign == 1
                       else max(setup["pullback_extreme"], confirmation["high"] + ask - bid))
            local_sl = extreme - sign * 0.1 * atr
            entry_sl = max(entry_sl, local_sl) if sign == 1 else min(entry_sl, local_sl)
        risk = sign * (executable - entry_sl)
        reward = config["target_distance"]
        # Cap reward at known H1 resistance/support if closer than the research target.
        barrier = (max(b["high"] for b in histories["H1"][-20:]) if sign == 1
                   else min(b["low"] for b in histories["H1"][-20:]))
        if sign * (barrier - executable) > 0:
            reward = min(reward, sign * (barrier - executable))
        diagnostics.update(risk=risk, reward=reward, rr=reward / risk if risk > 0 else None,
                           minimum_rr=config["min_rr"], stop_price=entry_sl,
                           thesis_invalidation=setup["sl"])
        if risk <= 0 or reward / risk < config["min_rr"]:
            return result("ARMED", "INSUFFICIENT_RISK_REWARD", setup=setup)
        m15_trend = features['M15']['direction']
        opposing_m15 = 'DOWN' if setup_side == 'BUY' else 'UP'
        diagnostics.update(m15_entry_check=dict(direction=m15_trend, candidate_side=setup_side,
                           against_entry=m15_trend == opposing_m15, neutral_allowed=True))
        if m15_trend == opposing_m15:
            record('CANCEL', reason='M15_TREND_AGAINST_ENTRY', setup=deepcopy(setup),
                   m15_direction=m15_trend, candidate_side=setup_side,
                   candidate_entry=executable, candidate_sl=entry_sl,
                   candidate_tp=executable+sign*reward)
            state['setup'] = None
            state['cancel_quote_time'] = now
            return result('CANCEL', 'M15_TREND_AGAINST_ENTRY')
        trade = {"id": setup["id"], "side": setup_side, "entry_time": now,
                 "entry_price": executable, "tp": executable + sign * reward,
                 "sl": entry_sl, "rr": reward / risk, "mfe_observed": 0.0, "mae_observed": ask-bid,
                 "policy": "CONTEXTUAL_REACTION_V4", "selection": deepcopy(selection),
                 "coverage_gap": False, "basis": "OBSERVED_QUOTE_PAPER_FILL"}
        trade["mode"] = setup_mode
        state["trade"], state["setup"] = trade, None
        record("ENTRY", trade=deepcopy(trade))
        return result("ENTRY", "HYBRID_CONFIRMED_PAPER_ENTRY", decision=setup_side, trade=trade)
