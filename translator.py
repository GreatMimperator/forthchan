#!/usr/bin/python3
"""Транслятор forthchan в машинный код.
"""

import re
import struct
import sys

from isa import Opcode, Instruction, Term, write_code


def is_int64(value: int) -> bool:
    try:
        packed_value = struct.pack('q', value)
        return len(packed_value) == 8
    except struct.error:
        return False


def is_correct_number(char_seq: str) -> bool:
    try:
        value = int(char_seq)
        return is_int64(value)
    except ValueError:
        return False


def is_sign_word(char_seq: str) -> bool:
    return len(char_seq) == 1 and \
        char_seq in ["+", "-", "/", "*"]


def is_equals_word(char_seq: str) -> bool:
    return char_seq in ["<>", "=", ">", "<"]


def is_word(char_seq: str) -> bool:
    return re.fullmatch(r"[a-zA-Z][a-zA-Z\-\\_]*", char_seq) \
        is not None


def is_comment_mark(char_seq: str) -> bool:
    return char_seq == "\\"


def is_correct_word_def_term(char_seq: str) -> bool:
    if char_seq.startswith(":"):
        return is_word(char_seq[1:])
    return char_seq == ";"


# def is_correct_char_sequence_print(char_seq: str) -> bool:
#     return re.fullmatch(r"\.\"[ !#-~]+\"", char_seq) \
#         is not None


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
        for pos, char_seq in enumerate(re.split(r"\s+", line.rstrip()), 1):
            if is_correct_number(char_seq) or \
                    is_sign_word(char_seq) or \
                    is_equals_word(char_seq) or \
                    is_word(char_seq) or \
                    is_correct_word_def_term(char_seq):
                terms.append(Term(line_num, pos, char_seq))
            elif is_comment_mark(char_seq):
                break
            else:
                assert f"Problems with {line_num}:{pos} term"
    return terms


def code_correctness_check(terms: list[Term]):
    """Проверка формальной корректности кода"""
    blocks = []  # for, while and if
    is_in_word_def = False
    for term in terms:
        if is_word(term.name):
            if is_for_cycle_begin(term.name):
                blocks.append({"name": "for"})
            elif is_while_cycle_begin(term.name):
                blocks.append({"name": "while"})
            elif term.name == "if":
                blocks.append({"name": "if", "had_else": False})
            elif is_for_cycle_end(term.name):
                if blocks.pop()["name"] != "for":
                    assert "Bad \"for\" cycle def!"
            elif is_while_cycle_end(term.name):
                if blocks.pop()["name"] != "while":
                    assert "Bad \"while\" cycle def!"
            elif term.name == "else":
                if blocks[-1]["name"] != "if" or blocks[-1]["had_else"]:
                    assert "Bad \"if\" cycle def!"
                blocks[-1] = {"name": "if", "had_else": True}
            elif term.name == "then":
                if blocks.pop()["name"] != "if":
                    assert "Bad \"if\" cycle def!"
            elif term.name[0] == ":":
                if len(blocks) != 0 or is_in_word_def:
                    assert "Bad word def def!"
                is_in_word_def = True
            elif term.name == ";":
                if len(blocks) != 0 or not is_in_word_def:
                    assert "Bad word def def!"
                is_in_word_def = False
    if len(blocks) != 0 or is_in_word_def:
        assert "Bad word def def!"


def exec_2dup(code: list[Instruction], pc: int, term: Term) -> [list[Instruction], int]:
    code.append(Instruction(pc, Opcode.DUP, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.NUMBER, 2, term))
    pc += 1
    code.append(Instruction(pc, Opcode.PICK, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.SWAP, None, term))
    pc += 1
    return code, pc


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


def exec_roll(code: list[Instruction], pc: int, term: Term) -> [list[Instruction], int]:
    code.append(Instruction(pc, Opcode.PUSH_TO_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.PUSH_m1_TO_RET, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE, None, term))
    pc += 1
    cycle_first_term_pc = pc  # exec-do - no need in init and adding index stages, but need to save first cycle term pc
    code.append(Instruction(pc, Opcode.SHIFT_FORWARD, None, term))
    pc += 1
    code.append(Instruction(pc, Opcode.SWAP, None, term))
    pc += 1
    # exec-loop begin
    return exec_loop(code, True, pc, cycle_first_term_pc, term)


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
    code.append(Instruction(pc, Opcode.START_WRITE_PORT, 0, term))
    pc += 1
    return code, pc


