from __future__ import annotations

import re
import sys
import math

from isa import Instruction, Opcode, Term, write_code


def is_int56(value: int) -> bool:
    if value < 0:
        return -value > -(2**56)
    else:
        return value < 2**56 - 1


def is_correct_number(char_seq: str) -> bool:
    try:
        value = int(char_seq)
        return is_int56(value)
    except ValueError:
        return False


def is_sign_word(char_seq: str) -> bool:
    return len(char_seq) == 1 and char_seq in ["+", "-", "/", "*"]


def is_comparator_word(char_seq: str) -> bool:
    return char_seq in ["<>", "=", ">", ">=", "<", "<="]


def is_user_word(char_seq: str) -> bool:
    return re.fullmatch(r"[a-zA-Z][a-zA-Z\-\\_]*", char_seq) is not None


def is_compiler_word(char_seq: str) -> bool:
    return len(char_seq) > 1 and char_seq[0] == "_" and is_user_word(char_seq[1:])


def is_string_imm_printing(char_seq: str) -> bool:
    return char_seq[0] == '"' and char_seq[-1] == '"'


def is_variable_operation(char_seq: str) -> bool:
    parts = char_seq.split("-")
    if len(parts) == 1:
        return (
            len(char_seq) > 0
            and (is_compiler_word(char_seq[:-1]) or is_user_word(char_seq[:-1]))
            and (char_seq[-1] in ["!", "?", "&"])
        )
    if len(parts) == 2:
        return (is_user_word(parts[0]) or is_compiler_word(parts[0])) and is_correct_number(parts[1])
    assert "wrong variable term"
    return False


def is_system_variable_operation(char_seq: str) -> bool:
    if char_seq[0] != "_":
        return False
    return is_variable_operation(char_seq[1:])


def is_comment_mark(char_seq: str) -> bool:
    return char_seq == "\\"


def is_correct_word_def_term(char_seq: str) -> bool:
    if char_seq.startswith(":"):
        return is_user_word(char_seq[1:])
    return char_seq == ";"


def is_for_cycle_begin(char_seq: str) -> bool:
    return char_seq in ["do", "doi"]


def is_for_cycle_end(char_seq: str) -> bool:
    return char_seq in ["loop", "mloop"]


def is_while_cycle_begin(char_seq: str) -> bool:
    return char_seq == "begin"


def is_while_cycle_end(char_seq: str) -> bool:
    return char_seq == "until"


def lines_to_terms(lines: list[str]) -> list[Term]:
    """Трансляция текста в последовательность операторов языка (токенов)

    Проверок корректности сочетания термов функция не выполняет"""

    terms: list[Term] = []
    for line_num, line in enumerate(lines, 1):
        d_quotes_sep = re.split('"', line.rstrip())
        assert len(d_quotes_sep) % 2 == 1  # их должно быть четное кол-во
        pos = 0
        for d_quotes_sep_part_num, sep_part_char_seq in enumerate(d_quotes_sep):
            if d_quotes_sep_part_num % 2 == 1:  # если это часть для печати (то, что между кавычками)
                pos += 1
                terms.append(Term(line_num, pos, f'"{sep_part_char_seq}"'))
            else:  # если это не тело для печати
                if len(sep_part_char_seq.strip()) == 0:
                    continue
                pos, part_terms, is_comment_mark_flag = not_quote_line_to_term(pos, sep_part_char_seq, line_num)
                terms.extend(part_terms)
                if is_comment_mark_flag:
                    break
    return terms


def not_quote_line_to_term(pos: int, char_seq: str, line_num: int) -> [int, list[Term], bool]:
    terms: list[Term] = []
    is_comment_mark_flag = False
    for code_char_seq in re.split(r"\s+", char_seq.strip()):
        pos += 1
        if (
            is_correct_number(code_char_seq)
            or is_sign_word(code_char_seq)
            or is_comparator_word(code_char_seq)
            or is_user_word(code_char_seq)
            or is_system_variable_operation(code_char_seq)
            or is_variable_operation(code_char_seq)
            or is_correct_word_def_term(code_char_seq)
            or is_string_imm_printing(code_char_seq)
        ):
            terms.append(Term(line_num, pos, code_char_seq))
        elif is_comment_mark(code_char_seq):
            is_comment_mark_flag = True
            break
        else:
            assert f"Problems with {line_num}:{pos} term"
    return pos, terms, is_comment_mark_flag


