# sample_test.py
# Pytest test suite for sample_source.py.
# Each class targets one function and includes at least one test that fails
# due to a bug in the source — the agent's job is to fix those bugs.

import pytest

from sample_source import add, count_vowels, find_max, is_palindrome, to_title_case


class TestAdd:
    def test_positive_numbers(self):
        assert add(2, 3) == 5

    def test_negative_operand(self):
        assert add(-4, 4) == 0

    def test_both_negative(self):
        assert add(-1, -2) == -3


class TestIsPalindrome:
    def test_lowercase_palindrome(self):
        assert is_palindrome("racecar") is True

    def test_not_palindrome(self):
        assert is_palindrome("hello") is False

    def test_mixed_case_palindrome(self):
        # "Racecar" is a palindrome when case is ignored
        assert is_palindrome("Racecar") is True

    def test_mixed_case_non_palindrome(self):
        assert is_palindrome("Hello") is False


class TestCountVowels:
    def test_lowercase(self):
        assert count_vowels("hello") == 2

    def test_uppercase(self):
        assert count_vowels("HELLO") == 2

    def test_mixed_case(self):
        assert count_vowels("HeLLo WoRLd") == 3


class TestFindMax:
    def test_normal_list(self):
        assert find_max([3, 1, 4, 1, 5]) == 5

    def test_single_element(self):
        assert find_max([7]) == 7

    def test_empty_list_returns_none(self):
        assert find_max([]) is None


class TestToTitleCase:
    def test_single_word(self):
        assert to_title_case(["hello"]) == ["Hello"]

    def test_multiple_words(self):
        assert to_title_case(["hello", "world"]) == ["Hello", "World"]

    def test_already_uppercase(self):
        assert to_title_case(["HELLO"]) == ["Hello"]
