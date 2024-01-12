#!/usr/bin/python3
"""Транслятор forthchan в машинный код.
"""

import sys

from isa import Opcode, Term, write_code
import re


def symbols():
    """Полное множество символов языка brainfuck."""
    return {"<", ">", "+", "-", ",", ".", "[", "]"}


def symbol2opcode(symbol):
    """Отображение операторов исходного кода в коды операций."""
    return {
        "<": Opcode.LEFT,
        ">": Opcode.RIGHT,
        "+": Opcode.INC,
        "-": Opcode.DEC,
        ",": Opcode.INPUT,
        ".": Opcode.PRINT,
    }.get(symbol)


def is_correct_number(char_seq: str) -> bool:
    try:
        int(char_seq)
        return True
    except ValueError:
        return False


def is_sign_word(char_seq: str) -> bool:
    if len(char_seq) != 0:
        return False
    return char_seq in ["+", "-", "/", "*"]


def is_equals_word(char_seq: str) -> bool:
    return char_seq in ["<>", "="]


def is_word(char_seq: str) -> bool:
    return re.fullmatch(r"[a-zA-Z][a-zA-Z\-]*", char_seq) \
        is not None

def is_comment_mark(char_seq: str) -> bool:
    return char_seq == "\\"


def is_correct_word_def_term(char_seq: str) -> bool:
    if char_seq.startswith(":"):
        return is_word(char_seq[1:])
    return char_seq == ";"


def is_correct_char_sequence_print(char_seq: str) -> bool:
    return re.fullmatch(r"\.\"[ !#-~]+\"", char_seq) is not None


def is_for_cycle_begin(char_seq: str) -> bool:
    return char_seq in ["do", "doi"]


def is_for_cycle_end(char_seq: str) -> bool:
    return char_seq in ["loop", "mloop"]


def is_while_cycle_begin(char_seq: str) -> bool:
    return char_seq == "begin"


def is_while_cycle_end(char_seq: str) -> bool:
    return char_seq == "until"


def lines2terms(lines):
    """Трансляция текста в последовательность операторов языка (токенов).

    Включает в себя:

    - отсеивание комментариев;
    - проверка формальной корректности программы.
    """
    terms = []
    for line_num, line in enumerate(lines, 1):
        for pos, char_seq in enumerate(re.split(r"\s+", line.rstrip()), 1):
            if is_correct_number(char_seq) or \
                    is_sign_word(char_seq) or \
                    is_equals_word(char_seq) or \
                    is_word(char_seq) or \
                    is_correct_word_def_term(char_seq) or \
                    is_correct_char_sequence_print(char_seq):
                terms.append(Term(line_num, pos, char_seq))
            elif is_comment_mark(char_seq):
                break
            else:
                assert f"Problems with {line_num}:{pos} term"
    cycles = []  # for and while
    is_in_word_def = False
    if_began_count = 0
    in_else_count = 0
    for term in terms:
        # print(term.symbol)
        if is_word(term.symbol):
            if is_for_cycle_begin(term.symbol):
                cycles.append("for")
                print(cycles)
            elif is_while_cycle_begin(term.symbol):
                cycles.append("while")
                print(cycles)
            elif is_for_cycle_end(term.symbol):
                print(cycles)
                assert len(cycles) > 0, "Bad cycle def!"
                if cycles.pop() != "for":
                    assert "Bad cycle def!"
            elif is_while_cycle_end(term.symbol):
                print(cycles)
                assert len(cycles) > 0, "Bad cycle def!"
                if cycles.pop() != "while":
                    assert "Bad cycle def!"
            elif term.symbol == "if":
                if_began_count += 1
            elif term.symbol == "else":
                assert in_else_count < if_began_count, "Bad if-else def!"
                in_else_count += 1
            elif term.symbol == "then":
                if in_else_count > 0:
                    in_else_count -= 1
                assert if_began_count > 0, "Bad if def!"
                if_began_count -= 1
            elif term.symbol[0] == ":":
                assert if_began_count == 0 and \
                       not is_in_word_def and \
                       len(cycles) == 0, "Bad word def context!"
                is_in_word_def = True
            elif term.symbol == ";":
                assert if_began_count == 0 and \
                       is_in_word_def and \
                       len(cycles) == 0, "Bad closes in word def (cycles or if statements)"
                is_in_word_def = False
    assert len(cycles) == 0 and \
           not is_in_word_def and \
           if_began_count == 0, "Bad closes (cycles, if statements or words def)"
    return terms


