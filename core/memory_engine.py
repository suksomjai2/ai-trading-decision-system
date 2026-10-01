class MemoryEngine:

    def __init__(self):
        self.history = []


    def store(self, result):

        self.history.append(
            result
        )


    def get_history(self):

        return self.history


    def last_result(self):

        if self.history:
            return self.history[-1]

        return None
