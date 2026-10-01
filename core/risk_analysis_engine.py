class RiskAnalysisEngine:

    def evaluate(self, history):

        if not history:
            return {
                "samples": 0,
                "risk_accuracy": {}
            }

        result = {}

        for item in history:
            risk = item.get("risk", "UNKNOWN")
            outcome = item.get("result")

            if risk not in result:
                result[risk] = {
                    "total": 0,
                    "correct": 0
                }

            result[risk]["total"] += 1

            if item.get("decision") == outcome:
                result[risk]["correct"] += 1

        for risk in result:
            total = result[risk]["total"]
            result[risk]["accuracy"] = (
                result[risk]["correct"] / total
            )

        return {
            "samples": len(history),
            "risk_accuracy": result
        }
