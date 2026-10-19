"""A small expression evaluator.

Grammar (precedence low -> high):
    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary)*
    unary   := ('+' | '-')* unary | power
    power   := primary ('^' unary)?          # right-associative
    primary := NUMBER | '(' expr ')'

`^` binds tighter than unary minus, so:  -2^2 == -(2^2) == -4
and `^` is right-associative:            2^3^2 == 2^(3^2) == 512
"""

import re

_NUM_RE = re.compile(r'\d+\.?\d*|\.\d+')


class _Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.tokens = []
        self._tokenize()

    def _tokenize(self):
        i, n = 0, len(self.text)
        while i < n:
            c = self.text[i]
            if c.isspace():
                i += 1
                continue
            if c in '+-*/^()':
                self.tokens.append((c, c))
                i += 1
                continue
            m = _NUM_RE.match(self.text, i)
            if m:
                self.tokens.append(('NUM', m.group(0)))
                i = m.end()
                continue
            raise ValueError(f"unknown character {c!r} at position {i}")


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def advance(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, kind):
        t, v = self.advance()
        if t != kind:
            raise ValueError(f"expected {kind!r}, got {v!r}")
        return v

    def parse(self):
        if not self.tokens:
            raise ValueError("empty expression")
        value = self.expr()
        if self.i != len(self.tokens):
            raise ValueError(f"trailing input: {self.peek()[1]!r}")
        return value

    def expr(self):
        value = self.term()
        while True:
            t, v = self.peek()
            if t == '+':
                self.advance()
                value = value + self.term()
            elif t == '-':
                self.advance()
                value = value - self.term()
            else:
                break
        return value

    def term(self):
        value = self.unary()
        while True:
            t, v = self.peek()
            if t == '*':
                self.advance()
                value = value * self.unary()
            elif t == '/':
                self.advance()
                rhs = self.unary()
                if rhs == 0:
                    raise ZeroDivisionError("division by zero")
                value = value / rhs
            else:
                break
        return value

    def unary(self):
        t, v = self.peek()
        if t in ('+', '-'):
            self.advance()
            operand = self.unary()
            return -operand if t == '-' else +operand
        return self.power()

    def power(self):
        base = self.primary()
        t, v = self.peek()
        if t == '^':
            self.advance()
            # right-associative; exponent may itself carry unary signs
            return base ** self.unary()
        return base

    def primary(self):
        t, v = self.peek()
        if t == 'NUM':
            self.advance()
            return float(v)
        if t == '(':
            self.advance()
            value = self.expr()
            self.expect(')')
            return value
        raise ValueError(f"unexpected token {v!r}")


def evaluate(expr: str) -> float:
    if not isinstance(expr, str):
        raise ValueError("expression must be a string")
    tokens = _Tokenizer(expr).tokens
    return _Parser(tokens).parse()
