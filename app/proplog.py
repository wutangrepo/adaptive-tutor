# Propositional logic formula evaluator (pure function, no dependencies)
import re
from itertools import product


def normalize(s: str) -> str:
    """Normalize the formula by converting various representations to standard symbols."""
    s = s.replace('˄', '∧').replace('˅', '∨')
    s = s.replace('<->', '↔').replace('->', '→')
    s = s.replace('~', '¬')
    s = s.replace('&', '∧').replace('^', '∧').replace('|', '∨')
    s = s.replace(' xor ', ' ⊕ ')
    return s


TOKEN = re.compile(r'\s*(↔|→|∨|⊕|∧|¬|\(|\)|[A-Za-z][A-Za-z0-9_]*)')


def tokenize(s: str) -> list:
    s = normalize(s)
    toks = TOKEN.findall(s)
    if re.sub(r'\s', '', s) != ''.join(toks):
        raise ValueError(f"cannot tokenize: {s!r}")
    return toks


class _Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

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

    def equiv(self):                      # ↔ Lowest precedence
        n = self.imp()
        while self.peek() == '↔':
            self.eat(); n = ('↔', n, self.imp())
        return n

    def imp(self):                        # → Right associative
        n = self.disj()
        if self.peek() == '→':
            self.eat(); return ('→', n, self.imp())
        return n

    def disj(self):                       # ∨
        n = self.xor()
        while self.peek() == '∨':
            self.eat(); n = ('∨', n, self.xor())
        return n

    def xor(self):                        # ⊕
        n = self.conj()
        while self.peek() == '⊕':
            self.eat(); n = ('⊕', n, self.conj())
        return n

    def conj(self):                       # ∧
        n = self.neg()
        while self.peek() == '∧':
            self.eat(); n = ('∧', n, self.neg())
        return n

    def neg(self):                        # ¬
        if self.peek() == '¬':
            self.eat(); return ('¬', self.neg())
        return self.atom()

    def atom(self):
        tok = self.peek()
        if tok == '(':
            self.eat(); n = self.equiv(); self.eat(')'); return n
        if tok is None or tok in '↔→∨⊕∧¬)':
            raise ValueError(f"unexpected {tok}")
        self.eat()
        return ('var', tok)


def parse(s: str):
    return _Parser(tokenize(s)).parse()


def eval_ast(node, env):
    tag = node[0]
    if tag == 'var':
        name = node[1]
        if name == 'T':
            return 1
        if name == 'F':
            return 0
        if name not in env:
            raise ValueError(f"unbound variable {name}")
        return int(bool(env[name]))
    if tag == '¬':
        return 1 - eval_ast(node[1], env)
    a, b = eval_ast(node[1], env), eval_ast(node[2], env)
    return {'∧': a & b, '∨': a | b, '⊕': a ^ b,
            '→': (1 - a) | b, '↔': 1 - (a ^ b)}[tag]


def variables(formula: str) -> list:
    def walk(n, acc):
        if n[0] == 'var':
            acc.add(n[1])
        else:
            for c in n[1:]:
                walk(c, acc)
        return acc
    return sorted(walk(parse(formula), set()))


def evaluate(formula: str, env: dict) -> int:
    return eval_ast(parse(formula), env)


def truth_table(formula: str):
    vs = variables(formula)
    return [(dict(zip(vs, bits)), evaluate(formula, dict(zip(vs, bits))))
            for bits in product([0, 1], repeat=len(vs))]


def is_tautology(formula: str) -> bool:
    return all(v == 1 for _, v in truth_table(formula))


def is_contradiction(formula: str) -> bool:
    return all(v == 0 for _, v in truth_table(formula))


def are_equivalent(f1: str, f2: str) -> bool:
    vs = sorted(set(variables(f1)) | set(variables(f2)))
    return all(evaluate(f1, dict(zip(vs, b))) == evaluate(f2, dict(zip(vs, b)))
               for b in product([0, 1], repeat=len(vs)))