def code_correctness_check(terms: list[Term]):
    """Проверка формальной корректности кода"""
    blocks = []  # for, while and if
    is_in_word_def = False
    for term in terms:
        if is_user_word(term.name):
            checked = if_not_proc_block_check(term.name, blocks)
            if checked:
                continue
            _, is_in_word_def = if_proc_block_check(term.name, is_in_word_def, blocks)
    if len(blocks) != 0 or is_in_word_def:
        assert "Bad word def def!"


def if_proc_block_check(term_name: str, is_in_word_def: bool, blocks: list[dict[str, str]]) -> [bool, bool]:
    checked = True
    if term_name[0] == ":":
        if len(blocks) != 0 or is_in_word_def:
            assert "Bad word def def!"
        is_in_word_def = True
    elif term_name == ";":
        if len(blocks) != 0 or not is_in_word_def:
            assert "Bad word def def!"
        is_in_word_def = False
    else:
        checked = False
    return checked, is_in_word_def


def if_not_proc_block_check(term_name: str, blocks: list[dict[str, str]]) -> bool:
    checked = if_block_begin_check(term_name, blocks)
    if checked:
        return True
    checked = if_block_middle_check(term_name, blocks)
    if checked:
        return True
    checked = if_block_end_check(term_name, blocks)
    if checked:
        return True
    return False


def if_block_begin_check(term_name: str, blocks: list[dict[str, str]]) -> bool:
    if is_for_cycle_begin(term_name):
        blocks.append({"name": "for"})
    elif is_while_cycle_begin(term_name):
        blocks.append({"name": "while"})
    elif term_name == "if":
        blocks.append({"name": "if", "had_else": False})
    else:
        return False
    return True


def if_block_middle_check(term_name: str, blocks: list[dict[str, str]]) -> bool:
    if term_name == "else":
        if blocks[-1]["name"] != "if" or blocks[-1]["had_else"]:
            assert 'Bad "if" cycle def!'
        blocks[-1] = {"name": "if", "had_else": True}
    elif term_name == "leave":
        is_inside_loop = False
        for block in blocks:
            if block["name"] in ["for", "while"]:
                is_inside_loop = True
                break
        assert is_inside_loop, 'Bad "leave"!'
    else:
        return False
    return True


def if_block_end_check(term_name: str, blocks: list[dict[str, str]]) -> bool:
    if is_for_cycle_end(term_name):
        if blocks.pop()["name"] != "for":
            assert 'Bad "for" cycle def!'
    elif is_while_cycle_end(term_name):
        if blocks.pop()["name"] != "while":
            assert 'Bad "while" cycle def!'
    elif term_name == "then":
        if blocks.pop()["name"] != "if":
            assert 'Bad "if" cycle def!'
    else:
        return False
    return True


def exec_loop(code: list[Instruction], is_inc: bool, pc: int, jmp_to: int, term: Term) -> [list[Instruction], int]:
    if is_inc:
        code.append(Instruction(pc, Opcode.INCREMENT_RET, None, term))
    else:
        code.append(Instruction(pc, Opcode.DECREMENT_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.EQ_NOT_CONSUMING_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.EXEC_COND_JMP_RET, jmp_to - pc - 1, term))
    pc += 1
    code.append(Instruction(pc, Opcode.SHIFT_BACK_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.SHIFT_BACK_RET, None, term))
    pc += 1
    return code, pc


def do_init_exec(code: list[Instruction], pc: int, term: Term) -> [list[Instruction], int]:
    code.append(Instruction(pc, Opcode.SWAP, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.POP_TO_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.POP_TO_RET, None, term))
    pc += 1
    return code, pc


def do_index_adding_exec(code: list[Instruction], pc: int, term: Term) -> [list[Instruction], int]:
    code.append(Instruction(pc, Opcode.PUSH_TO_OD, None, term))
    pc += 1
    return code, pc


def emit_exec(code: list[Instruction], pc: int, term: Term) -> [list[Instruction], int]:
    code.append(Instruction(pc, Opcode.WRITE_PORT, 0, term))
    pc += 1
    return code, pc


def replace_complex_terms(terms: list[Term]) -> list[Term]:
    new_terms: list[Term] = []
    for term in terms:
        if term.name == "print_string":
            new_terms.extend(print_string_code_terms(term))
        elif is_string_imm_printing(term.name):
            string = term.name[1:-1]
            new_terms.extend(
                map(
                    lambda name: Term(term.line_number, term.line_position, name),
                    re.split(
                        r"\s+",
                        f"""_string-{len(string) + 1}
                    _string& _string_pointer!""",
                    ),
                )
            )
            for ch in string:
                new_terms.extend(
                    map(
                        lambda name: Term(term.line_number, term.line_position, name),
                        re.split(
                            r"\s+",
                            f"""{ord(ch)}
                        _string_pointer? put_absolute
                        _string_pointer? 1 + _string_pointer!""",
                        ),
                    )
                )
            new_terms.extend(
                map(
                    lambda name: Term(term.line_number, term.line_position, name),
                    re.split(
                        r"\s+",
                        """0 _string_pointer? put_absolute
                    _string&""",
                    ),
                )
            )
            new_terms.extend(print_string_code_terms(term))
        else:
            new_terms.append(term)
    return new_terms


