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
from enum import Enum

from isa import Opcode, read_code, Term, Instruction


class Port:
    filled_with_device: bool = False
    filled_with_cpu: bool = False
    data: int = 0


class InterruptablePort:
    port: Port
    interrupt_code_on_write: list[Instruction]
    interrupt_code_on_read: list[Instruction]

    def __init__(self, interrupt_code_on_write: list[Instruction], interrupt_code_on_read: list[Instruction]):
        self.port = Port()
        self.interrupt_code_on_write = interrupt_code_on_write
        self.interrupt_code_on_read = interrupt_code_on_read


class LatchInput(str, Enum):
    TOP = "TOP"
    IP_MINUS_TOP = "IP MINUS TOP"
    IP_PLUS_ARG = "IP PLUS ARG"
    IP_INC = "IP INC"
    IP_CONV_SIG_SUM_INC = "IP CONV SIG SUM INC"
    OD_SHP_INC = "OD SHP INC"
    OD_SHP_DEC = "OD SHP DEC"
    OD_SHP_MINUS_TWO = "OD SHP MINUS TWO"
    PRA_SHP_INC = "PRA SHP INC"
    PRA_SHP_DEC = "PRA SHP DEC"
    ALU_OUT = "ALU OUT"
    NEXT = "NEXT OUT"
    PORT_VALUE = "PORT"
    HAS_PORT_FILLED_WITH_DEVICE = "HAS DEVICE FILLED WITH DEVICE"
    HAS_DEVICE_FILLED_WITH_CPU = "HAS DEVICE FILLED WITH CPU"
    FALSE = "FALSE"
    TRUE = "TRUE"
    MA_MINUS_ONE_OUT = "MA MINUS ONE OUT"
    MA_OUT = "MA OUT"
    ISN_INC = "ISN INC"
    ONE = "ONE"
    ARG = "ARG"
    IP_PLUS_TWO = "IP PLUS TWO"
    OD_SHP = "OD SHP"
    PRA_SHP = "PRA SHP"
    OD_SHP_MINUS_TOP_DEC = "OD SHP MINUS TOP DEC"
    OD_SHP_MINUS_TOP_AND_TWO = "OD SHP MINUS TOP AND TWO"
    IP = "IP"
    VDSP_PLUS_ARG = "VDSP PLUS ARG"
    VDSP_PLUS_TOP = "VDSP PLUS TOP"


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
    """Указывает на точку начала перечисления указателей на процедуры обработчиков прерываний
    (формат WRWRWR... для 0, 1, 2... портов).
    До него располагаются сами эти процедуры, обязательно оканчивающиеся HALT-ом"""

    instruction_pointer: int = None
    "Instruction Pointer - Указатель на текущую инструкцию"

    TOP: int = "None"
    "Регистр, хранящий значение по OD SHP"

    NEXT: int = "None"
    "Регистр, хранящий значение по OD SHP - 1"

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

    var_data_start_point: int = None

    class RegsState:
        IP: int
        OD_SHP: int
        PRA_SHP: int
        TOP: int
        NEXT: int

        def save(self, IP: int, OD_SHP: int, PRA_SHP: int, TOP: int, NEXT: int):
            self.IP = IP
            self.OD_SHP = OD_SHP
            self.PRA_SHP = PRA_SHP
            self.TOP = TOP
            self.NEXT = NEXT

    cur_tick_regs_state: RegsState = RegsState()

    def __init__(self, memory_size: int, var_memory_size: int, ports_description: list[InterruptablePort],
                 program: list[Instruction]):
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
        self.var_data_start_point = self.interruption_procedures_points_table_begin + len(procedures_points_table)
        self.instruction_pointer = self.var_data_start_point + var_memory_size
        self.write_code(self.instruction_pointer, program)
        self.OD_STACK_START = self.instruction_pointer + len(program)
        self.OD_SH_pointer = self.OD_STACK_START
        self.PRA_SH_pointer = memory_size - 1
        self.instruction_stage_number = 1
        logging.debug(
            f"{self.interruption_procedures_points_table_begin}, {self.var_data_start_point}, {self.instruction_pointer}, {self.OD_SH_pointer}")

    def write_code(self, memory_index: int, code: list[Instruction]):
        for instruction in code:
            self.data_memory[memory_index] = instruction
            memory_index += 1

    def latch_IP(self, instruction: Instruction, latch_input: LatchInput):
        match latch_input:
            case LatchInput.TOP:
                self.instruction_pointer = self.cur_tick_regs_state.TOP
            case LatchInput.IP_CONV_SIG_SUM_INC:
                top_conv_sig = 1 if self.cur_tick_regs_state.TOP == 0 else 0
                pra_ma_out_conv_sig = 1 if self.data_memory[self.cur_tick_regs_state.PRA_SHP] == 0 else 0
                match instruction.opcode:
                    case Opcode.EXEC_IF:
                        self.instruction_pointer += 1 + top_conv_sig
                    case Opcode.EXEC_COND_JMP:
                        self.instruction_pointer += 1 + (0 if top_conv_sig == 1 else instruction.arg)
                    case Opcode.EXEC_COND_JMP_RET:
                        self.instruction_pointer += 1 + (0 if pra_ma_out_conv_sig == 1 else instruction.arg)
                    case _:
                        raise "fatal"
            case LatchInput.IP_MINUS_TOP:
                self.instruction_pointer -= self.cur_tick_regs_state.TOP
            case LatchInput.IP_PLUS_ARG:
                self.instruction_pointer += instruction.arg
            case LatchInput.IP_INC:
                self.instruction_pointer += 1
            case _:
                raise "fatal"

    def latch_OD_SHP(self, instruction: Instruction, latch_input: LatchInput):
        match latch_input:
            case LatchInput.OD_SHP_INC:
                self.OD_SH_pointer += 1
            case LatchInput.OD_SHP_DEC:
                self.OD_SH_pointer -= 1
            case LatchInput.OD_SHP_MINUS_TWO:
                self.OD_SH_pointer -= 2
            case _:
                raise "fatal"

    def latch_PRA_SHP(self, instruction: Instruction, latch_input: LatchInput):
        match latch_input:
            case LatchInput.PRA_SHP_INC:
                self.PRA_SH_pointer += 1
            case LatchInput.PRA_SHP_DEC:
                self.PRA_SH_pointer -= 1
            case _:
                raise "fatal"
        pass

    def latch_TOP(self, instruction: Instruction, latch_input: LatchInput):
        port_num = instruction.arg
        match latch_input:
            case LatchInput.ALU_OUT:
                match instruction.opcode:
                    case Opcode.SUM:
                        self.TOP = self.cur_tick_regs_state.NEXT + self.cur_tick_regs_state.TOP
                    case Opcode.DIFF:
                        self.TOP = self.cur_tick_regs_state.NEXT - self.cur_tick_regs_state.TOP
                    case Opcode.DIV:
                        self.TOP = self.cur_tick_regs_state.NEXT // self.cur_tick_regs_state.TOP
                    case Opcode.MUL:
                        self.TOP = self.cur_tick_regs_state.NEXT * self.cur_tick_regs_state.TOP
                    case Opcode.MOD:
                        self.TOP = self.cur_tick_regs_state.NEXT % self.cur_tick_regs_state.TOP
                    case Opcode.EQ:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT == self.cur_tick_regs_state.TOP else -1
                    case Opcode.NEQ:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT != self.cur_tick_regs_state.TOP else -1
                    case Opcode.LESS:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT < self.cur_tick_regs_state.TOP else -1
                    case Opcode.GR:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT > self.cur_tick_regs_state.TOP else -1
                    case Opcode.LE:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT <= self.cur_tick_regs_state.TOP else -1
                    case Opcode.GE:
                        self.TOP = 0 if self.cur_tick_regs_state.NEXT >= self.cur_tick_regs_state.TOP else -1
                    case Opcode.SHIFT_BACK:
                        self.TOP = self.cur_tick_regs_state.NEXT
                    case Opcode.EQ_NOT_CONSUMING_RET:
                        match self.instruction_stage_number:
                            case 1:
                                self.TOP = 0 if (self.data_memory[self.cur_tick_regs_state.PRA_SHP + 1] ==
                                                 self.data_memory[self.cur_tick_regs_state.PRA_SHP]) \
                                    else -1
                            case 3:
                                self.TOP = self.data_memory[self.cur_tick_regs_state.OD_SHP]
                            case _:
                                raise "fatal"
                    case _:
                        raise "fatal"
            case LatchInput.HAS_DEVICE_FILLED_WITH_CPU:
                self.TOP = 0 if self.ports[port_num].filled_with_cpu else -1
            case LatchInput.HAS_PORT_FILLED_WITH_DEVICE:
                self.TOP = 0 if self.ports[port_num].filled_with_device else -1
            case LatchInput.NEXT:
                self.TOP = self.cur_tick_regs_state.NEXT
            case LatchInput.MA_OUT:
                match instruction.opcode:
                    case Opcode.PUT | Opcode.PUT_ABSOLUTE:
                        self.TOP = self.data_memory[self.cur_tick_regs_state.OD_SHP]
                    case Opcode.PICK:
                        self.TOP = self.data_memory[self.cur_tick_regs_state.OD_SHP - self.cur_tick_regs_state.TOP - 1]
                    case Opcode.PICK_ABSOLUTE:
                        self.TOP = self.data_memory[self.cur_tick_regs_state.TOP]
                    case Opcode.PUSH_TO_OD | Opcode.POP_TO_OD:
                        self.TOP = self.data_memory[self.cur_tick_regs_state.PRA_SHP]
                    case Opcode.DUP_RET | Opcode.INCREMENT_RET | Opcode.DECREMENT_RET:
                        match self.instruction_stage_number:
                            case 1:
                                self.TOP = self.data_memory[self.cur_tick_regs_state.PRA_SHP]
                            case 3:
                                self.TOP = self.data_memory[self.cur_tick_regs_state.OD_SHP]
                            case _:
                                raise "fatal"
                    case Opcode.JMP_POP_PRA_SHP:
                        match self.instruction_stage_number:
                            case 1:
                                self.TOP = self.data_memory[self.cur_tick_regs_state.PRA_SHP]
                            case 2:
                                self.TOP = self.data_memory[self.cur_tick_regs_state.OD_SHP]
                            case _:
                                raise "fatal"
                    case Opcode.READ_VARDATA:
                        self.TOP = self.data_memory[self.var_data_start_point + instruction.arg]
            case LatchInput.ARG:
                self.TOP = instruction.arg
            case LatchInput.VDSP_PLUS_TOP:
                self.TOP = self.var_data_start_point + self.cur_tick_regs_state.TOP
            case LatchInput.PORT_VALUE:
                self.TOP = self.ports[instruction.arg].data
            case _:
                raise "fatal"

    def latch_NEXT(self, instruction: Instruction, latch_input: LatchInput):
        match latch_input:
            case LatchInput.TOP:
                self.NEXT = self.cur_tick_regs_state.TOP
            case LatchInput.MA_MINUS_ONE_OUT:
                match instruction.opcode:
                    case Opcode.PUT | Opcode.PUT_ABSOLUTE:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.TOP - 1]
                    case Opcode.PUSH_TO_OD | Opcode.POP_TO_OD:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1]
                    case Opcode.EXEC_IF | Opcode.EXEC_COND_JMP:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1 - 1]
                    case Opcode.WRITE_VARDATA | Opcode.WRITE_PORT:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1 - 1]
                    case Opcode.WRITE_VARDATA_USER_LINK:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1]
                    case Opcode.POP_TO_RET:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1]
                    case _:
                        logging.debug(instruction.opcode)
                        raise instruction.opcode
                        # raise "fatal"
            case LatchInput.MA_OUT:
                match instruction.opcode:
                    case Opcode.SUM | Opcode.DIFF | Opcode.DIV | Opcode.MUL | \
                         Opcode.MOD | Opcode.EQ | Opcode.NEQ | Opcode.LESS | \
                         Opcode.GR | Opcode.LE | Opcode.GE:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 2]
                    case Opcode.SHIFT_BACK:
                        self.NEXT = self.data_memory[self.cur_tick_regs_state.OD_SHP - 1]
            case _:
                raise "fatal"

    def latch_memory_data(self, instruction: Instruction, latch_input: LatchInput):
        match latch_input:
            case LatchInput.ARG:
                match instruction.opcode:
                    case Opcode.NUMBER:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = instruction.arg
            case LatchInput.TOP:
                match instruction.opcode:
                    case Opcode.SUM | Opcode.DIFF | Opcode.DIV | Opcode.MUL | \
                         Opcode.MOD | Opcode.EQ | Opcode.NEQ | Opcode.LESS | \
                         Opcode.GR | Opcode.LE | Opcode.GE:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP] = self.cur_tick_regs_state.TOP
                    case Opcode.PICK | Opcode.PICK_ABSOLUTE:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP] = self.cur_tick_regs_state.TOP
                    case Opcode.SWAP:
                        match self.instruction_stage_number:
                            case 1:
                                self.data_memory[self.cur_tick_regs_state.OD_SHP - 1] = self.cur_tick_regs_state.TOP
                            case 2:
                                self.data_memory[self.cur_tick_regs_state.OD_SHP] = self.cur_tick_regs_state.TOP
                    case Opcode.PUSH_TO_RET | Opcode.POP_TO_RET:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP - 1] = self.cur_tick_regs_state.TOP
                    case Opcode.PUSH_TO_OD | Opcode.POP_TO_OD:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP] = self.cur_tick_regs_state.TOP
                    case Opcode.DUP_RET:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP + 1] = self.cur_tick_regs_state.TOP
                    case Opcode.DUP:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = self.cur_tick_regs_state.TOP
                    case Opcode.DUDUP:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = self.cur_tick_regs_state.TOP
                    case Opcode.EQ_NOT_CONSUMING_RET:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP] = self.cur_tick_regs_state.TOP
                    case Opcode.WRITE_VARDATA:
                        self.data_memory[self.var_data_start_point + instruction.arg] = self.cur_tick_regs_state.TOP
                    case Opcode.READ_VARDATA:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = self.cur_tick_regs_state.TOP
                    case _:
                        raise "fatal"
            case LatchInput.NEXT:
                match instruction.opcode:
                    case Opcode.PUT:
                        self.data_memory[
                            self.cur_tick_regs_state.OD_SHP - self.cur_tick_regs_state.TOP - 2] = self.cur_tick_regs_state.NEXT
                    case Opcode.PUT_ABSOLUTE:
                        self.data_memory[self.cur_tick_regs_state.TOP] = self.cur_tick_regs_state.NEXT
                    case Opcode.DUDUP:
                        self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = self.cur_tick_regs_state.NEXT
                    case _:
                        raise "fatal"
            case LatchInput.ALU_OUT:
                match instruction.opcode:
                    case Opcode.INCREMENT_RET:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP] = self.cur_tick_regs_state.TOP + 1
                    case Opcode.DECREMENT_RET:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP] = self.cur_tick_regs_state.TOP - 1
                    case _:
                        raise "fatal"
            case LatchInput.IP_PLUS_TWO:
                match instruction.opcode:
                    case Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                        self.data_memory[self.cur_tick_regs_state.PRA_SHP - 1] = self.cur_tick_regs_state.IP + 2
                    case _:
                        raise "fatal"
            case LatchInput.HAS_DEVICE_FILLED_WITH_CPU:
                self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = 0 if self.ports[
                    instruction.arg].filled_with_cpu else -1
            case LatchInput.HAS_PORT_FILLED_WITH_DEVICE:
                self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = 0 if self.ports[
                    instruction.arg].filled_with_cpu else -1
            case LatchInput.VDSP_PLUS_TOP:
                self.data_memory[
                    self.cur_tick_regs_state.OD_SHP] = self.var_data_start_point + self.cur_tick_regs_state.TOP
            case LatchInput.PORT_VALUE:
                self.data_memory[self.cur_tick_regs_state.OD_SHP + 1] = self.ports[instruction.arg].data
            case _:
                raise "fatal"

    def signal_increment_instruction_stage_number(self):
        self.instruction_stage_number += 1

    def signal_reset_instruction_stage_number(self):
        self.instruction_stage_number = 1

    def latch_port_flags(self, instruction: Instruction, latch_input: LatchInput):
        port_number = instruction.arg
        match instruction.opcode:
            case Opcode.WRITE_PORT:
                match latch_input:
                    case LatchInput.TRUE:
                        self.ports[port_number].filled_with_cpu = True
                    case _:
                        raise "fatal exception"
            case Opcode.READ_PORT:
                match latch_input:
                    case LatchInput.FALSE:
                        self.ports[port_number].filled_with_device = False
                    case _:
                        raise "fatal exception"
            case _:
                raise "fatal exception"

    def latch_port_value(self, instruction: Instruction, latch_input: LatchInput):
        match instruction.opcode:
            case Opcode.WRITE_PORT:
                match latch_input:
                    case LatchInput.TOP:
                        self.ports[instruction.arg].data = self.cur_tick_regs_state.TOP
                    case _:
                        raise "fatal exception"
            case _:
                raise "fatal exception"


