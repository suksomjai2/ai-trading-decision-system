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
        side = {"UP": "BUY", "DOWN": "SELL"}.get(direction)
        setup_side = side if features["H1"]["direction"] == direction else None
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
            }
            state["last_quote_time"] = now
            state["last_mid"] = (bid + ask) / 2
            state["last_result"] = deepcopy(value)
            return state, value, events

        trade = state.get("trade")
        if trade:
            sign = 1 if trade["side"] == "BUY" else -1
            exit_quote = bid if sign == 1 else ask
            trade["mfe_observed"] = max(trade["mfe_observed"], sign * (exit_quote - trade["entry_price"]))
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
            opposing = side is not None and side != trade["side"]
            record_needed = opposing and not trade.get("opposing_bias", False)
            trade["opposing_bias"] = opposing
            if record_needed:
                record("OPPOSING_BIAS_WHILE_MANAGING", trade_id=trade["id"], direction=direction)
            return result("MANAGE", "OPPOSING_BIAS_NO_REVERSE" if opposing else "PAPER_POSITION_OPEN",
                          trade=trade)

        if state.get("blocked_cycle") == cycle:
            return result("WAIT", "COOLDOWN_AFTER_EXIT_OR_CANCEL")
        if atr <= 0:
            return result("WAIT", "NO_VOLATILITY")
        setup = state.get("setup")
        midpoint = (bid + ask) / 2
        # Detect adverse movement both across observed quotes and across closed M5 bars.
        impulse = False
        if setup:
            sign = 1 if setup["side"] == "BUY" else -1
            adverse_tick = -sign * (midpoint - state.get("last_mid", midpoint))
            new_bars = [b for b in m5 if b["time"] + 300 > setup["created"]]
            adverse_bar = any(-sign * (b["close"] - b["open"]) >= config["impulse_atr"] * atr
                              for b in new_bars)
            impulse = adverse_tick >= config["impulse_atr"] * atr or adverse_bar
            invalid = bid <= setup["sl"] if sign == 1 else ask >= setup["sl"]
            reason = ("STRUCTURAL_INVALIDATION" if invalid else "IMPULSE_OVERRIDE" if impulse
                      else "BIAS_OR_SETUP_CHANGED" if setup_side != setup["side"]
                      else "SETUP_EXPIRED" if now >= setup["expires"] else None)
            if reason:
                record("CANCEL", reason=reason, setup=deepcopy(setup))
                if not setup.get("zone_seen"):
                    record("MISSED_ENTRY_REVIEW", reason="ZONE_NOT_OBSERVED_BEFORE_CANCEL", setup_id=setup["id"])
                state["setup"] = None
                state["blocked_cycle"] = cycle
                return result("CANCEL", reason)
        if setup_side is None:
            return result("WAIT", "NO_ALIGNED_H4_H1_SETUP")
        if (ask - bid) > config["max_spread_atr"] * atr:
            return result("ARMED" if setup else "WAIT", "SPREAD_TOO_WIDE", setup=setup)
        if (setup is None or setup["source_bar"] != histories["H1"][-1]["time"]
                or setup.get("source_m15", cycle) != cycle):
            if setup:
                record("CANCEL", reason="CLOSED_STRUCTURE_REFRESH", setup=deepcopy(setup))
            center = features["M15"]["ema20"]
            low_zone, high_zone = center - config["zone_atr"] * atr, center + config["zone_atr"] * atr
            sl = (min(b["low"] for b in m15[-5:]) - 0.1 * atr if setup_side == "BUY"
                  else max(b["high"] for b in m15[-5:]) + 0.1 * atr)
            setup = {"id": f"{payload['symbol']}:{now}", "side": setup_side,
                     "created": now, "expires": now + config["setup_lifetime"],
                     "source_bar": histories["H1"][-1]["time"], "source_m15": cycle,
                     "zone_low": low_zone, "zone_high": high_zone, "sl": sl,
                     "zone_seen": False, "late_chase_recorded": False,
                     "confirmation_after": m5[-1]["time"]}
            state["setup"] = setup
            record("ARMED", setup=deepcopy(setup))
            return result("ARMED", "WAIT_FOR_PULLBACK_AND_NEW_CONFIRMATION", setup=setup)
        executable = ask if setup_side == "BUY" else bid
        in_zone = setup["zone_low"] <= executable <= setup["zone_high"]
        if in_zone and not setup["zone_seen"]:
            setup["zone_seen"] = True
            setup["zone_seen_time"] = now
            setup["confirmation_after"] = m5[-1]["time"]
            record("PULLBACK_OBSERVED", setup_id=setup["id"], price=executable)
            return result("ARMED", "PULLBACK_OBSERVED_WAIT_CONFIRMATION", setup=setup)
        chase_distance = (executable - setup["zone_high"] if setup_side == "BUY"
                          else setup["zone_low"] - executable)
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
        if not confirms or not triggered:
            return result("ARMED", "WAIT_FOR_LIVE_TRIGGER", setup=setup)
        # Reject a live short-term impulse against the thesis even before M15 close.
        if -sign * (midpoint - confirmation["close"]) >= config["impulse_atr"] * atr:
            state["setup"] = None
            state["blocked_cycle"] = cycle
            record("CANCEL", reason="LIVE_IMPULSE_OVERRIDE", setup=deepcopy(setup))
            return result("CANCEL", "LIVE_IMPULSE_OVERRIDE")
        risk = sign * (executable - setup["sl"])
        reward = config["target_distance"]
        # Cap reward at known H1 resistance/support if closer than the research target.
        barrier = (max(b["high"] for b in histories["H1"][-20:]) if sign == 1
                   else min(b["low"] for b in histories["H1"][-20:]))
        if sign * (barrier - executable) > 0:
            reward = min(reward, sign * (barrier - executable))
        if risk <= 0 or reward / risk < config["min_rr"]:
            return result("ARMED", "INSUFFICIENT_RISK_REWARD", setup=setup)
        trade = {"id": setup["id"], "side": setup_side, "entry_time": now,
                 "entry_price": executable, "tp": executable + sign * reward,
                 "sl": setup["sl"], "rr": reward / risk, "mfe_observed": 0.0,
                 "coverage_gap": False, "basis": "OBSERVED_QUOTE_PAPER_FILL"}
        state["trade"], state["setup"] = trade, None
        record("ENTRY", trade=deepcopy(trade))
        return result("ENTRY", "HYBRID_CONFIRMED_PAPER_ENTRY", decision=setup_side, trade=trade)
