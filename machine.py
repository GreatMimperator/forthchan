#!/usr/bin/python3
"""Модель процессора, позволяющая выполнить машинный код полученный из программы
на языке Forthchan.

Модель включает в себя три основных компонента:

- `DataPath` -- работа с памятью данных и вводом-выводом.

- `ControlUnit` -- работа с памятью команд и их интерпретация.

- и набор вспомогательных функций: `simulation`, `main`.
"""

import logging
import sys

from isa import Opcode, read_code, Term, Instruction


class Port:
    write_flag: bool = False
    read_flag: bool = False
    reading: bool = False
    writing: bool = False
    data: int = 0
    bit_index_slave: int = 0


class InterruptablePort:
    port: Port
    interrupt_code_on_write: list[Instruction]
    interrupt_code_on_read: list[Instruction]

    def __init__(self, interrupt_code_on_write: list[Instruction], interrupt_code_on_read: list[Instruction]):
        self.port = Port()
        self.interrupt_code_on_write = interrupt_code_on_write
        self.interrupt_code_on_read = interrupt_code_on_read


def signal_convert(input_number: int):
    if input_number == 0:
        return 1
    else:
        return 0


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

    OD_STACK_START: int = None
    "Start of Operational Data Stack"

    OD_SH_pointer: int = None
    "Operational Data Stack Head Pointer - пользовательский стек"

    instruction_stage_number: int = None
    "Instruction Stage Number - счетчик стадий команды"

    ports: list[Port] = []
    "Порты"

    port_communication_register: int = 0
    "Через этот регистр идет общение с портами"

    def __init__(self, memory_size: int, ports_description: list[InterruptablePort], program: list[Instruction]):
        assert memory_size > 0, "Data_memory size should be non-zero"
        self.data_memory_size = memory_size
        self.data_memory = [0] * memory_size
        assert len(ports_description) != 0, "Not enough ports for built-in instructions"
        procedures_points_table: list[int] = []
        procedure_start_point = 0
        for port_description in ports_description:
            procedures_points_table.append(procedure_start_point)
            self.write_code(procedure_start_point, port_description.interrupt_code_on_write)
            procedure_start_point += len(port_description.interrupt_code_on_write)
            procedures_points_table.append(procedure_start_point)
            self.write_code(procedure_start_point, port_description.interrupt_code_on_read)
            procedure_start_point += len(port_description.interrupt_code_on_read)
            self.ports.append(port_description.port)
        self.interruption_procedures_points_table_begin = procedure_start_point
        for i in range(0, len(procedures_points_table)):
            self.data_memory[self.interruption_procedures_points_table_begin + i] = procedures_points_table[i]
        self.instruction_pointer = self.interruption_procedures_points_table_begin + len(procedures_points_table)
        self.write_code(self.instruction_pointer, program)
        self.OD_STACK_START = self.instruction_pointer + len(program)
        self.OD_SH_pointer = self.OD_STACK_START
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
                self.data_memory[self.OD_SH_pointer - 1] //= self.data_memory[self.OD_SH_pointer]
            case Opcode.MUL:
                self.data_memory[self.OD_SH_pointer - 1] *= self.data_memory[self.OD_SH_pointer]
            case Opcode.EQ:
                if self.data_memory[self.OD_SH_pointer - 1] == self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.IS_OVER:
                if self.data_memory[self.OD_SH_pointer - 1] > self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.IS_LOWER:
                if self.data_memory[self.OD_SH_pointer - 1] < self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.EQ_NOT_CONSUMING_RET:
                if self.data_memory[self.PRA_SH_pointer + 1] == self.data_memory[self.PRA_SH_pointer]:
                    self.data_memory[self.PRA_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.PRA_SH_pointer - 1] = -1
            case Opcode.N_EQ:
                if self.data_memory[self.OD_SH_pointer - 1] != self.data_memory[self.OD_SH_pointer]:
                    self.data_memory[self.OD_SH_pointer - 1] = 0
                else:
                    self.data_memory[self.OD_SH_pointer - 1] = -1
            case Opcode.MOD:
                self.data_memory[self.OD_SH_pointer - 1] %= self.data_memory[self.OD_SH_pointer]
            case Opcode.DUP:
                self.data_memory[self.OD_SH_pointer + 1] = self.data_memory[self.OD_SH_pointer]
            case Opcode.PUT:
                wma = self.OD_SH_pointer - self.data_memory[self.OD_SH_pointer] - 2
                self.data_memory[wma] = self.data_memory[self.OD_SH_pointer - 1]
            case Opcode.PICK:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = \
                            self.OD_SH_pointer - self.data_memory[self.OD_SH_pointer] - 1
                    case 2:
                        self.data_memory[self.OD_SH_pointer + 1] = \
                            self.data_memory[self.data_memory[self.PRA_SH_pointer]]
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
                        self.data_memory[self.OD_SH_pointer - 1] = self.data_memory[self.PRA_SH_pointer]
            case Opcode.PUSH_TO_RET | Opcode.POP_TO_RET:
                self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.OD_SH_pointer]
            case Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE:
                pass
            case Opcode.PUSH_m1_TO_RET:
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
                        self.data_memory[self.PRA_SH_pointer + 1] = self.data_memory[self.PRA_SH_pointer] + 1
            case Opcode.DECREMENT_RET:
                match self.instruction_stage_number:
                    case 1:
                        self.data_memory[self.PRA_SH_pointer - 1] = self.data_memory[self.PRA_SH_pointer]
                    case 2:
                        self.data_memory[self.PRA_SH_pointer + 1] = self.data_memory[self.PRA_SH_pointer] - 1
            case Opcode.EXEC_COND_JMP_RET:
                pass
            case Opcode.SHIFT_BACK_RET, Opcode.SHIFT_FORWARD_RET:
                pass
            case Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.data_memory[self.PRA_SH_pointer - 1] = self.instruction_pointer + 2
            case Opcode.JMP_POP_PRA_SHP:
                pass
            case Opcode.HALT:
                pass
            case Opcode.READ_PORT:
                self.data_memory[self.OD_SH_pointer + 1] = self.port_communication_register
            case Opcode.START_READ_PORT | Opcode.START_WRITE_PORT:
                pass
            case Opcode.HAS_PORT_TRANSFERRED:
                self.data_memory[self.OD_SH_pointer + 1] = 0 if not self.ports[arg].reading and not self.ports[arg].writing else -1
            case Opcode.HAS_PORT_WROTE:
                self.data_memory[self.OD_SH_pointer + 1] = 0 if self.ports[arg].write_flag else -1

    def signal_latch_instruction_pointer(self, instruction: Instruction):
        sel = instruction.opcode
        match sel:
            case Opcode.HALT:
                pass
            case Opcode.SUM | Opcode.DIFF | Opcode.DIV | \
                 Opcode.MUL | Opcode.EQ | Opcode.IS_OVER | Opcode.IS_LOWER | Opcode.EQ_NOT_CONSUMING_RET | Opcode.N_EQ | \
                 Opcode.MOD | Opcode.DUP | Opcode.PUT | Opcode.SHIFT_BACK | \
                 Opcode.SHIFT_FORWARD | Opcode.PUSH_TO_RET | Opcode.POP_TO_RET | \
                 Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE | Opcode.PUSH_m1_TO_RET | \
                 Opcode.NUMBER | Opcode.PUSH_TO_OD | Opcode.DUP_RET | \
                 Opcode.SHIFT_BACK_RET | Opcode.SHIFT_FORWARD_RET | Opcode.PUSH_INC_INC_IP_TO_PRA_SHP | Opcode.READ_PORT | \
                 Opcode.START_READ_PORT | Opcode.START_WRITE_PORT | Opcode.HAS_PORT_WROTE | Opcode.HAS_PORT_TRANSFERRED:
                self.instruction_pointer += 1
            case Opcode.PICK | Opcode.INCREMENT_RET | Opcode.DECREMENT_RET:
                if self.instruction_stage_number == 2:
                    self.instruction_pointer += 1
            case Opcode.SWAP:
                if self.instruction_stage_number == 3:
                    self.instruction_pointer += 1
            case Opcode.JMP:
                self.instruction_pointer += instruction.arg
            case Opcode.EXEC_IF:
                self.instruction_pointer += 1 + signal_convert(self.data_memory[self.OD_SH_pointer])
            case Opcode.EXEC_COND_JMP:
                if self.data_memory[self.OD_SH_pointer] == 0:
                    self.instruction_pointer += 1
                else:
                    self.instruction_pointer += 1 + instruction.arg
            case Opcode.EXEC_COND_JMP_RET:
                if self.data_memory[self.PRA_SH_pointer] == 0:
                    self.instruction_pointer += 1
                else:
                    self.instruction_pointer += 1 + instruction.arg
            case Opcode.JMP_POP_PRA_SHP:
                self.instruction_pointer = self.data_memory[self.PRA_SH_pointer]

    def signal_latch_PRA_SH_pointer(self, instruction: Instruction):
        sel = instruction.opcode
        match sel:
            case Opcode.SUM | Opcode.DIFF | Opcode.DIV | \
                 Opcode.MUL | Opcode.EQ | Opcode.IS_OVER | Opcode.IS_LOWER | Opcode.N_EQ | Opcode.MOD | \
                 Opcode.DUP | Opcode.PUT | Opcode.SHIFT_BACK | \
                 Opcode.SHIFT_FORWARD | Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE | Opcode.NUMBER | \
                 Opcode.JMP | Opcode.EXEC_IF | Opcode.EXEC_COND_JMP | \
                 Opcode.PUSH_TO_OD | Opcode.READ_PORT | Opcode.START_READ_PORT | Opcode.START_WRITE_PORT | \
                 Opcode.HAS_PORT_WROTE | Opcode.HAS_PORT_TRANSFERRED | Opcode.HALT:
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
            case Opcode.PUSH_m1_TO_RET | Opcode.PUSH_TO_RET | Opcode.POP_TO_RET | \
                 Opcode.DUP_RET | Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.PRA_SH_pointer -= 1
            case Opcode.INCREMENT_RET | Opcode.DECREMENT_RET:
                match self.instruction_stage_number:
                    case 1:
                        self.PRA_SH_pointer -= 1
                    case 2:
                        self.PRA_SH_pointer += 1
            case Opcode.SHIFT_BACK_RET | Opcode.EXEC_COND_JMP_RET | Opcode.JMP_POP_PRA_SHP:
                self.PRA_SH_pointer += 1
            case Opcode.SHIFT_FORWARD_RET | Opcode.EQ_NOT_CONSUMING_RET:
                self.PRA_SH_pointer -= 1

    def signal_latch_OD_SH_pointer(self, instruction: Instruction):
        sel = instruction.opcode
        match sel:
            case Opcode.PUSH_TO_RET | Opcode.PUSH_m1_TO_RET | Opcode.JMP | \
                 Opcode.DUP_RET | Opcode.INCREMENT_RET | Opcode.DECREMENT_RET | \
                 Opcode.EXEC_COND_JMP_RET | Opcode.SHIFT_BACK_RET | Opcode.SHIFT_FORWARD_RET | Opcode.PUSH_INC_INC_IP_TO_PRA_SHP | \
                 Opcode.JMP_POP_PRA_SHP | Opcode.START_READ_PORT | Opcode.HALT:
                pass
            case Opcode.SUM | Opcode.DIFF | Opcode.DIV | \
                 Opcode.MUL | Opcode.EQ | Opcode.IS_OVER | Opcode.IS_LOWER | Opcode.N_EQ | \
                 Opcode.MOD | Opcode.SHIFT_BACK | Opcode.POP_TO_RET | \
                 Opcode.EXEC_IF | Opcode.EXEC_COND_JMP | Opcode.START_WRITE_PORT:
                self.OD_SH_pointer -= 1
            case Opcode.DUP | Opcode.SHIFT_FORWARD | Opcode.NUMBER | \
                 Opcode.PUSH_TO_OD | Opcode.READ_PORT | Opcode.HAS_PORT_WROTE | Opcode.HAS_PORT_TRANSFERRED:
                self.OD_SH_pointer += 1
            case Opcode.PUT:
                self.OD_SH_pointer -= 2
            case Opcode.PICK:
                match self.instruction_stage_number:
                    case 1:
                        self.OD_SH_pointer -= 1
                    case 2:
                        self.OD_SH_pointer += 1
            case Opcode.SWAP:
                match self.instruction_stage_number:
                    case 1:
                        self.OD_SH_pointer -= 1
                    case 2:
                        self.OD_SH_pointer += 1
                    case 3:
                        pass
            case Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE:
                self.OD_SH_pointer -= self.data_memory[self.OD_SH_pointer] + 1

    def signal_increment_instruction_stage_number(self):
        self.instruction_stage_number += 1

    def signal_reset_instruction_stage_number(self):
        self.instruction_stage_number = 1

    def signal_latch_port(self, instruction: Instruction):
        port_number = instruction.arg
        match instruction.opcode:
            case Opcode.START_READ_PORT:
                self.ports[port_number].reading = True
            case Opcode.START_WRITE_PORT:
                self.ports[port_number].writing = True
            case Opcode.READ_PORT:
                self.ports[port_number].write_flag = False
            case Opcode.HAS_PORT_WROTE | Opcode.HAS_PORT_TRANSFERRED:
                pass

    def signal_port_communication_register(self, instruction: Instruction):
        match instruction.opcode:
            case Opcode.START_READ_PORT | Opcode.READ_PORT | Opcode.HAS_PORT_WROTE | Opcode.HAS_PORT_TRANSFERRED:
                pass
            case Opcode.START_WRITE_PORT:
                self.port_communication_register = self.data_memory[self.OD_SH_pointer]

    def write_into_port(self, port_number, value):
        self.ports[port_number].data = value
        self.ports[port_number].write_flag = True


