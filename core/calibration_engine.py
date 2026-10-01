class CalibrationEngine:

    def evaluate(self, history):

        if not history:
            return {
                "samples": 0,
                "calibration": 0
            }

        total = len(history)
        correct = 0

        for item in history:
            if item.get("decision") == item.get("outcome"):
                correct += 1

        return {
            "samples": total,
            "calibration": correct / total
        }
