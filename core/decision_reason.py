class DecisionReason:

    def __init__(self):
        pass


    def generate(self, decision, confidence, risk):

        reasons = []

        reasons.extend(
            decision.get(
                "reasons",
                []
            )
        )


        reasons.append(
            f"Confidence level: {confidence.get('level')}"
        )


        reasons.append(
            f"Risk level: {risk.get('risk_level')}"
        )


        return {
            "summary": reasons,
            "count": len(reasons)
        }