class MasterSPI:
    data_path: DataPath
    "Data path, от которого нам нужны устройства (порты) и регистр для передачи данных"

    slave_select: int
    "Выбор микросхемы для ввода вывода"

    master_out_slave_in: bool
    "Выход с мастера на ведомый (сигнал, кодирующийся как true = 1, false = 0)"

    master_in_slave_out: bool
    "Выход с ведомого на мастер (сигнал, кодирующийся как true = 1, false = 0)"

    bit_index: int
    "Индекс передаваемого сигнала"

    def __init__(self, data_path: DataPath):
        self.slave_select = 0
        self.bit_index = 0
        self.data_path = data_path

    def tick(self):
        self.tick_rise()
        self.tick_fall()

    def tick_rise(self):
        self.master_out_slave_in = bit_to_signal((self.data_path.port_communication_register >> self.bit_index) % 2)
        self.master_in_slave_out = bit_to_signal((self.data_path.ports[self.slave_select].data >> self.bit_index) % 2)

    def tick_fall(self):
        selected_port = self.data_path.ports[self.slave_select]
        bit_value = 2 ** self.bit_index
        if selected_port.reading:
            port_bit = (selected_port.data >> self.bit_index) % 2
            if port_bit != self.master_out_slave_in:
                if port_bit == 0:
                    self.data_path.port_communication_register += bit_value
                else:
                    self.data_path.port_communication_register -= bit_value
        if selected_port.writing:
            reg_bit = (self.data_path.port_communication_register >> self.bit_index) % 2
            if reg_bit != self.master_in_slave_out:
                if reg_bit != 0:
                    self.data_path.ports[self.slave_select].data += bit_value
                else:
                    self.data_path.ports[self.slave_select].data -= bit_value
        if selected_port.reading or selected_port.writing:
            self.bit_index += 1
            logging.debug(self)
            if self.bit_index == 64:
                self.bit_index = 0
                self.data_path.ports[self.slave_select].reading = False
                if selected_port.writing:
                    self.data_path.ports[self.slave_select].read_flag = True
                self.data_path.ports[self.slave_select].writing = False


    def __repr__(self):
        """Вернуть строковое представление состояния передачи."""
        state_repr = "MOSI: {:2}, MISO: {:2}, SS: {}, bit_index: {}, port_communication_register: {}, SS data: {}, " \
                     "SS reading: {}, SS writing: {}".format(
            1 if self.master_out_slave_in else 0,
            1 if self.master_in_slave_out else 0,
            self.slave_select,
            self.bit_index,
            self.data_path.port_communication_register,
            self.data_path.ports[self.slave_select].data,
            self.data_path.ports[self.slave_select].reading,
            self.data_path.ports[self.slave_select].writing
        )
        return state_repr


