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
        "index": 0,
        "opcode": "jz",
        "arg": 5,
        "term": [
            1,
            5,
            "]"
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
from collections import namedtuple
from enum import Enum


class Opcode(str, Enum):
    """
    Opcode для инструкций.
    """

    SUM = "sum"
    DIFF = "diff"
    DIV = "div"
    MUL = "mul"
    EQ = "eq"
    N_EQ = "not eq"
    MOD = "mod"
    DUP = "dup"
    PICK = "pick"
    SHIFT_BACK = "shift back"
    SHIFT_FORWARD = "shift forward"
    SWAP = "swap"
    PUSH_TO_RET = "push to ret"
    POP_TO_RET = "pop to ret"
    REDUCE_OD_SHP_TO_ITS_VALUE = "reduce od shp to its value"
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
    PUSH_INC_INC_IP_TO_PRA_SHP = "push inc inc ip to pra shp"
    JMP_POP_PRA_SHP = "jmp pop pra shp"
    HALT = "halt"
    READ_PORT = "read port"
    WRITE_PORT = "write port"

    def __str__(self):
        """Переопределение стандартного поведения `__str__` для `Enum`: вместо
        `Opcode.HALT` вернуть `halt`.
        """
        return str(self.value)


class Term(namedtuple("Term", "line pos symbol")):
    """Описание выражения из исходного текста программы.

    Сделано через класс, чтобы был docstring.
    """


class Instruction:
    index: int
    opcode: str
    arg: int
    term: Term

    def __init__(self, index: int, opcode: str, arg: int, term: Term):
        self.index = index
        self.opcode = opcode
        self.arg = arg
        self.term = term


def write_code(filename, code):
    """Записать машинный код в файл."""
    with open(filename, "w", encoding="utf-8") as file:
        # Почему не: `file.write(json.dumps(code, indent=4))`?
        # Чтобы одна инструкция была на одну строку.
        buf = []
        for instr in code:
            buf.append(json.dumps(instr))
        file.write("[" + ",\n ".join(buf) + "]")


def read_code(filename):
    """Прочесть машинный код из файла.

    Так как в файле хранятся не только простейшие типы (`Opcode`, `Term`), мы
    также выполняем конвертацию в объекты классов вручную (возможно, следует
    переписать через `JSONDecoder`, но это скорее усложнит код).

    """
    with open(filename, encoding="utf-8") as file:
        code_json_objects = json.loads(file.read())
    code = []
    for instruction_json in code_json_objects:
        index = int(instruction_json["index"])
        opcode = Opcode(instruction_json["opcode"])
        arg = None
        if "arg" in instruction_json:
            arg = int(instruction_json["arg"])
        assert len(instruction_json["term"]) == 3
        term = Term(instruction_json["term"][0], instruction_json["term"][1], instruction_json["term"][2])
        code.append(Instruction(index, opcode, arg, term))
    return code