def translate(lines):
    """Трансляция текста программы в машинный код"""
    terms = lines_to_terms(lines)
    code_correctness_check(terms)

    word_def_pc: dict[str, int] = {}
    word_jmp_pcs: dict[str, list[int]] = {}

    code: list[Instruction] = []
    jmp_points: list[int] = []
    leaves_points: list[list[int]] = []
    last_word_def_jmp_pc = None
    pc = 0
    for term in terms:
        if is_word(term.name):
            no_arg_opcode = None
            if term.name == "mod":
                no_arg_opcode = Opcode.MOD
            elif term.name == "dup":
                no_arg_opcode = Opcode.DUP
            elif term.name == "put":
                no_arg_opcode = Opcode.PUT
            elif term.name == "pick":
                no_arg_opcode = Opcode.PICK
            elif term.name == "swap":
                no_arg_opcode = Opcode.SWAP
            elif term.name == "drop":
                no_arg_opcode = Opcode.SHIFT_BACK
            if no_arg_opcode is not None:
                code.append(Instruction(pc, no_arg_opcode, None, term))
                pc += 1
                continue
            if term.name == "roll":
                code, pc = exec_roll(code, pc, term)
            elif term.name == "rot":
                code.append(Instruction(pc, Opcode.NUMBER, 2, term))
                pc += 1
                code, pc = exec_roll(code, pc, term)
            elif term.name == "dudup":
                code, pc = exec_2dup(code, pc, term)
            elif term.name == "stkey":
                code.append(Instruction(pc, Opcode.START_READ_PORT, 0, term))
                pc += 1
            elif term.name == "key":
                code.append(Instruction(pc, Opcode.READ_PORT, 0, term))
                pc += 1
            elif term.name == "wrote":
                code.append(Instruction(pc, Opcode.HAS_PORT_WROTE, 0, term))
                pc += 1
            elif term.name == "transferred":
                code.append(Instruction(pc, Opcode.HAS_PORT_TRANSFERRED, 0, term))
                pc += 1
            elif term.name == "emit":
                code, pc = emit_exec(code, pc, term)
            elif term.name == "cr":
                code.append(Instruction(pc, Opcode.NUMBER, 13, term))
                pc += 1
                code, pc = emit_exec(code, pc, term)
            # с переходами - открывающие блоки
            elif term.name == "do":
                code, pc = do_init_exec(code, pc, term)
                jmp_points.append(pc)
                leaves_points.append([])
            elif term.name == "doi":
                code, pc = do_init_exec(code, pc, term)
                jmp_points.append(pc)
                code, pc = do_index_adding_exec(code, pc, term)
                leaves_points.append([])
            elif term.name == "begin":
                jmp_points.append(pc)
                leaves_points.append([])
            elif term.name == "if":
                code.append(Instruction(pc, Opcode.EXEC_IF, None, term))
                pc += 1
                jmp_points.append(pc)
                code.append(Instruction(pc, Opcode.JMP, None, term))
                pc += 1
            # с переходами - переходные блоки
            elif term.name == "else":
                if_false_jmp_pc = jmp_points.pop()
                jmp_points.append(pc)
                code.append(Instruction(pc, Opcode.JMP, None, term))
                pc += 1
                code[if_false_jmp_pc].arg = pc - if_false_jmp_pc
            elif term.name == "leave":
                leaves_points[-1].append(pc)
                code.append(Instruction(pc, Opcode.JMP, None, term))
                pc += 1
            # с переходами - закрывающие блоки
            elif term.name == "then":
                if_true_jmp_pc = jmp_points.pop()
                code[if_true_jmp_pc].arg = pc - if_true_jmp_pc
            elif term.name == "until":
                code.append(Instruction(pc, Opcode.NUMBER, 0, term))
                pc += 1
                code.append(Instruction(pc, Opcode.N_EQ, None, term))
                pc += 1
                begin_jmp_pc = jmp_points.pop()
                code.append(Instruction(pc, Opcode.EXEC_COND_JMP, begin_jmp_pc - pc - 1, term))
                # указывает на инструкцию до той, на которую нужно прыгнуть
                pc += 1
                for leave_pc in leaves_points[-1]:
                    code[leave_pc].arg = pc - leave_pc
                leaves_points.pop()
            elif term.name in ["mloop", "loop"]:
                do_jmp_pc = jmp_points.pop()
                code, pc = exec_loop(code, term.name == "loop", pc, do_jmp_pc, term)
                for leave_pc in leaves_points[-1]:
                    code[leave_pc].arg = pc - leave_pc - 2  # -2 to delete (from, to) from stack
                leaves_points.pop()
            else:  # если пользовательское слово
                code.append(Instruction(pc, Opcode.PUSH_INC_INC_IP_TO_PRA_SHP, None, term))
                pc += 1
                if term.name not in word_jmp_pcs:
                    word_jmp_pcs[term.name] = []
                word_jmp_pcs[term.name].append(pc)
                code.append(Instruction(pc, Opcode.JMP, None, term))
                pc += 1
        else:
            if is_correct_number(term.name):
                code.append(Instruction(pc, Opcode.NUMBER, int(term.name), term))
                pc += 1
            elif is_sign_word(term.name) or is_equals_word(term.name):
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
                        opcode = Opcode.IS_OVER
                    case "<":
                        opcode = Opcode.IS_LOWER
                    case "<>":
                        opcode = Opcode.N_EQ
                code.append(Instruction(pc, opcode, None, term))
                pc += 1
            elif is_correct_word_def_term(term.name):
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
            else:
                assert "Somehow term not matched"

    for word, pcs in word_jmp_pcs.items():
        def_pc = word_def_pc[word]
        for pc in pcs:
            code[pc].arg = def_pc - pc

    # Добавляем инструкцию остановки процессора в конец программы.
    code.append(Instruction(len(code), Opcode.HALT, None, Term(-1, -1, '')))
    return code


def main(source: str, target: str):
    """Функция запуска транслятора. Параметры -- исходный и целевой файлы."""
    with open(source, encoding="utf-8") as f:
        source = f.read().splitlines()
    print(source)
    code = translate(source)

    write_code(target, code)
    print("source LoC:", len(source), "code instr:", len(code))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, source, target = sys.argv
    main(source, target)