def print_string_code_terms(term: Term) -> map:
    return map(
        lambda name: Term(term.line_number, term.line_position, name),
        re.split(
            r"\s+",
            """_string_pointer!
                begin
                     _string_pointer? pick_absolute
                     dup
                     if
                        drop
                        leave
                     then
                     begin
                        cant_emit
                     0 = until
                     emit
                     _string_pointer? 1 + _string_pointer!
                0 until""",
        ),
    )


def translate(lines):
    """Трансляция текста программы в машинный код"""
    terms = lines_to_terms(lines)
    code_correctness_check(terms)
    terms = replace_complex_terms(terms)

    word_def_pc: dict[str, int] = {}
    word_jmp_pcs: dict[str, list[int]] = {}

    vars_pcs: dict[str, list[dict[str, int]]] = {}

    code: list[Instruction] = []
    jmp_points: list[int] = []
    leaves_points: list[list[int]] = []
    last_word_def_jmp_pc = None
    pc = 0
    for term in terms:
        last_word_def_jmp_pc, pc = term_instruction_append(
            term, code, word_def_pc, jmp_points, leaves_points, word_jmp_pcs, vars_pcs, last_word_def_jmp_pc, pc
        )

    for word, pcs in word_jmp_pcs.items():
        def_pc = word_def_pc[word]
        for pc in pcs:
            code[pc].arg = def_pc - pc

    var_busy_cells_count = 0
    for variable_name, terms_desc in vars_pcs.items():
        max_size = 0
        for term_desc in terms_desc:
            code[term_desc["pc"]].arg = var_busy_cells_count
        for term_desc in terms_desc:
            max_size = max(max_size, term_desc["size"])
        var_busy_cells_count += max_size
        print(variable_name, max_size)
    print(f"Total busy static memory cells: {var_busy_cells_count}")

    # Добавляем инструкцию остановки процессора в конец программы.
    code.append(Instruction(len(code), Opcode.HALT, None, Term(-1, -1, "")))
    return code


def term_instruction_append(
    term: Term,
    code: list[Instruction],
    word_def_pc: dict[str, int],
    jmp_points: list[int],
    leaves_points: list[list[int]],
    word_jmp_pcs: dict[str, list[int]],
    vars_pcs: dict[str, list[dict[str, int]]],
    last_word_def_jmp_pc: int | None,
    pc: int,
) -> [int, int]:
    if is_correct_number(term.name):
        code.append(Instruction(pc, Opcode.NUMBER, int(term.name), term))
        pc += 1
        return last_word_def_jmp_pc, pc
    if is_sign_word(term.name) or is_comparator_word(term.name):
        _, pc = sign_word_or_comparator_append(term, code, pc)
        return last_word_def_jmp_pc, pc
    if is_user_word(term.name):
        pc = word_append(term, code, jmp_points, leaves_points, word_jmp_pcs, pc)
        return last_word_def_jmp_pc, pc
    if is_system_variable_operation(term.name) or is_variable_operation(term.name):
        pc = var_op_append(term, code, vars_pcs, pc)
        return last_word_def_jmp_pc, pc
    if is_correct_word_def_term(term.name):
        return word_def_append(term, code, word_def_pc, last_word_def_jmp_pc, pc)
    assert "Somehow term not matched"
    return last_word_def_jmp_pc, pc


def word_def_append(
    term: Term, code: list[Instruction], word_def_pc: dict[str, int], last_word_def_jmp_pc: int, pc: int
) -> [int, int]:
    if term.name == ";":
        code.append(Instruction(pc, Opcode.JMP_POP_PRA_SHP, None, term))
        pc += 1
        code[last_word_def_jmp_pc].arg = pc - last_word_def_jmp_pc
    else:
        last_word_def_jmp_pc = pc
        code.append(Instruction(pc, Opcode.JMP, None, term))
        pc += 1
        word = term.name[1:]
        word_def_pc[word] = pc
    return last_word_def_jmp_pc, pc


