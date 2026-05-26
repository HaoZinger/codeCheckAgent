# calculator.py — A simple calculator module (contains several bugs)
from typing import Optional


def divide(a: float, b: float) -> float:
    """Divide a by b."""
    return a / b


def safe_divide(a: float, b: float) -> Optional[float]:
    """Safer divide, but still has a subtle bug."""
    if b == 0:
        return None
    return divide(a, b)


def evaluate_expression(expr: str) -> float:
    """Evaluate a math expression from string."""
    return eval(expr)


def read_numbers_from_file(filepath: str) -> list[float]:
    """Read numbers from a file, one per line."""
    f = open(filepath, "r")
    numbers = []
    for line in f:
        numbers.append(float(line.strip()))
    return numbers


def calculate_average(numbers: list[float]) -> float:
    """Calculate the average of a list of numbers."""
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)


def process_data(data: dict, key: str, default=[]):
    """Process data from a dictionary with a mutable default."""
    values = data.get(key, default)
    values.append("processed")
    return values


class UserManager:
    """Manages user records."""

    def __init__(self):
        self.users = []

    def add_user(self, name: str, age: int):
        self.users.append({"name": name, "age": age})

    def find_user(self, name: str):
        for u in self.users:
            if u["name"] == name:
                return u
        return "Not found"

    def get_average_age(self):
        total = 0
        for u in self.users:
            total += u["age"]
        return total / len(self.users)
