# math_mutator.py
# ARCHITECTURAL ROLE: MATHEMATICAL CODE MUTATION ENGINE (WORKS IN TANDEM WITH HERMIT EVOLUTION)
# Provides AST-based mathematical optimizations and LLM-based numerical algorithm improvements.

import ast
import copy
import math
import json
from typing import Dict, Any, List, Optional, Tuple

class MathASTOptimizer(ast.NodeTransformer):
    """
    AST-based NodeTransformer that identifies and simplifies mathematical expressions:
    - Folding constants (e.g. 2 + 3 -> 5)
    - Power simplifications (e.g. x ** 2 -> x * x, x ** 0.5 -> math.sqrt(x))
    - Multiplicative identities (e.g. x * 1 -> x, x * 0 -> 0)
    - Additive identities (e.g. x + 0 -> x)
    - Closed-form summation of ranges (e.g. sum(range(N)) -> N * (N - 1) // 2)
    - Multiplication/division by constants to shifts (e.g. x * 4 -> x << 2, x // 8 -> x >> 3)
    """
    def __init__(self):
        super().__init__()
        self.math_imported_needed = False
        self.modified = False

    def is_simple_node(self, node: ast.AST) -> bool:
        """Determines if a node is simple enough to duplicate without side-effects or token overhead."""
        return isinstance(node, (ast.Name, ast.Constant))

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        # First visit the children
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)

        # 1. Constant Folding
        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            lval = node.left.value
            rval = node.right.value
            try:
                if isinstance(node.op, ast.Add):
                    res = lval + rval
                elif isinstance(node.op, ast.Sub):
                    res = lval - rval
                elif isinstance(node.op, ast.Mult):
                    res = lval * rval
                elif isinstance(node.op, ast.Div) and rval != 0:
                    res = lval / rval
                elif isinstance(node.op, ast.FloorDiv) and rval != 0:
                    res = lval // rval
                elif isinstance(node.op, ast.Mod) and rval != 0:
                    res = lval % rval
                elif isinstance(node.op, ast.Pow) and -100 <= rval <= 100:
                    res = lval ** rval
                else:
                    return node
                self.modified = True
                return ast.Constant(value=res)
            except Exception:
                pass

        # 2. Power Simplifications (x ** 2 -> x * x)
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            rval = node.right.value
            if rval == 2 and self.is_simple_node(node.left):
                self.modified = True
                return ast.BinOp(
                    left=node.left,
                    op=ast.Mult(),
                    right=copy.deepcopy(node.left)
                )
            # x ** 0.5 -> math.sqrt(x)
            elif rval == 0.5:
                self.math_imported_needed = True
                self.modified = True
                return ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="math", ctx=ast.Load()),
                        attr="sqrt",
                        ctx=ast.Load()
                    ),
                    args=[node.left],
                    keywords=[]
                )

        # 3. Identity Simplifications
        # Multiplications
        if isinstance(node.op, ast.Mult):
            # x * 0 -> 0
            if isinstance(node.right, ast.Constant) and node.right.value == 0 and self.is_simple_node(node.left):
                self.modified = True
                return ast.Constant(value=0)
            if isinstance(node.left, ast.Constant) and node.left.value == 0 and self.is_simple_node(node.right):
                self.modified = True
                return ast.Constant(value=0)
            # x * 1 -> x
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                self.modified = True
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 1:
                self.modified = True
                return node.right
            # x * 2 -> x + x
            if isinstance(node.right, ast.Constant) and node.right.value == 2 and self.is_simple_node(node.left):
                self.modified = True
                return ast.BinOp(left=node.left, op=ast.Add(), right=copy.deepcopy(node.left))

            # Integer mult by power of 2 -> shift (e.g. x * 4 -> x << 2)
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and node.right.value > 2:
                val = node.right.value
                if (val & (val - 1)) == 0:  # Check if power of 2
                    shift_val = int(math.log2(val))
                    self.modified = True
                    return ast.BinOp(
                        left=node.left,
                        op=ast.LShift(),
                        right=ast.Constant(value=shift_val)
                    )

        # Additions / Subtractions
        if isinstance(node.op, ast.Add):
            # x + 0 -> x
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.modified = True
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                self.modified = True
                return node.right
        if isinstance(node.op, ast.Sub):
            # x - 0 -> x
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.modified = True
                return node.left

        # Floor division / Shift
        if isinstance(node.op, ast.FloorDiv) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and node.right.value > 1:
            val = node.right.value
            if (val & (val - 1)) == 0:
                shift_val = int(math.log2(val))
                self.modified = True
                return ast.BinOp(
                    left=node.left,
                    op=ast.RShift(),
                    right=ast.Constant(value=shift_val)
                )

        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        # First visit the children
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [self.visit(kw) for kw in node.keywords]

        # Check for sum(range(...)) optimizations
        if isinstance(node.func, ast.Name) and node.func.id == "sum" and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "range":
                range_args = arg.args
                # Case 1: sum(range(N)) -> (N * (N - 1)) // 2
                if len(range_args) == 1:
                    N = range_args[0]
                    self.modified = True
                    return ast.BinOp(
                        left=ast.BinOp(
                            left=N,
                            op=ast.Mult(),
                            right=ast.BinOp(
                                left=copy.deepcopy(N),
                                op=ast.Sub(),
                                right=ast.Constant(value=1)
                            )
                        ),
                        op=ast.FloorDiv(),
                        right=ast.Constant(value=2)
                    )
                # Case 2: sum(range(start, end)) -> ((end - start) * (start + end - 1)) // 2
                elif len(range_args) == 2:
                    start = range_args[0]
                    end = range_args[1]
                    self.modified = True
                    # count = end - start
                    count_node = ast.BinOp(left=end, op=ast.Sub(), right=start)
                    # sum_val = start + end - 1
                    sum_val_node = ast.BinOp(
                        left=ast.BinOp(left=copy.deepcopy(start), op=ast.Add(), right=copy.deepcopy(end)),
                        op=ast.Sub(),
                        right=ast.Constant(value=1)
                    )
                    return ast.BinOp(
                        left=ast.BinOp(left=count_node, op=ast.Mult(), right=sum_val_node),
                        op=ast.FloorDiv(),
                        right=ast.Constant(value=2)
                    )

        return node