def var_op_append(term: Term, code: list[Instruction], vars_pcs: dict[str, list[dict[str, int]]], pc: int) -> int:
    parts = term.name.split("-")
    if len(parts) == 1:
        variable_name = term.name[:-1]
        match term.name[-1]:
            case "!" | "?":
                opcode = None
                if term.name[-1] == "!":
                    opcode = Opcode.WRITE_VARDATA
                else:
                    opcode = Opcode.READ_VARDATA
                code.append(Instruction(pc, opcode, None, term))
                if variable_name not in vars_pcs:
                    vars_pcs[variable_name] = []
                vars_pcs[variable_name].append({"pc": pc, "size": 1})
                pc += 1
            case "&":
                code.append(Instruction(pc, Opcode.NUMBER, None, term))
                if variable_name not in vars_pcs:
                    vars_pcs[variable_name] = []
                vars_pcs[variable_name].append({"pc": pc, "size": 1})
                pc += 1
                code.append(Instruction(pc, Opcode.SUM_TOP_WITH_VDSP, None, term))
                pc += 1
            case _:
                assert "fatal exception"
    else:  # array
        variable_name = parts[0]
        size = int(parts[1])
        if variable_name not in vars_pcs:
            vars_pcs[variable_name] = []
        vars_pcs[variable_name].append({"pc": pc, "size": size})
    return pc


def word_append(
    term: Term,
    code: list[Instruction],
    jmp_points: list[int],
    leaves_points: list[list[int]],
    word_jmp_pcs: dict[str, list[int]],
    pc: int,
) -> int:
    is_built_in, pc = if_built_in_common_commands_append(term, code, pc)
    if is_built_in:
        return pc

    is_port_command, pc = if_port_command_append(term, code, pc)
    if is_port_command:
        return pc

    is_jmp_command, pc = if_jmp_command_append(term, jmp_points, leaves_points, code, pc)
    if is_jmp_command:
        return pc

    # если пользовательское слово
    code.append(Instruction(pc, Opcode.PUSH_INC_INC_IP_TO_PRA_SHP, None, term))
    pc += 1
    if term.name not in word_jmp_pcs:
        word_jmp_pcs[term.name] = []
    word_jmp_pcs[term.name].append(pc)
    code.append(Instruction(pc, Opcode.JMP, None, term))
    pc += 1
    return pc


def sign_word_or_comparator_append(term: Term, code: list[Instruction], pc: int) -> [list[Instruction], int]:
    opcode = None
    match term.name:
        case "+":
            opcode = Opcode.SUM
        case "-":
            opcode = Opcode.DIFF
        case "*":
            opcode = Opcode.MUL
        case "/":
            opcode = Opcode.DIV
        case "=":
            opcode = Opcode.EQ
        case ">":
            opcode = Opcode.GR
        case ">=":
            opcode = Opcode.GE
        case "<":
            opcode = Opcode.LESS
        case "<=":
            opcode = Opcode.LE
        case "<>":
            opcode = Opcode.NEQ
    code.append(Instruction(pc, opcode, None, term))
    pc += 1

    return code, pc


def if_built_in_common_commands_append(term: Term, code: list[Instruction], pc: int) -> [bool, int]:
    no_arg_opcode = None
    match term.name:
        case "mod":
            no_arg_opcode = Opcode.MOD
        case "put":
            no_arg_opcode = Opcode.PUT
        case "put_absolute":
            no_arg_opcode = Opcode.PUT_ABSOLUTE
        case "pick":
            no_arg_opcode = Opcode.PICK
        case "pick_absolute":
            no_arg_opcode = Opcode.PICK_ABSOLUTE
        case "sum_top_with_vdsp":
            no_arg_opcode = Opcode.SUM_TOP_WITH_VDSP
        case "swap":
            no_arg_opcode = Opcode.SWAP
        case "drop":
            no_arg_opcode = Opcode.SHIFT_BACK
        case "dup":
            no_arg_opcode = Opcode.DUP
        case "dudup":
            no_arg_opcode = Opcode.DUDUP
    is_built_in = no_arg_opcode is not None
    if is_built_in:
        code.append(Instruction(pc, no_arg_opcode, None, term))
        pc += 1
    return is_built_in, pc