def exec_2dup(code, pc, term):
    code.append({"index": pc,
                 "opcode": Opcode.DUP,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.NUMBER,
                 "arg": 2,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.PICK,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.SWAP,
                 "term": term})
    pc += 1
    return code, pc


def exec_loop(code, is_inc: bool, pc, jmp_to, term):
    if is_inc:
        code.append({"index": pc,
                     "opcode": Opcode.INCREMENT_RET,
                     "term": term})
    else:
        code.append({"index": pc,
                     "opcode": Opcode.DECREMENT_RET,
                     "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.PUSH_TO_OD,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.PUSH_TO_OD,
                 "term": term})
    pc += 1
    code, pc = exec_2dup(code, pc, term)
    code.append({"index": pc,
                 "opcode": Opcode.EQ,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.POP_TO_RET,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.EXEC_COND_JMP_RET,
                 "arg": jmp_to - pc,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.SHIFT_BACK_RET,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.SHIFT_BACK_RET,
                 "term": term})
    pc += 1
    return code, pc


def exec_roll(code, pc, term):
    code.append({"index": pc,
                 "opcode": Opcode.PUSH_TO_RET,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.PUSH_0_TO_RET,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.REDUCE_OD_SHP_TO_ITS_VALUE,
                 "term": term})
    pc += 1
    cycle_first_term_pc = pc  # exec-do - no need in init and adding index stages, but need to save first cycle term pc
    code.append({"index": pc,
                 "opcode": Opcode.SHIFT_FORWARD,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.SWAP,
                 "term": term})
    pc += 1
    # exec-loop begin
    return exec_loop(code, True, pc, cycle_first_term_pc, term)


def do_init_exec(code, pc, term):
    code.append({"index": pc,
                 "opcode": Opcode.SWAP,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.POP_TO_RET,
                 "term": term})
    pc += 1
    code.append({"index": pc,
                 "opcode": Opcode.POP_TO_RET,
                 "term": term})
    pc += 1
    return code, pc

def do_index_adding_exec(code, pc, term):
    code.append({"index": pc,
                 "opcode": Opcode.PUSH_TO_OD,
                 "term": term})
    pc += 1
    return code, pc

def emit_exec(code, pc, term):
    code.append({"index": pc,
                 "opcode": Opcode.WRITE_PORT,
                 "arg": 0,
                 "term": term})
    pc += 1
    return code, pc


