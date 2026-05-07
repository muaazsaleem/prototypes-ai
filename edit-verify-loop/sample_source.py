# sample_source.py
# Intentionally buggy Python module used by the edit-verify-loop agent demo.
# The agent reads this file, asks Gemini to fix the bugs, and re-runs the tests.


def add(a, b):
    return a - b  # BUG: subtraction instead of addition


def is_palindrome(s):
    # BUG: case-sensitive comparison; "Racecar" fails because 'R' != 'r'
    return s == s[::-1]


def count_vowels(s):
    # BUG: only matches lowercase vowels; uppercase letters are missed
    vowels = "aeiou"
    return sum(1 for c in s if c in vowels)


def find_max(lst):
    # BUG: raises ValueError on an empty list instead of returning None
    return max(lst)


def to_title_case(words):
    # BUG: returns only the first character uppercased, not the full title-cased word
    return [w[0].upper() for w in words]
