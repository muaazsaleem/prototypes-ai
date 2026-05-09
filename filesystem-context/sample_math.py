def add(a, b):
    """Adds two numbers."""
    return a + b

def sum_list(numbers):
    """Calculates the sum of a list of numeric values.
    
    Ignores non-numeric values gracefully.
    """
    total = 0.0
    for num in numbers:
        if isinstance(num, (int, float)):
            total += num
    return total

class Calculator:
    """A simple calculator class."""
    def multiply(self, a, b):
        """Multiplies two numbers."""
        return a * b

    def divide(self, a, b):
        """Divides a by b, raising ValueError on zero division."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
