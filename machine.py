#!/usr/bin/python3
"""Модель процессора, позволяющая выполнить машинный код полученный из программы
на языке Brainfuck.

Модель включает в себя три основных компонента:

- `DataPath` -- работа с памятью данных и вводом-выводом.

- `ControlUnit` -- работа с памятью команд и их интерпретация.

- и набор вспомогательных функций: `simulation`, `main`.
"""

import logging
import sys

from isa import Opcode, read_code, Term, Instruction


class HistoricalInput:
    instruction_index: int
    port_index: int
    data_to_put: int

    def __init__(self, instruction_index: int, port_index: int, data_to_put: int):
        self.instruction_index = instruction_index
        self.port_index = port_index
        self.data_to_put = data_to_put


class Port:
    ready: bool = False
    data: int = None


class InterruptablePort:
    port: Port
    interrupt_code_on_read: list[Instruction]
    interrupt_code_on_write: list[Instruction]

    def __init__(self, interrupt_code_on_read: list[Instruction], interrupt_code_on_write: list[Instruction]):
        self.port = Port()
        self.interrupt_code_on_read = interrupt_code_on_read
        self.interrupt_code_on_write = interrupt_code_on_write


class DataPath:
    data_memory_size: int = None
    "Размер памяти данных."

    data_memory: list[int | Instruction] = None
    "Память данных. Инициализируется нулевыми значениями."

    interruption_procedures_points_table_begin: int = None
    "Указывает на точку начала перечисления указателей на процедуры обработчиков прерываний " \
    "(формат WRWRWR... для 0, 1, 2... портов). " \
    "До него располагаются сами эти процедуры, обязательно оканчивающиеся HALT-ом"

    instruction_pointer: int = None
    "Instruction Pointer - Указатель на текущую инструкцию"

    PRA_SH_pointer: int = None
    "Procedure Return Addresses Stack Head Pointer - служебный стек"

    OD_SH_pointer: int = None
    "Operational Data Stack Head Pointer - пользовательский стек"

    instruction_stage_number: int = None
    "Instruction Stage Number - счетчик стадий команды"

    def __init__(self, memory_size, ports_description: list[InterruptablePort], program: list[Instruction]):
        assert memory_size > 0, "Data_memory size should be non-zero"
        self.data_memory_size = memory_size
        self.data_memory = [0] * memory_size
        assert len(ports_description) >= 2, "Not enough ports for built-in instructions"
        procedures_points_table: list[int] = []
        procedure_start_point = 0
        for port_description in ports_description:
            procedures_points_table.append(procedure_start_point)
            self.write_code(procedure_start_point, port_description.interrupt_code_on_write)
            procedure_start_point += len(port_description.interrupt_code_on_write)
            procedures_points_table.append(procedure_start_point)
            self.write_code(procedure_start_point, port_description.interrupt_code_on_read)
            procedure_start_point += len(port_description.interrupt_code_on_read)
            procedures_points_table.append(procedure_start_point)
        self.interruption_procedures_points_table_begin = procedure_start_point
        for i in range(0, len(procedures_points_table)):
            self.data_memory[self.interruption_procedures_points_table_begin + i] = procedures_points_table[i]
        self.instruction_pointer = self.interruption_procedures_points_table_begin + len(procedures_points_table)
        self.write_code(self.instruction_pointer, program)
        self.OD_SH_pointer = self.instruction_pointer + len(program)
        self.PRA_SH_pointer = memory_size - 1
        self.instruction_stage_number = 1

    def write_code(self, memory_index: int, code: list[Instruction]):
        for instruction in code:
            self.data_memory[memory_index] = instruction
            memory_index += 1

    def signal_data_memory_write(self, instruction: Instruction):
        sel = instruction.opcode
        arg = instruction.arg
        match sel:
            case Opcode.SUM:
                self.data_memory[self.OD_SH_pointer - 1] += self.data_memory[self.OD_SH_pointer]
            case Opcode.DIFF:
                self.data_memory[self.OD_SH_pointer - 1] -= self.data_memory[self.OD_SH_pointer]
            case Opcode.DIV:
                self.data_memory[self.OD_SH_pointer - 1] /= self.data_memory[self.OD_SH_pointer]
            case Opcode.MUL:
                self.data_memory[self.OD_SH_pointer - 1] *= self.data_memory[self.OD_SH_pointer]
            case Opcode.EQ:
                if self.data_memory[self.OD_SH_pointer - 1] == self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.N_EQ:
                if self.data_memory[self.OD_SH_pointer - 1] != self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.MOD:
                self.data_memory[self.OD_SH_pointer - 1] %= self.data_memory[self.OD_SH_pointer]
            case Opcode.DUP:
                self.data_memory[self.OD_SH_pointer + 1] = self.data_memory[self.OD_SH_pointer]
            case Opcode.PICK:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = self.OD_SH_pointer - self.data_memory[
                            self.OD_SH_pointer]
                    case 2:
                        self.data_memory[self.OD_SH_pointer + 1] = self.data_memory[
                            self.data_memory[self.PRA_SH_pointer - 1]]
            case Opcode.SHIFT_BACK:
                pass
            case Opcode.SHIFT_FORWARD:
                pass
            case Opcode.SWAP:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.OD_SH_pointer]
                    case 2:
                        self.data_memory[self.OD_SH_pointer + 1] = self.data_memory[self.OD_SH_pointer]
                    case 3:
                        self.data_memory[self.OD_SH_pointer] = self.data_memory[self.PRA_SH_pointer]
            case Opcode.PUSH_TO_RET, Opcode.POP_TO_RET:
                self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.OD_SH_pointer]
            case Opcode.REDUCE_OD_SHP_TO_ITS_VALUE:
                pass
            case Opcode.PUSH_0_TO_RET:
                self.data_memory[self.PRA_SH_pointer - 1] = 0
            case Opcode.NUMBER:
                self.data_memory[self.OD_SH_pointer + 1] = arg
            case Opcode.JMP:
                pass
            case Opcode.EXEC_IF:
                pass
            case Opcode.EXEC_COND_JMP:
                pass
            case Opcode.PUSH_TO_OD:
                self.data_memory[self.OD_SH_pointer + 1] = self.data_memory[self.PRA_SH_pointer]
            case Opcode.DUP_RET:
                self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.PRA_SH_pointer]
            case Opcode.INCREMENT_RET:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.PRA_SH_pointer]
                    case 2:
                        self.data_memory[self.PRA_SH_pointer] = self.data_memory[self.PRA_SH_pointer + 1] + 1
            case Opcode.DECREMENT_RET:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.PRA_SH_pointer]
                    case 2:
                        self.data_memory[self.PRA_SH_pointer] = self.data_memory[self.PRA_SH_pointer + 1] - 1
            case Opcode.EXEC_COND_JMP_RET:
                pass
            case Opcode.SHIFT_BACK_RET:
                pass
            case Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.data_memory[self.PRA_SH_pointer - 1] = self.instruction_pointer + 2
            case Opcode.JMP_POP_PRA_SHP:
                pass
            case Opcode.HALT:
                pass
            case Opcode.READ_PORT:
                if self.ports[arg]["ready"]:
                    self.data_memory[self.OD_SH_pointer + 1] = self.ports[arg]["data"]
                pass
            case Opcode.WRITE_PORT:
                pass

    def signal_latch_instruction_pointer(self, sel: Opcode):
        match sel:
            case Opcode.JMP, Opcode.EXEC_IF, Opcode.EXEC_COND_JMP, \
                 Opcode.EXEC_COND_JMP_RET, Opcode.JMP_POP_PRA_SHP, Opcode.HALT:
                pass
            case Opcode.SUM, Opcode.DIFF, Opcode.DIV, \
                 Opcode.MUL, Opcode.EQ, Opcode.N_EQ, \
                 Opcode.MOD, Opcode.DUP, Opcode.SHIFT_BACK, \
                 Opcode.SHIFT_FORWARD, Opcode.PUSH_TO_RET, Opcode.POP_TO_RET, \
                 Opcode.REDUCE_OD_SHP_TO_ITS_VALUE, Opcode.PUSH_0_TO_RET, \
                 Opcode.NUMBER, Opcode.PUSH_TO_OD, Opcode.DUP_RET, \
                 Opcode.SHIFT_BACK_RET, Opcode.PUSH_INC_INC_IP_TO_PRA_SHP, Opcode.READ_PORT, \
                 Opcode.WRITE_PORT:
                self.instruction_pointer += 1
            case Opcode.PICK, Opcode.INCREMENT_RET, Opcode.DECREMENT_RET:
                if self.instruction_stage_number == 2:
                    self.instruction_pointer += 1
            case Opcode.SWAP:
                if self.instruction_stage_number == 3:
                    self.instruction_pointer += 1

    def signal_latch_PRA_SH_pointer(self, sel: Opcode):
        match sel:
            case Opcode.SUM, Opcode.DIFF, Opcode.DIV, \
                 Opcode.MUL, Opcode.EQ, Opcode.N_EQ, Opcode.MOD, \
                 Opcode.DUP, Opcode.SHIFT_BACK, \
                 Opcode.SHIFT_FORWARD, Opcode.REDUCE_OD_SHP_TO_ITS_VALUE, Opcode.NUMBER, \
                 Opcode.JMP, Opcode.EXEC_IF, Opcode.EXEC_COND_JMP, \
                 Opcode.PUSH_TO_OD, Opcode.READ_PORT, Opcode.WRITE_PORT, Opcode.HALT:
                pass
            case Opcode.PICK:
                match self.instruction_stage_number:
                    case 1:
                        self.PRA_SH_pointer -= 1
                    case 2:
                        self.PRA_SH_pointer += 1
            case Opcode.SWAP:
                match self.instruction_stage_number:
                    case 1:
                        self.PRA_SH_pointer -= 1
                    case 2:
                        pass
                    case 3:
                        self.PRA_SH_pointer += 1
            case Opcode.PUSH_0_TO_RET, Opcode.PUSH_TO_RET, Opcode.POP_TO_RET, \
                 Opcode.DUP_RET, Opcode.EXEC_COND_JMP_RET, Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.PRA_SH_pointer -= 1
            case Opcode.INCREMENT_RET, Opcode.DECREMENT_RET:
                match self.instruction_stage_number:
                    case 1:
                        self.PRA_SH_pointer -= 1
                    case 2:
                        self.PRA_SH_pointer += 1
            case Opcode.SHIFT_BACK_RET, Opcode.JMP_POP_PRA_SHP:
                self.PRA_SH_pointer += 1

    def signal_latch_OD_SH_pointer(self, sel: Opcode):
        match sel:
            case Opcode.PUSH_TO_RET, Opcode.PUSH_0_TO_RET, Opcode.JMP, \
                 Opcode.DUP_RET, Opcode.INCREMENT_RET, Opcode.DECREMENT_RET, \
                 Opcode.EXEC_COND_JMP_RET, Opcode.SHIFT_BACK_RET, Opcode.PUSH_INC_INC_IP_TO_PRA_SHP, \
                 Opcode.JMP_POP_PRA_SHP, Opcode.HALT:
                pass
            case Opcode.SUM, Opcode.DIFF, Opcode.DIV, \
                 Opcode.MUL, Opcode.EQ, Opcode.N_EQ, \
                 Opcode.MOD, Opcode.SHIFT_BACK, Opcode.POP_TO_RET, \
                 Opcode.EXEC_IF, Opcode.EXEC_COND_JMP, Opcode.WRITE_PORT:
                self.OD_SH_pointer -= 1
            case Opcode.DUP, Opcode.SHIFT_FORWARD, Opcode.NUMBER, \
                 Opcode.PUSH_TO_OD, Opcode.READ_PORT:
                self.OD_SH_pointer += 1
            case Opcode.PICK:
                match self.instruction_stage_number:
                    case 1:
                        pass
                    case 2:
                        self.OD_SH_pointer += 1
            case Opcode.SWAP:
                match self.instruction_stage_number:
                    case 1:
                        self.OD_SH_pointer -= 1
                    case 2:
                        pass
                    case 3:
                        self.OD_SH_pointer += 1
            case Opcode.REDUCE_OD_SHP_TO_ITS_VALUE:
                self.OD_SH_pointer -= self.data_memory[self.OD_SH_pointer]

    def signal_increment_instruction_stage_number(self):
        self.instruction_stage_number += 1

    def signal_reset_instruction_stage_number(self):
        self.instruction_stage_number = 1

    def signal_latch_port_value(self, sel: Opcode, port_number: int):
        match sel:
            case Opcode.READ_PORT:
                self.ports[port_number]["ready"] = False
            case Opcode.WRITE_PORT:
                self.ports[port_number]["data"] = self.data_memory[self.OD_SH_pointer]
                self.ports[port_number]["ready"] = True


