import json
from pathlib import Path


class AdaptiveWeight:

    def __init__(self):
        self.file = Path("data/adaptive_weights.json")

        self.weights = self.load()


    def load(self):

        if self.file.exists():
            with open(self.file, "r") as f:
                return json.load(f)

        return {
            "buying_pressure": 1.0,
            "trend_strength": 1.0
        }


    def save(self):

        self.file.parent.mkdir(
            exist_ok=True
        )

        with open(self.file, "w") as f:
            json.dump(
                self.weights,
                f,
                indent=2
            )


    def get_weights(self):

        return self.weights


    def adjust(self, result):

        factor = 1.05 if result == "GOOD" else 0.95

        for key in self.weights:
            self.weights[key] *= factor

        self.save()

        return self.weights