class ControlUnit:
    """Блок управления процессора. Выполняет декодирование инструкций и
    управляет состоянием модели процессора, включая обработку данных (DataPath).

    Согласно варианту, любая инструкция может быть закодирована в одно слово.
    Следовательно, индекс памяти команд эквивалентен номеру инструкции."""

    data_path: DataPath

    is_in_interruption: bool = False

    ticks_counter: int = 0

    def __init__(self, data_path: DataPath):
        self.data_path = data_path

    def current_instruction(self):
        return self.data_path.data_memory[self.data_path.instruction_pointer]

    def tick(self):
        self.data_path.signal_increment_instruction_stage_number()

    def next_tick_execute(self) -> bool:
        """Основной цикл процессора. Декодирует и выполняет тик инструкции
        (возвращает истину если тик был последним в инструкции)"""
        instruction = self.current_instruction()
        self.data_path.cur_tick_regs_state.save(
            self.data_path.instruction_pointer,
            self.data_path.OD_SH_pointer,
            self.data_path.PRA_SH_pointer,
            self.data_path.TOP,
            self.data_path.NEXT
        )

        self.ticks_counter += 1

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
            case Opcode.SUM | Opcode.DIFF | Opcode.DIV | Opcode.MUL | \
                 Opcode.MOD | Opcode.EQ | Opcode.NEQ | Opcode.LESS | \
                 Opcode.GR | Opcode.LE | Opcode.GE:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.ALU_OUT)
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.SHIFT_BACK:
                self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                self.data_path.latch_NEXT(instruction, LatchInput.MA_OUT)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.SHIFT_BACK_RET:
                self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_INC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.PUT | Opcode.PUT_ABSOLUTE:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_memory_data(instruction, LatchInput.NEXT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_MINUS_TWO)
                    case 2:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.PICK | Opcode.PICK_ABSOLUTE:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.SWAP:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                        self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.PUSH_TO_RET:
                self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_DEC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.POP_TO_RET:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_DEC)
                        self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                    case 2:
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.PUSH_TO_OD | Opcode.POP_TO_OD:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                        if instruction.opcode == Opcode.POP_TO_OD:
                            self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_INC)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                    case 3:
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.NUMBER:
                self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                self.data_path.latch_memory_data(instruction, LatchInput.ARG)
                self.data_path.latch_TOP(instruction, LatchInput.ARG)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.JMP:
                self.data_path.latch_IP(instruction, LatchInput.IP_PLUS_ARG)
                is_last_instruction_tick = True
            case Opcode.EXEC_IF | Opcode.EXEC_COND_JMP:
                self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                self.data_path.latch_IP(instruction, LatchInput.IP_CONV_SIG_SUM_INC)
                self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                is_last_instruction_tick = True
            case Opcode.EXEC_COND_JMP_RET:
                self.data_path.latch_IP(instruction, LatchInput.IP_CONV_SIG_SUM_INC)
                self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_INC)
                is_last_instruction_tick = True
            case Opcode.DUP_RET:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_INC)
                    case 3:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.DUP:
                self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.DUDUP:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_memory_data(instruction, LatchInput.NEXT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.INCREMENT_RET | Opcode.DECREMENT_RET:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.ALU_OUT)
                    case 3:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.JMP_POP_PRA_SHP:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_INC)
                    case 2:
                        self.data_path.latch_IP(instruction, LatchInput.TOP)
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        is_last_instruction_tick = True
            case Opcode.PUSH_INC_INC_IP_TO_PRA_SHP:
                self.data_path.latch_memory_data(instruction, LatchInput.IP_PLUS_TWO)
                self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_DEC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.EQ_NOT_CONSUMING_RET:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_TOP(instruction, LatchInput.ALU_OUT)
                        self.data_path.latch_PRA_SHP(instruction, LatchInput.PRA_SHP_DEC)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                    case 3:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.READ_VARDATA:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                    case 2:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.WRITE_VARDATA:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_memory_data(instruction, LatchInput.TOP)
                        self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                    case 2:
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.READ_VARDATA_USER_LINK:
                self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.WRITE_VARDATA_USER_LINK:
                match self.data_path.instruction_stage_number:
                    case 1:
                        self.data_path.latch_memory_data(instruction, LatchInput.NEXT)
                        self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_MINUS_TWO)
                    case 2:
                        self.data_path.latch_TOP(instruction, LatchInput.MA_OUT)
                        self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                        self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                        is_last_instruction_tick = True
            case Opcode.SUM_TOP_WITH_VDSP:
                self.data_path.latch_TOP(instruction, LatchInput.VDSP_PLUS_TOP)
                self.data_path.latch_memory_data(instruction, LatchInput.VDSP_PLUS_TOP)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.READ_PORT:
                self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                self.data_path.latch_TOP(instruction, LatchInput.PORT_VALUE)
                self.data_path.latch_memory_data(instruction, LatchInput.PORT_VALUE)
                self.data_path.latch_port_flags(instruction, LatchInput.FALSE)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.WRITE_PORT:
                self.data_path.latch_port_value(instruction, LatchInput.TOP)
                self.data_path.latch_TOP(instruction, LatchInput.NEXT)
                self.data_path.latch_NEXT(instruction, LatchInput.MA_MINUS_ONE_OUT)
                self.data_path.latch_port_flags(instruction, LatchInput.TRUE)
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_DEC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True
            case Opcode.HAS_PORT_FILLED_WITH_CPU | Opcode.HAS_PORT_FILLED_WITH_DEVICE:
                self.data_path.latch_NEXT(instruction, LatchInput.TOP)
                match instruction.opcode:
                    case Opcode.HAS_PORT_FILLED_WITH_CPU:
                        self.data_path.latch_memory_data(instruction, LatchInput.HAS_DEVICE_FILLED_WITH_CPU)
                        self.data_path.latch_TOP(instruction, LatchInput.HAS_DEVICE_FILLED_WITH_CPU)
                    case Opcode.HAS_PORT_FILLED_WITH_DEVICE:
                        self.data_path.latch_memory_data(instruction, LatchInput.HAS_PORT_FILLED_WITH_DEVICE)
                        self.data_path.latch_TOP(instruction, LatchInput.HAS_PORT_FILLED_WITH_DEVICE)
                    case _:
                        raise "fatal exception"
                self.data_path.latch_OD_SHP(instruction, LatchInput.OD_SHP_INC)
                self.data_path.latch_IP(instruction, LatchInput.IP_INC)
                is_last_instruction_tick = True

        if is_last_instruction_tick:
            self.data_path.signal_reset_instruction_stage_number()
        else:
            self.tick()
        return is_last_instruction_tick

    def __repr__(self):
        """Вернуть строковое представление состояния процессора."""
        top = "None"
        next = "None"
        OD_SH_size = self.data_path.OD_SH_pointer - self.data_path.OD_STACK_START
        if OD_SH_size > 0:
            top = self.data_path.TOP
        if OD_SH_size > 1:
            next = self.data_path.NEXT
        mem = self.data_path.data_memory[self.data_path.var_data_start_point: self.data_path.var_data_start_point + 41]
        state_repr = "ticks: {:6} ISN: {:3} IP: {:3} OD_SHP: {:3} PRA_SHP: {:3} TOP: {:4} NEXT: {:4} els below OD_SHP: {}, els over PRA_SHP: {}, VDStartP: {}".format(
            self.ticks_counter,
            self.data_path.instruction_stage_number,
            self.data_path.instruction_pointer,
            self.data_path.OD_SH_pointer,
            self.data_path.PRA_SH_pointer,
            top,
            next,
            " ".join([str(i) for i in
                      self.data_path.data_memory[self.data_path.OD_STACK_START:self.data_path.OD_SH_pointer + 1]]),
            " ".join([str(i) for i in self.data_path.data_memory[self.data_path.PRA_SH_pointer:]]),
            self.data_path.var_data_start_point
        )

        instr: Instruction = self.data_path.data_memory[self.data_path.instruction_pointer]
        instr_repr = instr.opcode

        if instr.arg is not None:
            instr_repr += " {}".format(instr.arg)

        if instr.term is not None:
            term = instr.term
            instr_repr += "  ('{}'@{}:{})".format(term.name, term.line_number, term.line_position)

        return "{} \t{}\t{}".format(state_repr, instr_repr, mem)

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
               var_memory_size: int,
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
                         var_memory_size,
                         list(map(lambda x: InterruptablePort(x[0], x[1]), ports_description)),
                         program)
    control_unit = ControlUnit(data_path)
    # key is instruction number (to interrupt before),
    # only one because it is possible to process only one interruption in one time
    trimmed_input_tokens: dict[int, int] = {}
    for instruction_number, value in input_tokens:
        if instruction_number not in trimmed_input_tokens:
            trimmed_input_tokens[instruction_number] = value

    MAIN_PORT_NUMBER = 0
    logging.debug("%s", control_unit)
    try:
        while control_unit.ticks_counter < ticks_limit:
            if control_unit.ticks_counter in trimmed_input_tokens:
                if not control_unit.is_in_interruption:
                    control_unit.is_in_interruption = True
                    control_unit.data_path.ports[MAIN_PORT_NUMBER].data = trimmed_input_tokens[control_unit.ticks_counter]
                    control_unit.data_path.ports[MAIN_PORT_NUMBER].filled_with_device = True
                    control_unit.step_in_port_interruption(MAIN_PORT_NUMBER, True)
                    control_unit.ticks_counter += 2  # ticks for port interruption
                    logging.debug("Write interruption!!! %s", control_unit)
                    continue
                else:
                    logging.debug("WRITE OF SYMBOL \"%s\" is IGNORED (IN INTERRUPTION)!!!",
                                  chr(trimmed_input_tokens[control_unit.ticks_counter]))
            t = control_unit.next_tick_execute()
            if t:
                logging.debug("%s", control_unit)
            if data_path.ports[MAIN_PORT_NUMBER].filled_with_cpu:
                char_to_print = chr(data_path.ports[MAIN_PORT_NUMBER].data)
                logging.debug("Printed: %s", char_to_print)
                print(char_to_print, end="", flush=True)
                data_path.ports[MAIN_PORT_NUMBER].filled_with_cpu = False
                control_unit.is_in_interruption = True
                control_unit.step_in_port_interruption(MAIN_PORT_NUMBER, False)  # 1 instruction
                logging.debug("Read interruption!!! %s", control_unit)
                control_unit.ticks_counter += 1
                continue
    except StopIteration:
        pass

    if control_unit.ticks_counter >= ticks_limit:
        logging.warning("Limit exceeded!")
    logging.info("ticks count: %s", control_unit.ticks_counter)
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
        100,
        ports_description,
        program,
        input_tokens,
        1000000
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