class ControlUnit:
    """Блок управления процессора. Выполняет декодирование инструкций и
    управляет состоянием модели процессора, включая обработку данных (DataPath).

    Согласно варианту, любая инструкция может быть закодирована в одно слово.
    Следовательно, индекс памяти команд эквивалентен номеру инструкции.

    ```text
    +------------------(+1)-------+
    |                             |
    |   +-----+                   |
    +-->|     |     +---------+   |    +---------+
        | MUX |---->| program |---+--->| program |
    +-->|     |     | counter |        | memory  |
    |   +-----+     +---------+        +---------+
    |      ^                               |
    |      | sel_next                      | current instruction
    |      |                               |
    +---------------(select-arg)-----------+
           |                               |      +---------+
           |                               |      |  step   |
           |                               |  +---| counter |
           |                               |  |   +---------+
           |                               v  v        ^
           |                       +-------------+     |
           +-----------------------| instruction |-----+
                                   |   decoder   |
                                   |             |<-------+
                                   +-------------+        |
                                           |              |
                                           | signals      |
                                           v              |
                                     +----------+  zero   |
                                     |          |---------+
                                     | DataPath |
                      input -------->|          |----------> output
                                     +----------+
    ```

    """

    data_path: DataPath = None

    def __init__(self, data_path):
        self.data_path = data_path


    def current_instruction(self):
        return self.data_path.data_memory[self.data_path.instruction_pointer]


    def decode_and_execute_instruction(self):
        """Основной цикл процессора. Декодирует и выполняет инструкцию.

        Обработка инструкции:

        1. Проверить `Opcode`.

        2. Вызвать методы, имитирующие необходимые управляющие сигналы.

        3. Продвинуть модельное время вперёд на один такт (`tick`).

        4. (если необходимо) повторить шаги 2-3.

        5. Перейти к следующей инструкции.

        Обработка функций управления потоком исполнения вынесена в
        `decode_and_execute_control_flow_instruction`.
        """
        instruction = self.current_instruction()

        match instruction.opcode:
            case Opcode.HALT:
                raise StopIteration()
            case Opcode.SUM, Opcode.DIFF, Opcode.DIV, \
                 Opcode.MUL, Opcode.EQ, Opcode.N_EQ, \
                 Opcode.MOD:
                self.data_path.signal_data_memory_write(instruction)

        if self.decode_and_execute_control_flow_instruction(instr, opcode):
            return

        if opcode in {Opcode.RIGHT, Opcode.LEFT}:
            self.data_path.signal_latch_data_addr(opcode.value)
            self.signal_latch_program_counter(sel_next=True)
            self.tick()

        elif opcode in {Opcode.INC, Opcode.DEC, Opcode.INPUT}:
            self.data_path.signal_latch_acc()
            self.tick()

            self.data_path.signal_wr(opcode.value)
            self.signal_latch_program_counter(sel_next=True)
            self.tick()

        elif opcode is Opcode.PRINT:
            self.data_path.signal_latch_acc()
            self.tick()

            self.data_path.signal_output()
            self.signal_latch_program_counter(sel_next=True)
            self.tick()

    def __repr__(self):
        """Вернуть строковое представление состояния процессора."""
        state_repr = "TICK: {:3} PC: {:3} ADDR: {:3} MEM_OUT: {} ACC: {}".format(
            self._tick,
            self.program_counter,
            self.data_path.data_address,
            self.data_path.data_memory[self.data_path.data_address],
            self.data_path.acc,
        )

        instr = self.program[self.program_counter]
        opcode = instr["opcode"]
        instr_repr = str(opcode)

        if "arg" in instr:
            instr_repr += " {}".format(instr["arg"])

        if "term" in instr:
            term = instr["term"]
            instr_repr += "  ('{}'@{}:{})".format(term.symbol, term.line, term.pos)

        return "{} \t{}".format(state_repr, instr_repr)


