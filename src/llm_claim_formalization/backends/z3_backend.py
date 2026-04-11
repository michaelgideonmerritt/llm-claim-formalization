from z3 import *

def verify_with_z3(equation: str) -> dict:
    try:
        solver = Solver()

        exec_globals = {
            "Int": Int,
            "Real": Real,
            "solver": solver,
            "And": And,
            "Or": Or,
            "Not": Not,
        }

        exec(f"constraint = {equation}", exec_globals)
        constraint = exec_globals.get("constraint")

        if constraint is None:
            return {"verified": False, "error": "Failed to parse equation"}

        solver.add(Not(constraint))

        result = solver.check()
        verified = (result == unsat)

        return {
            "verified": verified,
            "solver": "z3",
            "result": str(result)
        }
    except Exception as e:
        return {
            "verified": False,
            "error": str(e)
        }
