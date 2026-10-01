from core.decision_reason import DecisionReason
from core.adaptive_weight import AdaptiveWeight


class DecisionEngine:

    def __init__(self):
        self.reason_engine = DecisionReason()
        self.weight_engine = AdaptiveWeight()

    def evaluate(self, features):

        score = 0

        weights = self.weight_engine.get_weights()

        if features.get("buying_pressure", 0) > 0.7:
            score += weights.get("buying_pressure", 1)
        
        if features.get("trend_strength", 0) > 0.5:
            score += weights.get("trend_strength", 1)

        reasons = self.reason_engine.generate(features, {}, {})

        if score >= 2:
            action = "BUY"
        elif score <= -2:
            action = "SELL"
        else:
            action = "HOLD"

        return {
            "action": action,
            "score": round(score, 2),
            "reasons": reasons
        }