def simulation(code, input_tokens, data_memory_size, limit):
    """Подготовка модели и запуск симуляции процессора.

    Длительность моделирования ограничена:

    - количеством выполненных инструкций (`limit`);

    - количеством данных ввода (`input_tokens`, если ввод используется), через
      исключение `EOFError`;

    - инструкцией `Halt`, через исключение `StopIteration`.
    """
    data_path = DataPath(data_memory_size, input_tokens)
    control_unit = ControlUnit(code, data_path)
    instr_counter = 0

    logging.debug("%s", control_unit)
    try:
        while instr_counter < limit:
            control_unit.decode_and_execute_instruction()
            instr_counter += 1
            logging.debug("%s", control_unit)
    except EOFError:
        logging.warning("Input buffer is empty!")
    except StopIteration:
        pass

    if instr_counter >= limit:
        logging.warning("Limit exceeded!")
    logging.info("output_buffer: %s", repr("".join(data_path.output_buffer)))
    return "".join(data_path.output_buffer), instr_counter, control_unit.current_tick()


def main(code_file, input_file):
    """Функция запуска модели процессора. Параметры -- имена файлов с машинным
    кодом и с входными данными для симуляции.
    """
    code = read_code(code_file)
    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        input_token = []
        for char in input_text:
            input_token.append(char)

    output, instr_counter, ticks = simulation(
        code,
        input_tokens=input_token,
        data_memory_size=100,
        limit=1000,
    )

    print("".join(output))
    print("instr_counter: ", instr_counter, "ticks:", ticks)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)