class ControlUnit:
    """Блок управления процессора. Выполняет декодирование инструкций и
    управляет состоянием модели процессора, включая обработку данных (DataPath).

    Согласно варианту, любая инструкция может быть закодирована в одно слово.
    Следовательно, индекс памяти команд эквивалентен номеру инструкции."""

    data_path: DataPath

    masterSPI: MasterSPI = None

    is_in_interruption: bool = False

    def __init__(self, data_path: DataPath):
        self.data_path = data_path
        self.masterSPI = MasterSPI(data_path)

    def current_instruction(self):
        return self.data_path.data_memory[self.data_path.instruction_pointer]

    def tick(self):
        self.data_path.signal_increment_instruction_stage_number()

    def ip_latch(self, instruction: Instruction):
        self.data_path.signal_latch_instruction_pointer(instruction)

    def next_tick_execute(self) -> bool:
        """Основной цикл процессора. Декодирует и выполняет тик инструкции
        (возвращает истину если тик был последним в инструкции)"""
        instruction = self.current_instruction()

        is_last_instruction_tick = False
        match instruction.opcode:
            case Opcode.HALT:
                if not self.is_in_interruption:
                    raise StopIteration()
                else:
                    self.data_path.instruction_stage_number = self.data_path.data_memory[self.data_path.PRA_SH_pointer]
                    self.data_path.PRA_SH_pointer += 1
                    self.data_path.instruction_pointer = self.data_path.data_memory[self.data_path.PRA_SH_pointer]
                    self.data_path.PRA_SH_pointer += 1
                    self.is_in_interruption = False
                    logging.debug("Interruption exit!!!")
                    return True
            case Opcode.SUM | Opcode.DIFF | Opcode.DIV | \
                 Opcode.MUL | Opcode.EQ | Opcode.IS_OVER | Opcode.IS_LOWER | Opcode.N_EQ | \
                 Opcode.MOD | Opcode.DUP | Opcode.PUT | \
                 Opcode.NUMBER:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.EQ_NOT_CONSUMING_RET:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.PICK:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_OD_SH_pointer(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                    case 2:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_OD_SH_pointer(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                        self.ip_latch(instruction)
                        is_last_instruction_tick = True
            case Opcode.SHIFT_BACK | Opcode.SHIFT_FORWARD:
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.SWAP:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                        self.data_path.signal_latch_OD_SH_pointer(instruction)
                    case 2:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_OD_SH_pointer(instruction)
                    case 3:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                        self.ip_latch(instruction)
                        is_last_instruction_tick = True
            case Opcode.PUSH_TO_RET:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.POP_TO_RET:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE:
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.PUSH_m1_TO_RET:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.JMP:
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.EXEC_IF | Opcode.EXEC_COND_JMP:
                self.ip_latch(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                is_last_instruction_tick = True
            case Opcode.PUSH_TO_OD:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.DUP_RET:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.INCREMENT_RET | Opcode.DECREMENT_RET:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                    case 2:
                        self.data_path.signal_data_memory_write(instruction)
                        self.data_path.signal_latch_PRA_SH_pointer(instruction)
                        self.ip_latch(instruction)
                        is_last_instruction_tick = True
            case Opcode.EXEC_COND_JMP_RET:
                self.ip_latch(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                is_last_instruction_tick = True
            case Opcode.SHIFT_BACK_RET:
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.SHIFT_FORWARD_RET:
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.JMP_POP_PRA_SHP:
                self.ip_latch(instruction)
                self.data_path.signal_latch_PRA_SH_pointer(instruction)
                is_last_instruction_tick = True
            case Opcode.START_WRITE_PORT:
                self.data_path.signal_latch_port(instruction)
                self.data_path.signal_port_communication_register(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.START_READ_PORT:
                self.data_path.signal_latch_port(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.READ_PORT:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_port(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.HAS_PORT_WROTE:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
            case Opcode.HAS_PORT_TRANSFERRED:
                self.data_path.signal_data_memory_write(instruction)
                self.data_path.signal_latch_OD_SH_pointer(instruction)
                self.ip_latch(instruction)
                is_last_instruction_tick = True
        if is_last_instruction_tick:
            self.data_path.signal_reset_instruction_stage_number()
        else:
            self.tick()
        return is_last_instruction_tick

    def __repr__(self):
        """Вернуть строковое представление состояния процессора."""
        state_repr = "ISN: {:3} IP: {:3} OD_SHP: {:3} PRA_SHP: {:3} els below OD_SHP: {}, els over PRA_SHP: {}".format(
            self.data_path.instruction_stage_number,
            self.data_path.instruction_pointer,
            self.data_path.OD_SH_pointer,
            self.data_path.PRA_SH_pointer,
            " ".join([str(i) for i in
                      self.data_path.data_memory[self.data_path.OD_STACK_START:self.data_path.OD_SH_pointer + 1]]),
            " ".join([str(i) for i in self.data_path.data_memory[self.data_path.PRA_SH_pointer:]]),
        )

        instr: Instruction = self.data_path.data_memory[self.data_path.instruction_pointer]
        instr_repr = instr.opcode

        if instr.arg is not None:
            instr_repr += " {}".format(instr.arg)

        if instr.term is not None:
            term = instr.term
            instr_repr += "  ('{}'@{}:{})".format(term.name, term.line_number, term.line_position)

        return "{} \t{}".format(state_repr, instr_repr)

    def step_in_port_interruption(self, port_number: int, is_write_interruption: bool):
        port_interruption_memory_index = self.data_path.interruption_procedures_points_table_begin + 2 * port_number
        if is_write_interruption:
            handler_start_pc = self.data_path.data_memory[port_interruption_memory_index]
        else:
            handler_start_pc = self.data_path.data_memory[port_interruption_memory_index + 1]
        # tick 1
        self.data_path.PRA_SH_pointer -= 1
        self.data_path.data_memory[self.data_path.PRA_SH_pointer] = self.data_path.instruction_pointer
        self.data_path.instruction_pointer = handler_start_pc
        # tick 2
        self.data_path.PRA_SH_pointer -= 1
        self.data_path.data_memory[self.data_path.PRA_SH_pointer] = self.data_path.instruction_stage_number
        self.data_path.instruction_stage_number = 1


def signal_to_bit(signal: bool) -> int:
    return 1 if signal else 0


def bit_to_signal(bit: int) -> bool:
    match bit:
        case 0:
            return False
        case 1:
            return True
        case _:
            raise Exception("Bit should be 0 or 1")


def simulation(data_memory_size: int,
               ports_description: list[tuple[list[Instruction], list[Instruction]]],
               program: list[Instruction],
               input_tokens: list[tuple[int, int]],
               ticks_limit: int):
    """Подготовка модели и запуск симуляции процессора.

    Длительность моделирования ограничена:
    - количеством выполненных тиков (`ticks_limit`);
    - инструкцией `Halt`, через исключение `StopIteration`.
    """
    data_path = DataPath(data_memory_size,
                         list(map(lambda x: InterruptablePort(x[0], x[1]), ports_description)),
                         program)
    control_unit = ControlUnit(data_path)
    ticks_counter = 0
    # key is instruction number (to interrupt before),
    # only one because it is possible to process only one interruption in one time
    trimmed_input_tokens: dict[int, int] = {}
    for instruction_number, value in input_tokens:
        if instruction_number not in trimmed_input_tokens:
            trimmed_input_tokens[instruction_number] = value

    MAIN_PORT_NUMBER = 0
    logging.debug("%s", control_unit)
    try:
        while ticks_counter < ticks_limit:
            if ticks_counter in trimmed_input_tokens:
                if data_path.ports[MAIN_PORT_NUMBER].writing or data_path.ports[MAIN_PORT_NUMBER].reading:
                    logging.debug("WRITE OF SYMBOL \"%s\" is IGNORED (WRITTEN BUT NOT READ BEFORE)",
                                  chr(trimmed_input_tokens[ticks_counter]))
                elif not control_unit.is_in_interruption:
                    control_unit.is_in_interruption = True
                    data_path.write_into_port(MAIN_PORT_NUMBER, trimmed_input_tokens[ticks_counter])
                    control_unit.step_in_port_interruption(MAIN_PORT_NUMBER, True)
                    ticks_counter += 2  # ticks for port interruption
                    logging.debug("Write interruption!!! %s", control_unit)
                    continue
                else:
                    logging.debug("WRITE OF SYMBOL \"%s\" is IGNORED (IN INTERRUPTION)!!!",
                                  chr(trimmed_input_tokens[ticks_counter]))
            t = control_unit.next_tick_execute()
            control_unit.masterSPI.tick()
            ticks_counter += 1
            if t:
                logging.debug("%s", control_unit)
            if data_path.ports[MAIN_PORT_NUMBER].read_flag:
                char_to_print = chr(data_path.ports[MAIN_PORT_NUMBER].data)
                logging.debug("Printed: %s", char_to_print)
                print(char_to_print, end="")
                data_path.ports[MAIN_PORT_NUMBER].read_flag = False
                control_unit.is_in_interruption = True
                control_unit.step_in_port_interruption(MAIN_PORT_NUMBER, False)  # 1 instruction
                logging.debug("Read interruption!!! %s", control_unit)
                ticks_counter += 1
                continue
    except StopIteration:
        pass

    if ticks_counter >= ticks_limit:
        logging.warning("Limit exceeded!")
    logging.info("ticks count: %s", ticks_counter)
    # logging.info("output_buffer: %s", repr("".join(data_path.output_buffer)))
    # return "".join(data_path.output_buffer), instr_counter, control_unit.current_tick()
    # return "smth"


def main(code_file: str, input_file: str, ports_interruption_handlers_files: list[str]):
    """Функция запуска модели процессора
    input_file - это файл, в котором каждая строчка представляет собой пару из индекса тика,
    перед которым выполняется ввод, и сам вводимый символ"""
    program = read_code(code_file)
    input_tokens: list[tuple[int, int]] = []
    with open(input_file, 'r', encoding="utf-8") as file:
        lines = file.readlines()
        for line in lines:
            sp = line.strip().split(" ")
            assert len(sp) == 2
            instruction_number = int(sp[0])
            key = sp[1]
            input_tokens.append((instruction_number, ord(key)))
    input_tokens = sorted(input_tokens, key=lambda x: x[0])
    ports_description: list[(list[Instruction], list[Instruction])] = []
    for i in range(0, len(ports_interruption_handlers_files), 2):
        output_interruption_code = read_code(ports_interruption_handlers_files[i])
        input_interruption_code = read_code(ports_interruption_handlers_files[i + 1])
        ports_description.append((output_interruption_code, input_interruption_code))

    # output, instr_counter, ticks = \
    simulation(
        1000,
        ports_description,
        program,
        input_tokens,
        100000
    )

    # print("".join(output))
    # print("instr_counter: ", instr_counter, "ticks:", ticks)


if __name__ == "__main__":
    logging.basicConfig(filename="log.log",
                        filemode='a',
                        level=logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) >= 4 and (len(sys.argv) - 3) % 2 == 0, \
        "Wrong arguments: machine.py <code_file> <input_file> " \
        "<emit-port-interruption-handler> <key-port-interruption-handler> " \
        "[<output-port-interruption-handler>, <input-port-interruption-handler]*"
    _, code_file, input_file = sys.argv[:3]
    ports_interruption_handlers_files = sys.argv[3:]
    main(code_file, input_file, ports_interruption_handlers_files)
