"""Run checks with exact commands and a consistent UTF-8 evidence log."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("task")
args = parser.parse_args()
if not re.fullmatch(r"TAI-\d{3}", args.task):
    parser.error("expected TAI-XXX")
root = Path(__file__).resolve().parents[1]
commands = [
    [sys.executable, "--version"],
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "ruff", "format", "--check", "."],
    [sys.executable, "-m", "mypy"],
    [sys.executable, "-m", "pytest", "-q"],
]
with (root / "docs" / "reports" / f"{args.task}-checks.txt").open("w", encoding="utf-8") as log:
    for command in commands:
        header = "$ " + subprocess.list2cmdline(command) + "\n"
        log.write(header)
        print(header, end="", flush=True)
        result = subprocess.run(
            command,
            cwd=root / "backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log.write(result.stdout)
        log.write(f"EXIT CODE: {result.returncode}\n")
        log.flush()
        print(result.stdout, end="", flush=True)
        if result.returncode:
            sys.exit(result.returncode)
