def evaluate(expr: str) -> float:
    """
    Evaluate a mathematical expression string.
    
    Supported:
    - Numbers: ints (2) and decimals (2.5, .5)
    - Operators: + - * / ^
    - ^ is right-associative, binds tighter than unary -/+
    - Unary plus/minus
    - Parentheses
    - Spaces anywhere
    
    Raises:
    - ValueError for invalid expressions
    - ZeroDivisionError for division by zero
    """
    
    # Remove all spaces
    s = expr.replace(' ', '')
    
    if not s:
        raise ValueError("Empty expression")
    
    # Tokenize
    tokens = []
    i = 0
    while i < len(s):
        c = s[i]
        
        if c.isdigit() or c == '.':
            # Parse number
            start = i
            has_dot = (c == '.')
            i += 1
            while i < len(s) and (s[i].isdigit() or s[i] == '.'):
                if s[i] == '.':
                    if has_dot:
                        raise ValueError("Invalid number: multiple decimal points")
                    has_dot = True
                i += 1
            num_str = s[start:i]
            if num_str == '.' or num_str == '':
                raise ValueError("Invalid number")
            try:
                num = float(num_str)
            except ValueError:
                raise ValueError("Invalid number")
            tokens.append(('NUM', num))
        
        elif c in '+-*/^()':
            tokens.append(('OP', c))
            i += 1
        
        else:
            raise ValueError(f"Unknown character: {c}")
    
    if not tokens:
        raise ValueError("Empty expression")
    
    # Parse using recursive descent
    class Parser:
        def __init__(self, tokens):
            self.tokens = tokens
            self.pos = 0
        
        def peek(self):
            if self.pos < len(self.tokens):
                return self.tokens[self.pos]
            return None
        
        def consume(self):
            token = self.peek()
            if token:
                self.pos += 1
            return token
        
        def parse_expression(self):
            """Parse addition and subtraction (lowest precedence)"""
            value = self.parse_term()
            
            while self.peek() and self.peek()[0] == 'OP' and self.peek()[1] in ('+', '-'):
                op = self.consume()[1]
                right = self.parse_term()
                if op == '+':
                    value += right
                else:
                    value -= right
            return value
        
        def parse_term(self):
            """Parse multiplication and division"""
            value = self.parse_power()
            
            while self.peek() and self.peek()[0] == 'OP' and self.peek()[1] in ('*', '/'):
                op = self.consume()[1]
                right = self.parse_power()
                if op == '*':
                    value *= right
                else:
                    if right == 0:
                        raise ZeroDivisionError("Division by zero")
                    value /= right
            return value
        
        def parse_power(self):
            """Parse power (right-associative).
            Since ^ binds tighter than unary, we parse the primary first,
            then apply ^, then apply unary.
            Wait - that's not right either.
            
            Correct interpretation: ^ binds tighter than unary.
            So in -2^2, the ^ happens before the unary -.
            Meaning: - (2^2) = -4.
            
            So the parse order should be:
            parse_expression (+/-)
              -> parse_term (* /)
                -> parse_power (^)
                  -> parse_unary (+/- unary)
                    -> parse_primary (num or (expr))
            
            But if parse_unary is called from parse_power, then unary is parsed
            BEFORE power, which means unary binds LOoser than power.
            That's what we want! parse_unary wraps around parse_power.
            
            So: parse_power calls parse_unary, and parse_unary applies +/- to
            whatever parse_power returns. But parse_unary should also handle
            the case where there's no unary op.
            
            Actually, let's think about it as:
            parse_power() returns the result of parsing a "power term"
            A power term is: unary_ops? primary (^ primary)*
            
            No, that's getting complicated. Let me use a simpler approach:
            
            parse_expression -> parse_term -> parse_power -> parse_unary -> parse_primary
            
            Where parse_unary handles unary +/- and calls parse_power.
            But then parse_power would call parse_unary, creating a cycle.
            
            Let me structure it as:
            parse_expression -> parse_term -> parse_power
            parse_power -> parse_unary
            parse_unary -> parse_primary
            
            And parse_unary handles ONE layer of unary ops.
            """
            # Parse a "unary" level, which includes the power operator
            # Since ^ binds tighter than unary, we parse primary, then ^, then 
            # any unary ops on the result? No, that's wrong too.
            
            # Let's think about -2^2:
            # Tokens: [-, 2, ^, 2]
            # We want: -(2^2) = -4
            # So the unary - wraps around the power expression 2^2
            
            # Structure:
            # parse_power() should parse: unary_ops? primary (^ primary)*
            # But unary ops bind looser than ^, so they should be applied AFTER
            # the power is parsed.
            
            # So: parse_power calls parse_primary, then handles ^, then
            # we need to apply unary ops. But unary ops are parsed at a higher level.
            
            # Actually, the cleanest way:
            # parse_unary() handles unary +/- and calls parse_power()
            # parse_power() handles ^ and calls parse_unary()
            # This creates the right precedence: unary wraps power, power wraps primary
            
            return self.parse_unary_with_power()
        
        def parse_unary_with_power(self):
            """Handle unary +/- and power operator together.
            Since ^ binds tighter than unary, we parse the power expression
            first (via primary), then apply unary.
            But ^ is right-associative, so we need to handle it recursively.
            """
            # First, handle any unary operators
            if self.peek() and self.peek()[0] == 'OP' and self.peek()[1] in ('+', '-'):
                op = self.consume()[1]
                value = self.parse_unary_with_power()
                if op == '-':
                    value = -value
                return value
            
            # Now parse the power expression (primary, possibly with ^)
            base = self.parse_primary()
            
            # Handle right-associative ^ operator
            if self.peek() and self.peek()[0] == 'OP' and self.peek()[1] == '^':
                self.consume()
                exponent = self.parse_unary_with_power()  # right-associative
                return base ** exponent
            
            return base
        
        def parse_primary(self):
            """Parse numbers and parentheses"""
            token = self.peek()
            
            if token is None:
                raise ValueError("Unexpected end of expression")
            
            if token[0] == 'NUM':
                self.consume()
                return token[1]
            
            if token[0] == 'OP' and token[1] == '(':
                self.consume()  # consume '('
                value = self.parse_expression()
                if self.peek() is None or self.peek()[0] != 'OP' or self.peek()[1] != ')':
                    raise ValueError("Missing closing parenthesis")
                self.consume()  # consume ')'
                return value
            
            raise ValueError("Unexpected token")
    
    parser = Parser(tokens)
    result = parser.parse_expression()
    
    # Check that all tokens were consumed
    if parser.pos != len(tokens):
        raise ValueError("Unexpected extra tokens")
    
    return result