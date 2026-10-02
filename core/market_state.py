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
