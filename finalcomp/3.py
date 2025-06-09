class Calculator:
    def add(self, x, y):
        return x + y

def compute_and_print():
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"Result: {result}")

compute_and_print()
