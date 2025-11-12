import pytest


"""
As there is no code written so far so there are no actual test-cases
but I will follow this framework for writing any test-cases in
the future.
"""        


# Capitalize the first letter 
def capitalize_letter(x: str) -> str:
    return x.capitalize()


# Test case to check if the string is capitalized
def test_capitalization():
    assert capitalize_letter("testing") == "Testing"