def if_port_command_append(term: Term, code: list[Instruction], pc: int) -> [bool, int]:
    is_port_command = True
    main_port_number = 0
    match term.name:
        case "cant_emit":
            code.append(Instruction(pc, Opcode.HAS_PORT_FILLED_WITH_CPU, main_port_number, term))
            pc += 1
        case "has_input":
            code.append(Instruction(pc, Opcode.HAS_PORT_FILLED_WITH_DEVICE, main_port_number, term))
            pc += 1
        case "key":
            code.append(Instruction(pc, Opcode.READ_PORT, main_port_number, term))
            pc += 1
        case "emit":
            code.append(Instruction(pc, Opcode.WRITE_PORT, main_port_number, term))
            pc += 1
        case "cr":
            code.append(Instruction(pc, Opcode.NUMBER, 13, term))
            pc += 1
            code, pc = emit_exec(code, pc, term)
        case _:
            is_port_command = False
    return is_port_command, pc


def if_jmp_command_append(
    term: Term, jmp_points: list[int], leaves_points: list[list[int]], code: list[Instruction], pc: int
) -> [bool, int]:
    is_opening, pc = if_opening_jmp_command_append(term, jmp_points, leaves_points, code, pc)
    if is_opening:
        return True, pc
    # с переходами - переходные блоки
    is_middle, pc = if_middle_jmp_command_append(term, jmp_points, leaves_points, code, pc)
    if is_middle:
        return True, pc
    # с переходами - закрывающие блоки
    is_closing, pc = if_closing_jmp_command_append(term, jmp_points, leaves_points, code, pc)
    return is_closing, pc


def if_opening_jmp_command_append(
    term: Term, jmp_points: list[int], leaves_points: list[list[int]], code: list[Instruction], pc: int
) -> [bool, int]:
    is_opening_block_command = True
    match term.name:
        case "do":
            code, pc = do_init_exec(code, pc, term)
            jmp_points.append(pc)
            leaves_points.append([])
        case "doi":
            code, pc = do_init_exec(code, pc, term)
            jmp_points.append(pc)
            code, pc = do_index_adding_exec(code, pc, term)
            leaves_points.append([])
        case "begin":
            jmp_points.append(pc)
            leaves_points.append([])
        case "if":
            code.append(Instruction(pc, Opcode.EXEC_IF, None, term))
            pc += 1
            jmp_points.append(pc)
            code.append(Instruction(pc, Opcode.JMP, None, term))
            pc += 1
        case _:
            is_opening_block_command = False
    return is_opening_block_command, pc


def if_middle_jmp_command_append(
    term: Term, jmp_points: list[int], leaves_points: list[list[int]], code: list[Instruction], pc: int
) -> [bool, int]:
    is_jmp_described_commands = True
    match term.name:
        case "else":
            if_false_jmp_pc = jmp_points.pop()
            jmp_points.append(pc)
            code.append(Instruction(pc, Opcode.JMP, None, term))
            pc += 1
            code[if_false_jmp_pc].arg = pc - if_false_jmp_pc
        case "leave":
            leaves_points[-1].append(pc)
            code.append(Instruction(pc, Opcode.JMP, None, term))
            pc += 1
        case _:
            is_jmp_described_commands = False
    return is_jmp_described_commands, pc


def if_closing_jmp_command_append(
    term: Term, jmp_points: list[int], leaves_points: list[list[int]], code: list[Instruction], pc: int
) -> [bool, int]:
    is_closing_block_commands = True
    match term.name:
        case "then":
            if_true_jmp_pc = jmp_points.pop()
            code[if_true_jmp_pc].arg = pc - if_true_jmp_pc
        case "until":
            code.append(Instruction(pc, Opcode.NUMBER, 0, term))
            pc += 1
            code.append(Instruction(pc, Opcode.NEQ, None, term))
            pc += 1
            begin_jmp_pc = jmp_points.pop()
            code.append(Instruction(pc, Opcode.EXEC_COND_JMP, begin_jmp_pc - pc - 1, term))
            # указывает на инструкцию до той, на которую нужно прыгнуть
            pc += 1
            for leave_pc in leaves_points[-1]:
                code[leave_pc].arg = pc - leave_pc
            leaves_points.pop()
        case "mloop" | "loop":
            do_jmp_pc = jmp_points.pop()
            code, pc = exec_loop(code, term.name == "loop", pc, do_jmp_pc, term)
            for leave_pc in leaves_points[-1]:
                code[leave_pc].arg = pc - leave_pc - 2  # -2 to delete (from, to) from stack
            leaves_points.pop()
        case _:
            is_closing_block_commands = False
    return is_closing_block_commands, pc


def main(source: str, target: str):
    """Функция запуска транслятора. Параметры -- исходный и целевой файлы."""
    with open(source, encoding="utf-8") as f:
        source = f.read().splitlines()
    code = translate(source)

    write_code(target, code)
    print("source LoC:", len(source), "code instr:", len(code))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, source, target = sys.argv
    main(source, target)