def check_math_imported(tree: ast.Module) -> bool:
    """Checks if math module is already imported in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name == "math":
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "math":
                return True
    return False

def add_math_import(tree: ast.Module):
    """Inserts import math statement at the beginning of the AST module."""
    import_node = ast.Import(names=[ast.alias(name="math")])
    tree.body.insert(0, import_node)

def optimize_math_ast(source_code: str) -> Optional[str]:
    """
    Parses source code into AST, simplifies mathematical expressions, and unparses back.
    Returns the optimized code if modified, otherwise None.
    """
    try:
        tree = ast.parse(source_code)
        optimizer = MathASTOptimizer()
        new_tree = optimizer.visit(tree)
        
        if optimizer.modified:
            if optimizer.math_imported_needed and not check_math_imported(new_tree):
                add_math_import(new_tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
    except Exception:
        pass
    return None

def mutate_math_llm(source_code: str, orchestrator_instance: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Uses Gemini LLM to suggest deep mathematical optimizations for numerical algorithms
    (e.g., closed-form solutions, memoization, Newton's method, fast bit manipulation).
    """
    if orchestrator_instance is None or not hasattr(orchestrator_instance, "call_gemini_api") or not orchestrator_instance.has_api_access():
        return []

    system_instruction = (
        "You are Project Hermit's Mathematical Mutation Expert.\n"
        "Your task is to analyze candidate python source code and output algebraically equivalent optimizations.\n"
        "You must return your output ONLY as a valid JSON object matching the requested schema."
    )

    prompt = f"""
    Analyze the following Python source code and propose up to two distinct variants that optimize its math or calculation logic.
    Look for:
    - Replacing slow loops with direct mathematical equations or closed-form math.
    - Implementing memoization or lookup tables for recurring expensive functions (like factorials, fibonacci, primes).
    - Using bitwise tricks (shifts, masks) instead of division/multiplication or modulo.
    - Using numerical approximations (like Taylor series, fast inverse square root) if high floating-point precision is not strict.
    - Unrolling inner loops containing simple arithmetic.
    
    SOURCE CODE:
    ```python
    {source_code}
    ```

    INSTRUCTIONS:
    1. Propose up to 2 distinct optimized variants.
    2. Do NOT import third-party packages (no numpy/scipy). Only use Python's built-in libraries.
    3. Return a valid JSON matching this schema:
    {{
        "variants": [
            {{
                "branch_name": "math_variant_name (lowercase, underscore)",
                "rationale": "Mathematical justification of this optimization.",
                "code": "The complete modified Python function definition code block."
            }}
        ]
    }}
    """
    try:
        res = orchestrator_instance.call_gemini_api(prompt, system_instruction)
        if res["success"]:
            clean_text = res["text"].strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            data = json.loads(clean_text)
            return data.get("variants", [])
    except Exception:
        pass
    return []

def generate_math_mutations(source_code: str, orchestrator_instance: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Combines rule-based AST optimization and LLM optimization to produce mathematical mutations.
    """
    mutations = []
    
    # 1. Try AST-based optimizer
    ast_optimized = optimize_math_ast(source_code)
    if ast_optimized and ast_optimized.strip() != source_code.strip():
        mutations.append({
            "branch_name": "math_ast_algebraic",
            "rationale": "Applied compiler-style mathematical reductions, constant folding, and identity simplifications in AST.",
            "code": ast_optimized
        })
        
    # 2. Try LLM-based optimizer
    llm_mutations = mutate_math_llm(source_code, orchestrator_instance)
    for m in llm_mutations:
        if m.get("code") and m["code"].strip() != source_code.strip():
            # Avoid duplicate branch names
            name = m.get("branch_name", "math_llm_optimized")
            if any(x["branch_name"] == name for x in mutations):
                name += "_alt"
            mutations.append({
                "branch_name": name,
                "rationale": m.get("rationale", "LLM proposed mathematical rewrite."),
                "code": m["code"]
            })
            
    return mutations
