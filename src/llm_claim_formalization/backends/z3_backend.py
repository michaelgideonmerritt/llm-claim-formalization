from __future__ import annotations

import ast
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from z3 import (
    And,
    BoolVal,
    Not,
    Or,
    Real,
    RealVal,
    Solver,
    is_bool,
    simplify,
    unsat,
)


class UnsafeExpressionError(ValueError):
    """Raised when an input expression contains unsupported syntax."""


def _normalize_equation(equation: str) -> str:
    """Normalize user-provided equations into Python/Z3-compatible expression syntax."""
    normalized = equation.strip()
    normalized = normalized.replace("≤", "<=").replace("≥", ">=")
    # Convert bare equality to Python equality while preserving <=, >=, !=, ==.
    normalized = re.sub(r"(?<![<>=!])=(?!=)", "==", normalized)
    return normalized


class _SafeZ3Parser:
    """AST parser that converts a restricted expression subset to Z3 terms."""

    def __init__(self) -> None:
        self.variables: dict[str, Any] = {}

    def parse(self, equation: str) -> tuple[Any, str]:
        normalized = _normalize_equation(equation)
        try:
            tree = ast.parse(normalized, mode="eval")
        except SyntaxError as exc:
            raise UnsafeExpressionError(f"Invalid syntax: {exc.msg}") from exc
        expr = self._convert(tree.body)
        return expr, normalized

    def _convert(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return self._convert_constant(node.value)

        if isinstance(node, ast.Name):
            return self._get_or_create_variable(node.id)

        if isinstance(node, ast.BinOp):
            left = self._convert(node.left)
            right = self._convert(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right

            raise UnsafeExpressionError(f"Unsupported binary operator: {type(node.op).__name__}")

        if isinstance(node, ast.UnaryOp):
            operand = self._convert(node.operand)

            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.Not):
                return Not(operand)

            raise UnsafeExpressionError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.BoolOp):
            values = [self._convert(value) for value in node.values]
            if isinstance(node.op, ast.And):
                return And(*values)
            if isinstance(node.op, ast.Or):
                return Or(*values)
            raise UnsafeExpressionError(f"Unsupported boolean operator: {type(node.op).__name__}")

        if isinstance(node, ast.Compare):
            left = self._convert(node.left)
            constraints: list[Any] = []

            for op, comparator in zip(node.ops, node.comparators):
                right = self._convert(comparator)
                constraints.append(self._convert_comparison(op, left, right))
                left = right

            return constraints[0] if len(constraints) == 1 else And(*constraints)

        raise UnsafeExpressionError(f"Unsupported expression node: {type(node).__name__}")

    @staticmethod
    def _convert_constant(value: Any) -> Any:
        if isinstance(value, bool):
            return BoolVal(value)

        if isinstance(value, (int, float)):
            return RealVal(str(value))

        raise UnsafeExpressionError(f"Unsupported literal type: {type(value).__name__}")

    def _get_or_create_variable(self, name: str) -> Any:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise UnsafeExpressionError(f"Unsupported variable name: {name!r}")

        if name not in self.variables:
            self.variables[name] = Real(name)

        return self.variables[name]

    @staticmethod
    def _convert_comparison(op: ast.cmpop, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right

        raise UnsafeExpressionError(f"Unsupported comparison operator: {type(op).__name__}")


def _to_plain_number(value: Any) -> float | int | None:
    """Best-effort conversion of Z3 simplified numeral to Python number."""
    text = str(value)

    if re.fullmatch(r"-?\d+", text):
        return int(text)

    if re.fullmatch(r"-?\d+/\d+", text):
        numerator, denominator = text.split("/", maxsplit=1)
        try:
            return float(Decimal(numerator) / Decimal(denominator))
        except (InvalidOperation, ZeroDivisionError):
            return None

    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None

    if parsed == parsed.to_integral_value():
        return int(parsed)
    return float(parsed)


def verify_with_z3(equation: str) -> dict[str, Any]:
    """
    Verify a formal expression using Z3.

    Returns:
    - Boolean claims: verified True/False with SAT/UNSAT status.
    - Arithmetic expressions: computed numeric value (verified=None).
    """
    parser = _SafeZ3Parser()

    try:
        expr, normalized_equation = parser.parse(equation)
    except UnsafeExpressionError as exc:
        return {
            "verified": False,
            "error": str(exc),
            "solver": "z3",
            "normalized_equation": equation,
        }

    try:
        if is_bool(expr):
            solver = Solver()
            solver.add(Not(expr))
            result = solver.check()
            verified = result == unsat

            return {
                "verified": verified,
                "solver": "z3",
                "result": str(result),
                "normalized_equation": normalized_equation,
                "variables": sorted(parser.variables.keys()),
            }

        # For non-boolean expressions, return computed value instead of failing.
        value = simplify(expr)
        return {
            "verified": None,
            "solver": "z3",
            "result": "computed",
            "normalized_equation": normalized_equation,
            "value": str(value),
            "value_numeric": _to_plain_number(value),
            "variables": sorted(parser.variables.keys()),
        }
    except Exception as exc:  # pragma: no cover - defensive guard around solver internals
        return {
            "verified": False,
            "error": str(exc),
            "solver": "z3",
            "normalized_equation": normalized_equation,
        }
