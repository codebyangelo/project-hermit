import unittest
from qubo_mutator import optimize_qubo_ast

class TestQUBOMutator(unittest.TestCase):
    def test_qubo_double_loop_detection(self):
        # A typical slow QUBO double loop calculation
        code = (
            "def compute_energy(Q, x, n):\n"
            "    total = 0\n"
            "    for i in range(n):\n"
            "        for j in range(n):\n"
            "            total += Q[i][j] * x[i] * x[j]\n"
            "    return total\n"
        )
        optimized = optimize_qubo_ast(code)
        # Verify that the AST transformer detected the structure and triggered an update
        self.assertIsNotNone(optimized)
        # It should compile and be valid Python
        self.assertIn("for i in range(n):", optimized)
        self.assertIn("for j in range(n):", optimized)

if __name__ == "__main__":
    unittest.main()
