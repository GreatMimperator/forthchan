"""Представление исходного и машинного кода.

Особенности реализации:

- Машинный код сериализуется в список JSON. Один элемент списка -- одна инструкция.
- Индекс списка соответствует:
     - адресу оператора в исходном коде;
     - адресу инструкции в машинном коде.

Пример:

```json
[
    {
        "index": 4,
        "opcode": "jmp",
        "arg": -4,
        "term": [
            4,
            5,
            "loop"
        ]
    },
]
```

где:

- `index` -- номер в машинном коде, необходим для того, чтобы понимать, куда делается условный переход;
- `opcode` -- строка с кодом операции (тип: `Opcode`);
- `arg` -- аргумент инструкции (если требуется);
- `term` -- информация о связанном месте в исходном коде (если есть).
"""

import json
from enum import Enum


class Opcode(str, Enum):
    """Коды инструкций"""

    SUM = "sum"
    DIFF = "diff"
    DIV = "div"
    MUL = "mul"
    EQ = "eq"
    EQ_NOT_CONSUMING_RET = "eq not consuming ret"
    N_EQ = "not eq"
    MOD = "mod"
    DUP = "dup"
    PUT = "put"
    PICK = "pick"
    SHIFT_BACK = "shift back"
    SHIFT_FORWARD = "shift forward"
    SWAP = "swap"
    PUSH_TO_RET = "push to ret"
    POP_TO_RET = "pop to ret"
    REDUCE_OD_SHP_TO_ITS_VALUE_MINUS_ONE = "reduce od shp to its value minus one"
    PUSH_0_TO_RET = "push 0 to ret"
    NUMBER = "number"
    JMP = "jmp"
    EXEC_IF = "exec if"
    EXEC_COND_JMP = "exec cond jmp"
    PUSH_TO_OD = "push to od"
    DUP_RET = "dup ret"
    INCREMENT_RET = "increment ret"
    DECREMENT_RET = "decrement ret"
    EXEC_COND_JMP_RET = "exec cond jmp ret"
    SHIFT_BACK_RET = "shift back ret"
    SHIFT_FORWARD_RET = "shift forward ret"
    PUSH_INC_INC_IP_TO_PRA_SHP = "push inc inc ip to pra shp"
    JMP_POP_PRA_SHP = "jmp pop pra shp"
    HALT = "halt"
    READ_PORT = "read port"
    WRITE_PORT = "write port"

    def __str__(self):
        return str(self.value)


class Term:
    """Описание выражения из исходного текста программы"""

    line_number: int
    "Номер строки"

    line_position: int
    "Позиция начала команды (высокоуровневая, не путать с инструкцией) в строчке"

    name: str
    "Название команды"

    def __init__(self, line_number: int, line_position: int, name: str):
        self.line_number = line_number
        self.line_position = line_position
        self.name = name


class Instruction:
    """Описание инструкции процессора"""

    index: int
    "Индекс инструкции в программе"

    opcode: Opcode
    "Код инструкции"

    arg: int | None
    "Аргумент инструкции, если есть"

    term: Term
    "Описание команды высокоуровневого языка, разложенного в эту (и возможно несколько других) инструкцию"

    def __init__(self, index: int, opcode: Opcode, arg: int | None, term: Term):
        self.index = index
        self.opcode = opcode
        self.arg = arg
        self.term = term

def write_code(filename: str, code: list[Instruction]):
    """Записать код из инструкций в файл."""
    with open(filename, "w", encoding="utf-8") as file:
        code_as_json: list[str] = []
        for instruction in code:
            code_as_json.append(json.dumps(instruction, default=lambda o: o.__dict__))
        file.write("[" + ",\n ".join(code_as_json) + "]")


def read_code(filename: str) -> list[Instruction]:
    """Прочесть машинный код из файла"""
    with open(filename, encoding="utf-8") as file:
        code_json_objects = json.loads(file.read())
    code: list[Instruction] = []
    for instruction_json in code_json_objects:
        index = int(instruction_json["index"])
        opcode = Opcode(instruction_json["opcode"])
        arg = None
        if "arg" in instruction_json:
            arg = int(instruction_json["arg"])
        assert len(instruction_json["term"]) == 3
        term = Term(instruction_json["term"]["line_number"],
                    instruction_json["term"]["line_position"],
                    instruction_json["term"]["name"])
        code.append(Instruction(index, opcode, arg, term))
    return code
