"""
PineScript translation/inspection helpers (Track 5.8/5.9).

pynescript 0.3.0 is a Pine *parser/AST* library (not a turnkey python codegen).
It exposes `pynescript.ast.parse(pine_source)` -> a `Script` AST. This module
wraps that for:
  - parse_pine(src)        -> the parsed AST (raises on invalid Pine)
  - pine_to_struct(src)    -> lightweight dict of declared vars/functions/indicators
                             used by fidelity scoring (5.9) and doc generation (5.9).

Full Pine->Python codegen would build on the AST; for now we expose structure
so fidelity = structural diff between the originating Pine and the python class.
"""
from pynescript.ast import parse, walk


def parse_pine(pine_src: str):
    """Parse PineScript source into a pynescript AST. Raises on syntax error."""
    return parse(pine_src)


def pine_to_struct(pine_src: str) -> dict:
    """Extract a structural summary from Pine source.

    Returns {indicators, inputs, vars, functions} — the surface the strategy
    class must mirror for a high fidelity score.
    """
    tree = parse(pine_src)
    struct = {"indicators": [], "inputs": [], "vars": [], "functions": []}
    for node in walk(tree):
        t = type(node).__name__
        if t == "Assign":
            # heuristic: `ta.ema(...)` / `input.int(...)` calls reveal intent
            try:
                tgt = node.target.id if hasattr(node.target, "id") else str(node.target)
            except Exception:
                tgt = "?"
            struct["vars"].append(tgt)
            # detect input.* calls -> tuneable param
            val = node.value
            if type(val).__name__ == "Call":
                func = val.func
                # func is Attribute (e.g. ta.ema, input.int). base name = func.value.id
                base = getattr(func, "value", None)
                base_name = getattr(base, "id", None)
                attr_name = getattr(func, "attr", None)
                if base_name == "input":
                    struct["inputs"].append({"name": tgt, "kind": attr_name or "input"})
        elif t == "FunctionDef":
            struct["functions"].append(node.name)
        elif t == "Expr":
            # indicator(...) / strategy(...) annotation call
            val = node.value
            if type(val).__name__ == "Call":
                func = val.func
                fname = func.attr if type(func).__name__ == "Attribute" else getattr(func, "id", "?")
                if fname in ("indicator", "strategy"):
                    struct["indicators"].append(fname)
    return struct
