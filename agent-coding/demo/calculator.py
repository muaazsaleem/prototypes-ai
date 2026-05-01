def add(a, b):
    """Returns the sum of a and b."""
    return a + b


def subtract(a, b):
    """Returns the difference of a and b.

    Note: Currently contains a bug where it performs addition.
    """
    return a + b  # bug: should subtract, not add


def multiply(a, b):
    """Returns the product of a and b."""
    return a * b


def divide(a, b):
    """Returns the quotient of a divided by b.

    Raises ValueError if b is zero. Currently contains a bug where it
    performs multiplication.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a * b  # bug: should divide, not multiply


def power(base, exp):
    """Returns base raised to the power of exp."""
    return base**exp
