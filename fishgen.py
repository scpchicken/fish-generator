import sys
import re
import heapq

# --- OPTIMIZED NUMBER GENERATOR ---

_NUM_FISH_CACHE = {}

def _init_num_fish():
    """Precomputes the absolute shortest Fish instruction sequence for integers using BFS."""
    global _NUM_FISH_CACHE
    dist = {}
    pq = []

    def add(val, code):
        if val < -500 or val > 2000:
            return
        if val not in dist or len(code) < len(dist[val]):
            dist[val] = code
            heapq.heappush(pq, (len(code), val, code))

    # Single hex digits 0..15 (1 char)
    for i in range(16):
        add(i, "0123456789abcdef"[i])

    # Printable ASCII characters (3 chars: 'c')
    for c in range(32, 127):
        ch = chr(c)
        if ch != "'":
            add(c, f"'{ch}'")

    # Fast single-byte control chars
    add(10, "a")  # '\n'
    add(13, "d")  # '\r'
    add(9, "9")   # '\t'

    # BFS search up to depth 6 for shortest representations
    while pq:
        l, v, code = heapq.heappop(pq)
        if len(dist[v]) < l or l >= 6:
            continue

        # Unary operations
        add(-v, f"0{code}-")
        add(v + 1, f"{code}1+")
        add(v - 1, f"{code}1-")
        add(v * 2, f"{code}:+")
        add(v * v, f"{code}:*")

        # Binary operations with small known values
        for v2, code2 in list(dist.items()):
            if len(code2) > 3:
                continue
            add(v + v2, f"{code}{code2}+")
            add(v - v2, f"{code}{code2}-")
            add(v * v2, f"{code}{code2}*")
            if v2 != 0 and v % v2 == 0:
                add(v // v2, f"{code}{code2},")
            if v2 != 0:
                add(v % v2, f"{code}{code2}%")

    _NUM_FISH_CACHE = dist

_init_num_fish()


def num_to_fish(n: int) -> str:
    """Returns the shortest Fish instruction sequence to push integer `n` onto the stack."""
    if n in _NUM_FISH_CACHE:
        return _NUM_FISH_CACHE[n]
    if n < 0:
        return num_to_fish(-n) + "0$-"
    
    # Fallback for large numbers outside precomputed cache
    q, r = divmod(n, 15)
    return num_to_fish(q) + "f*" + (f"{num_to_fish(r)}+" if r else "")


# --- AST NODES ---

class VarRef:
    """Represents variable access: simple `a` or indexed `a[expr]`."""
    def __init__(self, name: str, index=None):
        self.name = name
        self.index = index


class IntNode:
    def __init__(self, val):
        self.val = int(val)


class CharNode:
    def __init__(self, val: str):
        char_str = val[1:-1]
        if char_str.startswith("\\"):
            escapes = {'\\n': '\n', '\\t': '\t', '\\r': '\r', '\\\\': '\\', "\\'": "'", '\\0': '\0'}
            char_str = escapes.get(char_str, char_str[1:])
        self.val = ord(char_str[0])


class StringNode:
    """Represents a string literal used in print/println or string assignments."""
    def __init__(self, raw_val: str):
        content = raw_val[1:-1]
        escapes = {
            '\\n': '\n', '\\t': '\t', '\\r': '\r',
            '\\\\': '\\', '\\"': '"', "\\'": "'", '\\0': '\0'
        }
        self.text = re.sub(r'\\.', lambda m: escapes.get(m.group(0), m.group(0)[1:]), content)


class GetcNode:
    """Represents reading 1 character from standard input (Fish `i` operator)."""
    pass


class BinaryOpNode:
    """Represents binary operations like `a < b`, `a - b`, etc."""
    def __init__(self, left, op: str, right):
        self.left = left
        self.op = op
        self.right = right


class ArrayLiteralNode:
    def __init__(self, elements: list):
        self.elements = elements


class ASTNode:
    def line_count(self) -> int:
        raise NotImplementedError()


def should_use_loop(rhs) -> bool:
    """Determines whether using a loop construct is shorter than unrolling element positions."""
    if isinstance(rhs, StringNode):
        return len(rhs.text) >= 5
    elif isinstance(rhs, ArrayLiteralNode):
        return len(rhs.elements) >= 5
    return False


class AssignNode(ASTNode):
    def __init__(self, target: VarRef, op: str, rhs):
        self.target = target
        self.op = op
        self.rhs = rhs

    def line_count(self) -> int:
        if should_use_loop(self.rhs):
            return 3
        return 1


class PrintNode(ASTNode):
    def __init__(self, operand, mode='println'):
        self.operand = operand
        self.mode = mode

    def line_count(self) -> int:
        if isinstance(self.operand, StringNode):
            text = self.operand.text + ('\n' if self.mode == 'println' else '')
            if len(text) >= 15:
                return 3
        return 1


class IfNode(ASTNode):
    def __init__(self, cond, true_body, false_body):
        self.cond = cond
        self.true_body = true_body
        self.false_body = false_body

    def line_count(self) -> int:
        true_cnt = sum(n.line_count() for n in self.true_body)
        false_cnt = sum(n.line_count() for n in self.false_body)
        return 2 + true_cnt + false_cnt


class WhileNode(ASTNode):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

    def line_count(self) -> int:
        body_cnt = sum(n.line_count() for n in self.body)
        return 2 + body_cnt


# --- LEXER & PARSER ---

def tokenize(code: str):
    token_specification = [
        ('COMMENT',  r'#.*|/\*[\s\S]*?\*/'),
        ('WHILE',    r'\bwhile\b'),
        ('IF',       r'\bif\b'),
        ('ELSE',     r'\belse\b'),
        ('PRINTLN',  r'\bprintln\b'),
        ('PRINT',    r'\bprint\b'),
        ('PUTC',     r'\bputc\b'),
        ('GETC',     r'\bgetc\b'),
        ('LBRACE',   r'\{'),
        ('RBRACE',   r'\}'),
        ('LBRACK',   r'\['),
        ('RBRACK',   r'\]'),
        ('COMMA',    r','),
        ('LPAREN',   r'\('),
        ('RPAREN',   r'\)'),
        ('COMP',     r'==|!=|<=|>=|<|>'),
        ('NOT',      r'!'),
        ('OP',       r'\+=|-=|\*=|//=|\/=|%=|='),
        ('MUL_OP',   r'\/\/|\*|\/|%'),
        ('ADD_OP',   r'\+|-' ),
        ('STRING',   r'"(?:\\.|[^"\\])*"'),
        ('CHAR',     r"'(?:\\.|[^'\\])'"),
        ('INT',      r'\d+'),
        ('IDENT',    r'[a-zA-Z_]\w*'),
        ('SEMI',     r'[;\n:]+'),
        ('SKIP',     r'[ \t\r]+'),
        ('MISMATCH', r'.'),
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens = []
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind in ('SKIP', 'COMMENT'):
            continue
        elif kind == 'MISMATCH':
            raise SyntaxError(f"Unexpected character {value!r}")
        tokens.append((kind, value))
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return (None, None)

    def match(self, kind):
        k, v = self.peek()
        if k == kind:
            self.pos += 1
            return (k, v)
        return None

    def expect(self, kind):
        res = self.match(kind)
        if not res:
            k, v = self.peek()
            raise SyntaxError(f"Expected {kind}, got {k} ({v}) at token index {self.pos}")
        return res

    def parse_program(self):
        statements = []
        while self.pos < len(self.tokens):
            if self.match('SEMI'):
                continue
            if self.peek()[0] in ('RBRACE', None):
                break
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self):
        kind, val = self.peek()

        if kind == 'WHILE':
            self.expect('WHILE')
            cond = self.parse_expression()
            while self.match('SEMI'):
                pass
            self.expect('LBRACE')
            body = self.parse_program()
            self.expect('RBRACE')
            return WhileNode(cond, body)

        elif kind == 'IF':
            self.expect('IF')
            cond = self.parse_expression()
            while self.match('SEMI'):
                pass
            self.expect('LBRACE')
            true_body = self.parse_program()
            self.expect('RBRACE')

            false_body = []
            saved_pos = self.pos
            while self.match('SEMI'):
                pass
            if self.peek()[0] == 'ELSE':
                self.expect('ELSE')
                while self.match('SEMI'):
                    pass
                self.expect('LBRACE')
                false_body = self.parse_program()
                self.expect('RBRACE')
            else:
                self.pos = saved_pos

            return IfNode(cond, true_body, false_body)

        elif kind in ('PRINTLN', 'PRINT', 'PUTC'):
            self.expect(kind)
            self.expect('LPAREN')
            k, token_val = self.peek()
            if k == 'STRING':
                self.expect('STRING')
                operand = StringNode(token_val)
            else:
                operand = self.parse_expression()
            self.expect('RPAREN')
            self.match('SEMI')
            mode_map = {'PRINTLN': 'println', 'PRINT': 'print', 'PUTC': 'putc'}
            return PrintNode(operand, mode_map[kind])

        elif kind == 'IDENT':
            target = self.parse_var_ref()
            _, op = self.expect('OP')
            rhs = self.parse_rhs()
            self.match('SEMI')
            return AssignNode(target, op, rhs)

        else:
            raise SyntaxError(f"Unexpected token starting statement: {kind} ({val})")

    def parse_var_ref(self):
        _, var_name = self.expect('IDENT')
        index = None
        if self.match('LBRACK'):
            index = self.parse_expression()
            self.expect('RBRACK')
        return VarRef(var_name, index)

    def parse_expression(self):
        return self.parse_comparison()

    def parse_comparison(self):
        node = self.parse_additive()
        while self.peek()[0] == 'COMP':
            _, op = self.tokens[self.pos]
            self.pos += 1
            right = self.parse_additive()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while self.peek()[0] == 'ADD_OP':
            _, op = self.tokens[self.pos]
            self.pos += 1
            right = self.parse_multiplicative()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_multiplicative(self):
        node = self.parse_unary()
        while self.peek()[0] == 'MUL_OP':
            _, op = self.tokens[self.pos]
            self.pos += 1
            right = self.parse_unary()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_unary(self):
        if self.peek()[0] == 'ADD_OP' and self.peek()[1] == '-':
            self.pos += 1
            operand = self.parse_unary()
            if isinstance(operand, IntNode):
                return IntNode(-operand.val)
            return BinaryOpNode(IntNode(0), '-', operand)
        elif self.peek()[0] == 'NOT':
            self.pos += 1
            operand = self.parse_unary()
            return BinaryOpNode(operand, '==', IntNode(0))
        return self.parse_primary()

    def parse_primary(self):
        k, val = self.peek()
        if k == 'LPAREN':
            self.expect('LPAREN')
            expr = self.parse_expression()
            self.expect('RPAREN')
            return expr
        elif k == 'INT':
            self.expect('INT')
            return IntNode(val)
        elif k == 'CHAR':
            self.expect('CHAR')
            return CharNode(val)
        elif k == 'GETC':
            self.expect('GETC')
            if self.match('LPAREN'):
                self.expect('RPAREN')
            return GetcNode()
        elif k == 'IDENT':
            return self.parse_var_ref()
        elif k == 'STRING':
            raise SyntaxError("String literals cannot be used directly in arithmetic expressions!")
        else:
            raise SyntaxError(f"Expected expression, got {k} ({val}) at token index {self.pos}")

    def parse_rhs(self):
        if self.match('LBRACK'):
            elements = []
            if self.peek()[0] != 'RBRACK':
                while True:
                    elements.append(self.parse_expression())
                    if self.match('COMMA'):
                        continue
                    break
            self.expect('RBRACK')
            return ArrayLiteralNode(elements)
        elif self.peek()[0] == 'STRING':
            _, token_val = self.expect('STRING')
            return StringNode(token_val)
        else:
            return self.parse_expression()


# --- TRANSPILER ---

FISH_OPS = {
    '+': '+',
    '-': '-',
    '*': '*',
    '/': ',',
    '//': ',:1%-',
    '%': '%',
    '<': '(',
    '>': ')',
    '==': '=',
    '!=': '=0=',
    '<=': ')0=',
    '>=': '(0=',
}

class FishTranspiler:
    def __init__(self):
        self.var_layouts = {}  # var_name -> (base_x, y)
        self.var_stats = {}    # var_name -> {'scalar': count, 'indexed': count}

    def _analyze_vars(self, ast_nodes):
        """Pass 0: Collect all unique variables and count access frequencies."""
        self.var_stats = {}

        def walk(node):
            if isinstance(node, VarRef):
                if node.name not in self.var_stats:
                    self.var_stats[node.name] = {'scalar': 0, 'indexed': 0}
                if node.index is None:
                    self.var_stats[node.name]['scalar'] += 1
                else:
                    self.var_stats[node.name]['indexed'] += 1
                    walk(node.index)
            elif isinstance(node, AssignNode):
                walk(node.target)
                if not isinstance(node.rhs, (ArrayLiteralNode, StringNode)):
                    walk(node.rhs)
            elif isinstance(node, PrintNode):
                if not isinstance(node.operand, StringNode):
                    walk(node.operand)
            elif isinstance(node, BinaryOpNode):
                walk(node.left)
                walk(node.right)
            elif isinstance(node, IfNode):
                walk(node.cond)
                for n in node.true_body:
                    walk(n)
                for n in node.false_body:
                    walk(n)
            elif isinstance(node, WhileNode):
                walk(node.cond)
                for n in node.body:
                    walk(n)

        for node in ast_nodes:
            walk(node)

    def _optimize_layout(self, line_lengths: list):
        """
        Assigns each variable to a unique line y that minimizes total character length.
        Line y can be an existing code line (base_x = line_lengths[y]) or a new line below code (base_x = 0).
        """
        vars_sorted = sorted(
            self.var_stats.keys(),
            key=lambda v: self.var_stats[v]['scalar'] + self.var_stats[v]['indexed'],
            reverse=True
        )

        total_lines = len(line_lengths)
        used_lines = set()
        self.var_layouts = {}

        for var in vars_sorted:
            stats = self.var_stats[var]
            best_cost = float('inf')
            best_placement = (0, 0)

            max_candidate_y = total_lines + len(vars_sorted)
            for cand_y in range(max_candidate_y):
                if cand_y in used_lines:
                    continue

                if cand_y < total_lines:
                    base_x = line_lengths[cand_y]
                else:
                    base_x = 0

                x_cost = len(num_to_fish(base_x))
                y_cost = len(num_to_fish(cand_y))

                scalar_cost = stats['scalar'] * (x_cost + y_cost)

                if base_x > 0:
                    indexed_cost = stats['indexed'] * (x_cost + 1 + y_cost)
                else:
                    indexed_cost = stats['indexed'] * y_cost

                total_var_cost = scalar_cost + indexed_cost

                if total_var_cost < best_cost:
                    best_cost = total_var_cost
                    best_placement = (base_x, cand_y)

            chosen_x, chosen_y = best_placement
            self.var_layouts[var] = (chosen_x, chosen_y)
            used_lines.add(chosen_y)

    def _get_var_y(self, var_name: str) -> str:
        """Returns the y-coordinate instruction string for `var_name`."""
        return num_to_fish(self.var_layouts[var_name][1])

    def _get_addr_code(self, var_ref: VarRef) -> str:
        """Generates fish code pushing x-pos then y-pos onto stack."""
        base_x, y_coord = self.var_layouts[var_ref.name]
        y_code = num_to_fish(y_coord)

        if var_ref.index is None:
            x_code = num_to_fish(base_x)
        else:
            idx_code = self._eval_operand(var_ref.index)
            if base_x > 0:
                x_code = f"{idx_code}{num_to_fish(base_x)}+"
            else:
                x_code = idx_code

        return f"{x_code}{y_code}"

    def _build_string_push(self, text: str) -> str:
        """Generates fish code to push characters of `text` onto stack, supporting UTF-8 string literals."""
        fish_str = ""
        quote_char = "'" if ('"' in text and "'" not in text) else '"'
        in_quote = False

        for ch in text:
            code = ord(ch)
            # Allow any printable unicode character (code >= 32) except the enclosing quote character
            if ch.isprintable() and ch != quote_char and code >= 32:
                if not in_quote:
                    fish_str += quote_char
                    in_quote = True
                fish_str += ch
            else:
                if in_quote:
                    fish_str += quote_char
                    in_quote = False
                
                if code == 10:
                    fish_str += "a"
                elif code == 13:
                    fish_str += "d"
                elif code == 9:
                    fish_str += "9"
                elif code == 0:
                    fish_str += "0"
                else:
                    fish_str += num_to_fish(code)

        if in_quote:
            fish_str += quote_char
        return fish_str

    def _eval_operand(self, operand) -> str:
        """Evaluates an operand/expression leaving its value on top of the stack."""
        if isinstance(operand, IntNode) or isinstance(operand, CharNode):
            return num_to_fish(operand.val)
        elif isinstance(operand, GetcNode):
            return "i"
        elif isinstance(operand, VarRef):
            addr_code = self._get_addr_code(operand)
            return f"{addr_code}g"
        elif isinstance(operand, BinaryOpNode):
            left_code = self._eval_operand(operand.left)
            right_code = self._eval_operand(operand.right)
            fish_op = FISH_OPS[operand.op]
            return f"{left_code}{right_code}{fish_op}"
        else:
            raise ValueError(f"Unknown or invalid operand type: {type(operand)}")

    def transpile(self, code: str) -> str:
        tokens = tokenize(code)
        parser = Parser(tokens)
        ast_nodes = parser.parse_program()

        # Step 1: Analyze variable usage frequencies
        self._analyze_vars(ast_nodes)

        # Step 2: Dummy initial pass to accurately measure generated code line lengths
        total_lines = sum(node.line_count() for node in ast_nodes)
        self.var_layouts = {v: (0, total_lines + i) for i, v in enumerate(self.var_stats.keys())}

        dummy_lines = []
        curr_line = 0
        for idx, node in enumerate(ast_nodes):
            is_last = (idx == len(ast_nodes) - 1)
            nxt = None if is_last else curr_line + node.line_count()
            dummy_lines.extend(self._emit_node(node, curr_line, nxt))
            curr_line += node.line_count()

        line_lengths = [len(line) for line in dummy_lines]

        # Step 3: Determine optimal (base_x, y) coordinates per variable
        self._optimize_layout(line_lengths)

        # Step 4: Final generation pass with shortest variable coordinates
        fish_lines = []
        curr_line = 0
        for idx, node in enumerate(ast_nodes):
            is_last = (idx == len(ast_nodes) - 1)
            nxt = None if is_last else curr_line + node.line_count()
            fish_lines.extend(self._emit_node(node, curr_line, nxt))
            curr_line += node.line_count()

        return "\n".join(fish_lines)

    def _emit_node(self, node: ASTNode, start_line: int, next_line: int) -> list:
        if isinstance(node, AssignNode):
            if should_use_loop(node.rhs):
                # Efficient loop storage for longer strings/arrays
                var_name = node.target.name
                base_x_var, y_coord = self.var_layouts[var_name]
                y_code = num_to_fish(y_coord)

                # Initialize register & with starting X position
                if node.target.index is None:
                    init_x_code = f"{num_to_fish(base_x_var)}&"
                else:
                    idx_eval = self._eval_operand(node.target.index)
                    if base_x_var > 0:
                        init_x_code = f"{idx_eval}{num_to_fish(base_x_var)}+&"
                    else:
                        init_x_code = f"{idx_eval}&"

                # Push items in reverse order so element 0 is on top of stack
                if isinstance(node.rhs, StringNode):
                    push_code = self._build_string_push(node.rhs.text[::-1])
                elif isinstance(node.rhs, ArrayLiteralNode):
                    push_code = "".join(self._eval_operand(elem) for elem in reversed(node.rhs.elements))

                prefix = f">{init_x_code}{push_code}"
                
                # Loop body moving LEFT: & -> : -> 1 -> + -> & -> y_code -> p -> ^
                body_left = f"p{y_code[::-1]}&+1:&"
                num_spaces = len(body_left) - 2

                jump_next = f"0{num_to_fish(start_line + 1)}."
                jump_out = f"0{num_to_fish(next_line)}." if next_line is not None else ";"

                line_0 = f"{prefix}{jump_next}"
                line_1 = f">{' ' * num_spaces}l?v{jump_out}"
                line_2 = f"^{body_left}<"

                return [line_0, line_1, line_2]

            line_code = ">"
            if isinstance(node.rhs, ArrayLiteralNode):
                y_code = self._get_var_y(node.target.name)
                base_x = self.var_layouts[node.target.name][0]
                for idx, elem in enumerate(node.rhs.elements):
                    val_code = self._eval_operand(elem)
                    x_code = num_to_fish(base_x + idx)
                    line_code += f"{val_code}{x_code}{y_code}p"
            elif isinstance(node.rhs, StringNode):
                y_code = self._get_var_y(node.target.name)
                base_x = self.var_layouts[node.target.name][0]
                text = node.rhs.text
                line_code += self._build_string_push(text)
                for idx in range(len(text) - 1, -1, -1):
                    offset = base_x + idx
                    if node.target.index is None:
                        x_code = num_to_fish(offset)
                    else:
                        base_idx = self._eval_operand(node.target.index)
                        x_code = f"{base_idx}{num_to_fish(offset)}+" if offset > 0 else base_idx
                    line_code += f"{x_code}{y_code}p"
            else:
                addr = self._get_addr_code(node.target)
                if node.op == '=':
                    rhs_code = self._eval_operand(node.rhs)
                    line_code += f"{rhs_code}{addr}p"
                else:
                    op_map = {
                        '+=': '+', 
                        '-=': '-', 
                        '*=': '*', 
                        '/=': ',', 
                        '//=': ',:1%-', 
                        '%=': '%'
                    }
                    fish_op = op_map[node.op]
                    rhs_code = self._eval_operand(node.rhs)
                    line_code += f"{addr}g{rhs_code}{fish_op}{addr}p"

            line_code += f"0{num_to_fish(next_line)}." if next_line is not None else ";"
            return [line_code]

        elif isinstance(node, PrintNode):
            if isinstance(node.operand, StringNode):
                text = node.operand.text
                is_println = (node.mode == 'println')
                
                full_text = text + ('\n' if is_println else '')
                reversed_text = full_text[::-1]
                
                fish_str = self._build_string_push(reversed_text)

                if len(full_text) >= 15:
                    len_code = num_to_fish(len(full_text))
                    prefix = f">{fish_str}{len_code}&"
                    
                    jump_next = f"0{num_to_fish(start_line + 1)}."
                    jump_out = f"0{num_to_fish(next_line)}." if next_line is not None else ";"

                    line_0 = f"{prefix}{jump_next}"
                    line_1 = f"> &:?v{jump_out}"
                    line_2 = f"^o&-1<"
                    
                    return [line_0, line_1, line_2]
                else:
                    outputs = "o" * len(full_text)
                    line_code = f">{fish_str}{outputs}"
                    line_code += f"0{num_to_fish(next_line)}." if next_line is not None else ";"
                    return [line_code]
            else:
                val_code = self._eval_operand(node.operand)
                if node.mode == 'println':
                    out_code = "nao"
                elif node.mode == 'print':
                    out_code = "n"
                elif node.mode == 'putc':
                    out_code = "o"

                line_code = f">{val_code}{out_code}"
                line_code += f"0{num_to_fish(next_line)}." if next_line is not None else ";"
                return [line_code]

        elif isinstance(node, IfNode):
            lines = []
            true_cnt = sum(n.line_count() for n in node.true_body)
            false_cnt = sum(n.line_count() for n in node.false_body)

            L_true = start_line + 2
            L_false = start_line + 2 + true_cnt
            L_after = next_line

            cond_code = self._eval_operand(node.cond)
            target_L_false = L_false if false_cnt > 0 else L_after
            jump_false = f"0{num_to_fish(target_L_false)}." if target_L_false is not None else ";"
            line_0 = f">{cond_code}?v{jump_false}"
            lines.append(line_0)

            target_L_true = L_true if true_cnt > 0 else L_after
            jump_true = f"0{num_to_fish(target_L_true)}." if target_L_true is not None else ";"
            v_pos = 1 + len(cond_code) + 1

            if jump_true.endswith('.'):
                left_payload = ">.!" + jump_true[:-1][::-1]
            else:
                left_payload = jump_true[::-1]

            if v_pos >= len(left_payload):
                line_1 = " " * (v_pos - len(left_payload)) + f"{left_payload}<"
            else:
                line_1 = " " * v_pos + f">{jump_true}"
            lines.append(line_1)

            curr = L_true
            for idx, t_node in enumerate(node.true_body):
                is_last = (idx == len(node.true_body) - 1)
                nxt = L_after if is_last else curr + t_node.line_count()
                lines.extend(self._emit_node(t_node, curr, nxt))
                curr += t_node.line_count()

            curr = L_false
            for idx, f_node in enumerate(node.false_body):
                is_last = (idx == len(node.false_body) - 1)
                nxt = L_after if is_last else curr + f_node.line_count()
                lines.extend(self._emit_node(f_node, curr, nxt))
                curr += f_node.line_count()

            return lines

        elif isinstance(node, WhileNode):
            lines = []
            body_cnt = sum(n.line_count() for n in node.body)

            L_header0 = start_line
            L_body = start_line + 2
            L_after = next_line

            cond_code = self._eval_operand(node.cond)
            jump_false = f"0{num_to_fish(L_after)}." if L_after is not None else ";"
            line_0 = f">{cond_code}?v{jump_false}"
            lines.append(line_0)

            target_L_true = L_body if body_cnt > 0 else L_header0
            jump_true = f"0{num_to_fish(target_L_true)}."
            v_pos = 1 + len(cond_code) + 1

            if jump_true.endswith('.'):
                left_payload = ">.!" + jump_true[:-1][::-1]
            else:
                left_payload = jump_true[::-1]

            if v_pos >= len(left_payload):
                line_1 = " " * (v_pos - len(left_payload)) + f"{left_payload}<"
            else:
                line_1 = " " * v_pos + f">{jump_true}"
            lines.append(line_1)

            curr = L_body
            for idx, b_node in enumerate(node.body):
                is_last = (idx == len(node.body) - 1)
                nxt = L_header0 if is_last else curr + b_node.line_count()
                lines.extend(self._emit_node(b_node, curr, nxt))
                curr += b_node.line_count()

            return lines


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fishgenerator.py <input.c> [output.z]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else in_file.rsplit('.', 1)[0] + '.z'

    with open(in_file, 'r', encoding='utf-8') as f:
        source_code = f.read()

    transpiler = FishTranspiler()
    fish_code = transpiler.transpile(source_code)

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(fish_code)