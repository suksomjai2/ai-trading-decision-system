import json
from pathlib import Path

from core.adaptive_weight import AdaptiveWeight


class FeedbackEngine:

    def __init__(self):
        self.file = Path("data/feedback_history.json")

        self.history_data = self.load()

        self.weight_engine = AdaptiveWeight()


    def load(self):

        if self.file.exists():
            with open(self.file, "r") as f:
                return json.load(f)

        return []


    def save(self):

        self.file.parent.mkdir(
            exist_ok=True
        )

        with open(self.file, "w") as f:
            json.dump(
                self.history_data,
                f,
                indent=2
            )


    def record(self, decision, outcome):

        result = "GOOD"

        if decision != outcome:
            result = "BAD"


        item = {
            "decision": decision,
            "outcome": outcome,
            "result": result
        }


        self.history_data.append(item)

        self.save()

        self.weight_engine.adjust(result)


        return item


    def accuracy(self):

        if not self.history_data:
            return 0


        correct = sum(
            1
            for x in self.history_data
            if x["decision"] == x["outcome"]
        )

        return round(
            correct / len(self.history_data),
            2
        )


    def get_weights(self):

        return self.weight_engine.get_weights()


    def history(self):

        return self.history_data
