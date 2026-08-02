import sys
import re

def num_to_fish(n: int) -> str:
    """Generates fish instructions to push integer `n` onto the stack."""
    if n < 0:
        return num_to_fish(-n) + "0$-"
    if n <= 15:
        return "0123456789abcdef"[n]
    
    digits = []
    temp = n
    while temp > 0:
        digits.append(temp % 15)
        temp //= 15
    digits.reverse()
    
    code = num_to_fish(digits[0])
    for d in digits[1:]:
        code += "f*"
        if d > 0:
            code += f"{num_to_fish(d)}+"
    return code


# --- AST NODES ---

class VarRef:
    """Represents variable access: simple `a` or indexed `a[expr]`."""
    def __init__(self, name: str, index=None):
        self.name = name
        self.index = index  # None (defaults to x=0) or an operand node


class IntNode:
    def __init__(self, val: str):
        self.val = int(val)


class CharNode:
    def __init__(self, val: str):
        char_str = val[1:-1]
        if char_str.startswith("\\"):
            escapes = {'\\n': '\n', '\\t': '\t', '\\r': '\r', '\\\\': '\\', "\\'": "'", '\\0': '\0'}
            char_str = escapes.get(char_str, char_str[1:])
        self.val = ord(char_str[0])


class StringNode:
    """Represents a string literal used in print/println."""
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


class ArrayLiteralNode:
    def __init__(self, elements: list):
        self.elements = elements  # List of operands


class ASTNode:
    def line_count(self) -> int:
        raise NotImplementedError()


class AssignNode(ASTNode):
    def __init__(self, target: VarRef, op: str, rhs):
        self.target = target
        self.op = op
        self.rhs = rhs

    def line_count(self) -> int:
        return 1


class PrintNode(ASTNode):
    def __init__(self, operand, mode='println'):
        self.operand = operand  # Can be an operand node or a StringNode
        self.mode = mode        # 'println', 'print', or 'putc'

    def line_count(self) -> int:
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
        ('COMMENT',  r'#.*'),
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
        ('OP',       r'\+=|-=|\*=|//=|\/=|%=|='),
        ('STRING',   r'"(?:\\.|[^"\\])*"'),
        ('CHAR',     r"'(?:\\.|[^'\\])'"),
        ('INT',      r'-?\d+'),
        ('IDENT',    r'[a-zA-Z_]\w*'),
        ('SEMI',     r'[;\n]+'),
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
            cond = self.parse_operand()
            self.expect('LBRACE')
            body = self.parse_program()
            self.expect('RBRACE')
            return WhileNode(cond, body)

        elif kind == 'IF':
            self.expect('IF')
            cond = self.parse_operand()
            self.expect('LBRACE')
            true_body = self.parse_program()
            self.expect('RBRACE')

            false_body = []
            saved_pos = self.pos
            while self.match('SEMI'):
                pass
            if self.peek()[0] == 'ELSE':
                self.expect('ELSE')
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
                operand = self.parse_operand()
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
            index = self.parse_operand()
            self.expect('RBRACK')
        return VarRef(var_name, index)

    def parse_operand(self):
        k, val = self.peek()
        if k == 'INT':
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
            raise SyntaxError("String literals cannot be assigned to variables or stored in arrays!")
        else:
            raise SyntaxError(f"Expected operand (INT, CHAR, GETC, or IDENT), got {k} ({val})")

    def parse_rhs(self):
        if self.match('LBRACK'):
            elements = []
            if self.peek()[0] != 'RBRACK':
                while True:
                    elements.append(self.parse_operand())
                    if self.match('COMMA'):
                        continue
                    break
            self.expect('RBRACK')
            return ArrayLiteralNode(elements)
        else:
            return self.parse_operand()


# --- TRANSPILER ---