def translate(lines):
    """Трансляция текста программы в машинный код.

    Выполняется в два этапа:

    1. Трансляция текста в последовательность операторов языка (токенов).

    2. Генерация машинного кода.

        - Прямое отображение части операторов в машинный код.

        - Отображение операторов цикла в инструкции перехода с учётом
    вложенности и адресации инструкций. Подробнее см. в документации к
    `isa.Opcode`.

    """
    terms = lines2terms(lines)

    word_def_pc = {}
    word_jmp_pcs = {}

    code = []
    jmp_points = []
    leaves_points = []
    pc = 0
    for term in terms:
        if is_word(term.symbol):
            no_arg_opcode = None
            if term.symbol == "mod":
                no_arg_opcode = Opcode.MOD
            elif term.symbol == "dup":
                no_arg_opcode = Opcode.DUP
            elif term.symbol == "pick":
                no_arg_opcode = Opcode.PICK
            elif term.symbol == "swap":
                no_arg_opcode = Opcode.SWAP
            elif term.symbol == "drop":
                no_arg_opcode = Opcode.DROP
            if no_arg_opcode is not None:
                code.append({"index": pc,
                             "opcode": no_arg_opcode,
                             "term": term})
                pc += 1
                continue
            if term.symbol == "roll":
                code, pc = exec_roll(code, pc, term)
            elif term.symbol == "rot":
                code.append({"index": pc,
                             "opcode": Opcode.NUMBER,
                             "arg": 2,
                             "term": term})
                pc += 1
                code, pc = exec_roll(code, pc, term)
            elif term.symbol == "dudup":
                code, pc = exec_2dup(code, pc, term)
            elif term.symbol == "key":
                code.append({"index": pc,
                             "opcode": Opcode.READ_PORT,
                             "arg": 1,
                             "term": term})
                pc += 1
            elif term.symbol == "emit":
                code, pc = emit_exec(code, pc, term)
            elif term.symbol == "cr":
                code.append({"index": pc,
                             "opcode": Opcode.NUMBER,
                             "arg": 13,
                             "term": term})
                pc += 1
                code, pc = emit_exec(code, pc, term)

            # с переходами - открывающие блоки
            elif term.symbol == "do":
                code, pc = do_init_exec(code, pc, term)
                jmp_points.append(pc)
                leaves_points.append([])
            elif term.symbol == "doi":
                code, pc = do_init_exec(code, pc, term)
                jmp_points.append(pc)
                code, pc = do_index_adding_exec(code, pc, term)
                leaves_points.append([])
            elif term.symbol == "begin":
                jmp_points.append(pc)
                leaves_points.append([])
            elif term.symbol == "if":
                code.append({"index": pc,
                             "opcode": Opcode.EXEC_IF,
                             "term": term})
                pc += 1
                jmp_points.append(pc)
                code.append({"index": pc,
                             "opcode": Opcode.JMP,
                             "arg": None,
                             "term": term})
                pc += 1
            # с переходами - переходные блоки
            elif term.symbol == "else":
                if_false_jmp_pc = jmp_points.pop()
                jmp_points.append(pc)
                code.append({"index": pc,
                             "opcode": Opcode.JMP,
                             "arg": None,
                             "term": term})
                pc += 1
                code[if_false_jmp_pc]["arg"] = pc - if_false_jmp_pc
            elif term.symbol == "leave":
                leaves_points[-1].append(pc)
                code.append({"index": pc,
                             "opcode": Opcode.JMP,
                             "arg": None,
                             "term": term})
                pc += 1
            # с переходами - закрывающие блоки
            elif term.symbol == "then":
                if_true_jmp_pc = jmp_points.pop()
                code[if_true_jmp_pc]["arg"] = pc - if_true_jmp_pc
            elif term.symbol == "until":
                begin_jmp_pc = jmp_points.pop()
                code.append({"index": pc,
                             "opcode": Opcode.EXEC_COND_JMP,
                             "arg": begin_jmp_pc - pc - 1,  # указывает на инструкцию до той, на которую нужно прыгнуть
                             "term": term})
                pc += 1
                for leave_pc in leaves_points[-1]:
                    code[leave_pc]["arg"] = pc - leave_pc
                leaves_points.pop()
            elif term.symbol in ["mloop", "loop"]:
                do_jmp_pc = jmp_points.pop()
                code, pc = exec_loop(code, term.symbol == "loop", pc, do_jmp_pc, term)
                for leave_pc in leaves_points[-1]:
                    code[leave_pc]["arg"] = pc - leave_pc - 2  # -2 to delete (from, to) from stack
                leaves_points.pop()
            else:  # если пользовательское слово
                code.append({"index": pc,
                             "opcode": Opcode.PUSH_INC_INC_IP_TO_PRA_SHP,
                             "term": term})
                pc += 1
                if term.symbol not in word_jmp_pcs:
                    word_jmp_pcs[term.symbol] = []
                word_jmp_pcs[term.symbol].append(pc)
                code.append({"index": pc,
                             "opcode": Opcode.JMP,
                             "arg": None,
                             "term": term})
                pc += 1

        else:
            if is_correct_number(term.symbol):
                code.append({"index": pc,
                             "opcode": Opcode.NUMBER,
                             "arg": int(term.symbol),
                             "term": term})
                pc += 1
            elif is_sign_word(term.symbol) or is_equals_word(term.symbol):
                opcode = None
                match term.symbol:
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
                    case "<>":
                        opcode = Opcode.N_EQ
                code.append({"index": pc,
                             "opcode": opcode,
                             "term": term})
                pc += 1
            elif is_correct_word_def_term(term.symbol):
                if term.symbol == ";":
                    code.append({"index": pc,
                                 "opcode": Opcode.JMP_POP_PRA_SHP,
                                 "term": term})
                    pc += 1
                else:
                    word = term.symbol[1:]
                    word_def_pc[word] = pc
            elif is_correct_char_sequence_print(term.symbol):
                print("smth")
                print(term.symbol[2:-1])

    print(word_def_pc)
    print(word_jmp_pcs)
    for word, pcs in word_jmp_pcs.items():
        def_pc = word_def_pc[word]
        for pc in pcs:
            code[pc]["arg"] = def_pc - pc

    # Добавляем инструкцию остановки процессора в конец программы.
    code.append({"index": len(code), "opcode": Opcode.HALT})
    return code


def main(source, target):
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
