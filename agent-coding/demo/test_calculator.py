import pytest

from calculator import add, divide, multiply, power, subtract


class TestAdd:
    """Verifies the addition logic in the calculator."""

    def test_positive_numbers(self):
        """Checks adding two positive integers."""
        assert add(2, 3) == 5

    def test_with_zero(self):
        """Checks adding zero to an integer."""
        assert add(0, 5) == 5

    def test_negative(self):
        """Checks adding a negative integer to its positive counterpart."""
        assert add(-3, 3) == 0


class TestSubtract:
    """Verifies the subtraction logic in the calculator."""

    def test_basic(self):
        """Checks subtraction of two positive integers."""
        assert subtract(10, 4) == 6

    def test_negative_result(self):
        """Checks subtraction resulting in a negative value."""
        assert subtract(3, 7) == -4

    def test_same_numbers(self):
        """Checks subtraction of an integer from itself."""
        assert subtract(5, 5) == 0


class TestMultiply:
    """Verifies the multiplication logic in the calculator."""

    def test_basic(self):
        """Checks product of two positive integers."""
        assert multiply(3, 4) == 12

    def test_by_zero(self):
        """Checks multiplication by zero."""
        assert multiply(99, 0) == 0


class TestDivide:
    """Verifies the division logic in the calculator."""

    def test_even_division(self):
        """Checks exact division of two integers."""
        assert divide(10, 2) == 5

    def test_decimal_result(self):
        """Checks division resulting in a float."""
        assert divide(7, 2) == 3.5

    def test_zero_divisor_raises(self):
        """Ensures ValueError is raised when dividing by zero."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(5, 0)


class TestPower:
    """Verifies the exponentiation logic in the calculator."""

    def test_square(self):
        """Checks raising an integer to the power of two."""
        assert power(3, 2) == 9

    def test_zero_exponent(self):
        """Checks raising an integer to the power of zero."""
        assert power(5, 0) == 1