class FishTranspiler:
    def __init__(self):
        self.var_map = {}
        self.base_y = 100

    def _get_var_y(self, var_name: str) -> str:
        """Returns the y-coordinate instruction string for `var_name`."""
        if var_name not in self.var_map:
            self.var_map[var_name] = len(self.var_map)
        y_coord = self.base_y + self.var_map[var_name]
        return num_to_fish(y_coord)

    def _eval_operand(self, operand) -> str:
        """Generates fish code that evaluates an operand and leaves its value on top of stack."""
        if isinstance(operand, IntNode) or isinstance(operand, CharNode):
            return num_to_fish(operand.val)
        elif isinstance(operand, GetcNode):
            return "i"
        elif isinstance(operand, VarRef):
            addr_code = self._get_addr_code(operand)
            return f"{addr_code}g"
        else:
            raise ValueError(f"Unknown or invalid operand type: {type(operand)}")

    def _get_addr_code(self, var_ref: VarRef) -> str:
        """Generates fish code that pushes x-pos then y-pos onto the stack."""
        y_code = self._get_var_y(var_ref.name)
        if var_ref.index is None:
            x_code = "0"
        else:
            x_code = self._eval_operand(var_ref.index)
        return f"{x_code}{y_code}"

    def transpile(self, code: str) -> str:
        self.var_map = {}
        tokens = tokenize(code)
        parser = Parser(tokens)
        ast_nodes = parser.parse_program()

        total_lines = sum(node.line_count() for node in ast_nodes)
        self.base_y = total_lines + 100

        fish_lines = []
        curr_line = 0

        for idx, node in enumerate(ast_nodes):
            is_last = (idx == len(ast_nodes) - 1)
            nxt = None if is_last else curr_line + node.line_count()
            lines = self._emit_node(node, curr_line, nxt)
            fish_lines.extend(lines)
            curr_line += node.line_count()

        return "\n".join(fish_lines)

    def _emit_node(self, node: ASTNode, start_line: int, next_line: int) -> list:
        if isinstance(node, AssignNode):
            line_code = ">"
            if isinstance(node.rhs, ArrayLiteralNode):
                # Array literal: assign elements sequentially along row y
                y_code = self._get_var_y(node.target.name)
                for idx, elem in enumerate(node.rhs.elements):
                    val_code = self._eval_operand(elem)
                    x_code = num_to_fish(idx)
                    line_code += f"{val_code}{x_code}{y_code}p"
            else:
                addr = self._get_addr_code(node.target)
                if node.op == '=':
                    rhs_code = self._eval_operand(node.rhs)
                    line_code += f"{rhs_code}{addr}p"
                else:
                    op_map = {'+=': '+', '-=': '-', '*=': '*', '/=': ',', '//=': ',', '%=': '%'}
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
                
                fish_str = ""
                in_quote = False
                
                for ch in reversed_text:
                    code = ord(ch)
                    # Safe printable ASCII inside fish string mode (excluding double quotes & control chars)
                    if 32 <= code <= 126 and ch != '"':
                        if not in_quote:
                            fish_str += '"'
                            in_quote = True
                        fish_str += ch
                    else:
                        if in_quote:
                            fish_str += '"'
                            in_quote = False
                        
                        # Handle special characters cleanly without breaking grid line alignment
                        if code == 10:    # \n -> hex 'a'
                            fish_str += "a"
                        elif code == 13:  # \r -> hex 'd'
                            fish_str += "d"
                        elif code == 9:   # \t -> '9'
                            fish_str += "9"
                        else:
                            fish_str += num_to_fish(code)

                if in_quote:
                    fish_str += '"'

                outputs = "o" * len(full_text)
                line_code = f">{fish_str}{outputs}"
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
            L_header1 = start_line + 1
            L_body = start_line + 2
            L_after = next_line

            cond_code = self._eval_operand(node.cond)
            jump_false = f"0{num_to_fish(L_after)}." if L_after is not None else ";"
            line_0 = f">{cond_code}?v{jump_false}"
            lines.append(line_0)

            target_L_true = L_body if body_cnt > 0 else L_header0
            jump_true = f"0{num_to_fish(target_L_true)}."
            v_pos = 1 + len(cond_code) + 1
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