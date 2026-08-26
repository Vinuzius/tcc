class Profile:
    def __init__(self, name: str, transform):
        self.name = name
        self.transform = transform

    def apply(self, results: list[dict]) -> list[dict]:
        return [
            {
                key: self.transform(value) if isinstance(value, str) else value
                for key, value in row.items()
            }
            for row in results
        ]