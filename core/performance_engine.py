class PerformanceEngine:

    def evaluate(self, history):
        if not history:
            return {
                "count": 0,
                "accuracy": 0
            }

        correct = 0

        for item in history:
            if item.get("decision") == item.get("outcome"):
                correct += 1

        accuracy = correct / len(history)

        return {
            "count": len(history),
            "correct": correct,
            "accuracy": accuracy
        }
