import unittest
import math
from math_mutator import optimize_math_ast

class TestMathMutator(unittest.TestCase):
    def test_power_to_multiplication(self):
        code = "def f(x):\n    return x ** 2"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("x * x", optimized)
        self.assertNotIn("x ** 2", optimized)

    def test_power_to_sqrt(self):
        code = "def f(x):\n    return x ** 0.5"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("import math", optimized)
        self.assertIn("math.sqrt(x)", optimized)

    def test_identity_multiplication(self):
        code = "def f(x):\n    return x * 1"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("return x", optimized)

    def test_identity_addition(self):
        code = "def f(x):\n    return x + 0"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("return x", optimized)

    def test_power_of_two_shift(self):
        code = "def f(x):\n    return x * 4"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("x << 2", optimized)

    def test_power_of_two_div_shift(self):
        code = "def f(x):\n    return x // 8"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("x >> 3", optimized)

    def test_constant_folding(self):
        code = "def f():\n    return 2 + 3 * 4"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("return 14", optimized)

    def test_range_sum_closed_form(self):
        code = "def f(n):\n    return sum(range(n))"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("n * (n - 1) // 2", optimized)

    def test_range_sum_start_end(self):
        code = "def f(a, b):\n    return sum(range(a, b))"
        optimized = optimize_math_ast(code)
        self.assertIsNotNone(optimized)
        self.assertIn("(b - a) * (a + b - 1) // 2", optimized)

if __name__ == "__main__":
    unittest.main()
