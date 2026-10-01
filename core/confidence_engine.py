class ConfidenceEngine:

    def __init__(self):
        pass


    def evaluate(self, decision, features):

        score = decision.get(
            "score",
            0
        )

        reasons = features.get(
            "reason_count",
            0
        )

        confidence = 0.5

        confidence += min(
            abs(score) * 0.1,
            0.3
        )

        confidence += min(
            reasons * 0.05,
            0.2
        )

        if confidence > 1:
            confidence = 1


        return {
            "value": round(confidence, 2),
            "level": (
                "HIGH"
                if confidence >= 0.7
                else "MEDIUM"
                if confidence >= 0.4
                else "LOW"
            )
        }
