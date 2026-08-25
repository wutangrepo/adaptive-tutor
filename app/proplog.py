# Propositional logic evaluator — pure functions, no I/O.
# Optimized with AST caching (formulas repeat across students) and fast normalization.

import re
from functools import lru_cache
from itertools import product

# Translation table for single-char normalizations is faster than chained replace().
_NORMALIZE_TABLE = str.maketrans({"~": "¬", "&": "∧", "^": "∧", "|": "∨"})

def normalize(s: str) -> str:
    """Convert variant symbols to canonical ∧∨¬→↔⊕."""
    # Fast single-char pass first, then multi-char tokens.
    s = s.translate(_NORMALIZE_TABLE)
    s = s.replace("˄", "∧").replace("˅", "∨")
    s = s.replace("<->", "↔").replace("->", "→")
    # keep ' xor ' as distinct token with spaces to avoid partial word replace
    s = s.replace(" xor ", " ⊕ ")
    return s

TOKEN = re.compile(r"\s*(↔|→|∨|⊕|∧|¬|\(|\)|[A-Za-z][A-Za-z0-9_]*)")


def tokenize(s: str) -> list[str]:
    s = normalize(s)
    toks = TOKEN.findall(s)
    if re.sub(r"\s", "", s) != "".join(toks):
        raise ValueError(f"cannot tokenize: {s!r}")
    return toks


class _Parser:
    __slots__ = ("t", "i")

    def __init__(self, toks: list[str]):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, sym=None):
        tok = self.peek()
        if sym is not None and tok != sym:
            raise ValueError(f"expected {sym}, got {tok}")
        self.i += 1
        return tok

    def parse(self):
        node = self.equiv()
        if self.i != len(self.t):
            raise ValueError("trailing tokens")
        return node

    def equiv(self):  # ↔ lowest
        n = self.imp()
        while self.peek() == "↔":
            self.eat()
            n = ("↔", n, self.imp())
        return n

    def imp(self):  # → right-associative
        n = self.disj()
        if self.peek() == "→":
            self.eat()
            return ("→", n, self.imp())
        return n

    def disj(self):  # ∨
        n = self.xor()
        while self.peek() == "∨":
            self.eat()
            n = ("∨", n, self.xor())
        return n

    def xor(self):  # ⊕
        n = self.conj()
        while self.peek() == "⊕":
            self.eat()
            n = ("⊕", n, self.conj())
        return n

    def conj(self):  # ∧
        n = self.neg()
        while self.peek() == "∧":
            self.eat()
            n = ("∧", n, self.neg())
        return n

    def neg(self):  # ¬
        if self.peek() == "¬":
            self.eat()
            return ("¬", self.neg())
        return self.atom()

    def atom(self):
        tok = self.peek()
        if tok == "(":
            self.eat()
            n = self.equiv()
            self.eat(")")
            return n
        if tok is None or tok in "↔→∨⊕∧¬)":
            raise ValueError(f"unexpected {tok}")
        self.eat()
        return ("var", tok)


@lru_cache(maxsize=512)
def parse(s: str):
    return _Parser(tokenize(s)).parse()


def eval_ast(node, env: dict) -> int:
    tag = node[0]
    if tag == "var":
        name = node[1]
        if name == "T":
            return 1
        if name == "F":
            return 0
        if name not in env:
            raise ValueError(f"unbound variable {name}")
        return int(bool(env[name]))
    if tag == "¬":
        return 1 - eval_ast(node[1], env)
    a = eval_ast(node[1], env)
    b = eval_ast(node[2], env)
    # branchless dispatch is slightly faster than dict lookup per eval
    if tag == "∧":
        return a & b
    if tag == "∨":
        return a | b
    if tag == "⊕":
        return a ^ b
    if tag == "→":
        return (1 - a) | b
    if tag == "↔":
        return 1 - (a ^ b)
    raise ValueError(f"unknown operator {tag}")


@lru_cache(maxsize=512)
def variables(formula: str) -> tuple[str, ...]:
    """Sorted variable names for a formula (cached)."""
    def walk(n, acc: set):
        if n[0] == "var":
            acc.add(n[1])
        else:
            for c in n[1:]:
                # c may be tuple node
                if isinstance(c, tuple):
                    walk(c, acc)
        return acc

    vs = walk(parse(formula), set())
    # Filter constants T/F
    vs.discard("T")
    vs.discard("F")
    return tuple(sorted(vs))


def evaluate(formula: str, env: dict) -> int:
    return eval_ast(parse(formula), env)


def truth_table(formula: str):
    vs = variables(formula)
    # Reuse parsed AST to avoid re-parsing per row
    ast = parse(formula)
    return [(dict(zip(vs, bits)), eval_ast(ast, dict(zip(vs, bits)))) for bits in product([0, 1], repeat=len(vs))]


def is_tautology(formula: str) -> bool:
    return all(v == 1 for _, v in truth_table(formula))


def is_contradiction(formula: str) -> bool:
    return all(v == 0 for _, v in truth_table(formula))


def are_equivalent(f1: str, f2: str) -> bool:
    vs = tuple(sorted(set(variables(f1)) | set(variables(f2))))
    a1 = parse(f1)
    a2 = parse(f2)
    for bits in product([0, 1], repeat=len(vs)):
        env = dict(zip(vs, bits))
        if eval_ast(a1, env) != eval_ast(a2, env):
            return False
    return True
