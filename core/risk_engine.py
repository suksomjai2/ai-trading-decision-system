class RiskEngine:

    def __init__(self):
        pass


    def evaluate(self, decision, features):

        confidence = decision.get(
            "confidence",
            0
        )

        action = decision.get(
            "action",
            "HOLD"
        )


        if confidence >= 0.8:
            risk = "LOW"

        elif confidence >= 0.5:
            risk = "MEDIUM"

        else:
            risk = "HIGH"


        return {
            "action": action,
            "risk_level": risk,
            "confidence": confidence
        }
