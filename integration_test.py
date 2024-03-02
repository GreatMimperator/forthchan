import logging
import os
import subprocess
import tempfile

import pytest


@pytest.mark.golden_test("golden/*.yml")
def test_translator_and_machine(golden, caplog):
    caplog.set_level(logging.DEBUG)

    with tempfile.TemporaryDirectory() as tmpdirname:
        print(tmpdirname)
        source = os.path.join(tmpdirname, "source.forthchan")
        input_stream = os.path.join(tmpdirname, "input.txt")
        target = os.path.join(tmpdirname, "target.o")
        read_interruption_handler = os.path.join(tmpdirname, "read_interruption_handler.o")
        write_interruption_handler = os.path.join(tmpdirname, "write_interruption_handler.o")

        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])
        with open(input_stream, "w", encoding="utf-8") as file:
            file.write(golden["in_stdin"])
        with open(read_interruption_handler, "w", encoding="utf-8") as file:
            file.write(golden["read_interruption_handler"])
        with open(write_interruption_handler, "w", encoding="utf-8") as file:
            file.write(golden["write_interruption_handler"])

        stdout = subprocess.check_output(f"python translator.py {source} {target}", shell=True).decode()
        stdout += "============================================================\n"
        stdout += subprocess.check_output(
            f"python machine.py {target} {input_stream} {write_interruption_handler} {read_interruption_handler}",
            shell=True,
        ).decode()

        with open(target, encoding="utf-8") as file:
            code = file.read()
        logs = os.path.join("log.log")
        with open(logs, encoding="utf-8") as file:
            logs = file.read()

        assert code == golden.out["out_code"]
        assert stdout.strip() == golden.out["out_stdout"].strip()
        assert logs.strip() == golden.out["out_log"].strip(), "Failed LOG"
