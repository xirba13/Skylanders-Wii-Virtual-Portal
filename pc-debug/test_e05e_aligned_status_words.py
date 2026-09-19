#!/usr/bin/env python3
"""Static/disassembly gate for E05e aligned status construction."""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")
ELF = ROOT / "plugin/skylanders-hidv5-plugin.elf.orig"
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    status = SOURCE[SOURCE.index("write_status_response("):
                    SOURCE.index("interrupt_transfer_handler(")]
    disassembly = subprocess.check_output(
        [str(OBJDUMP), "-d", str(ELF)], text=True, errors="replace")
    start = disassembly.index("<write_status_response>:")
    end = disassembly.index("<interrupt_transfer_handler>:")
    machine = disassembly[start:end]
    checks = []
    checks.append(check("puntero alineado", "volatile u32 *data_words" in status,
                        "salida tratada como palabras"))
    checks.append(check("ocho words", "for (i = 0; i < 8; ++i)" in status and
                        "data_words[i] = 0;" in status, "32 bytes inicializados"))
    checks.append(check("word S", "data_words[0] = 0x53000000;" in status,
                        "53 00 00 00"))
    checks.append(check("word dinámico", "data_words[1] = (counter << 16) |" in status and
                        "((u32)portal_activated << 8)" in status,
                        "00 counter active 00"))
    checks.append(check("sin stores byte C", all(token not in status for token in
                        ("data[0] = 'S'", "data[5] =", "data[6] =")),
                        "retirada construcción E05d"))
    checks.append(check("sin STRB a salida",
                        re.search(r"strb\s+[^,]+,\s*\[r0", machine.lower()) is None,
                        "el único STRB permitido actualiza el contador global"))
    checks.append(check("STR máquina", "str" in machine.lower(),
                        "escrituras ARM presentes"))
    checks.append(check("writeback", "os_sync_after_write(data, vectors[1].len);" in status,
                        "coherencia conservada"))
    checks.append(check("probe E05e+", any(build in PROBE for build in
                        ('PROBE_BUILD "E05e-aligned-status-words-v26"',
                         'PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                         'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                         'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                         'PROBE_BUILD "E05j-control-colour-v30"',
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')),
                        "identificador visible"))
    checks.append(check("misma secuencia", all(token in PROBE for token in
                        ("status inactive:", "activation response:", "status active:",
                         "interrupt_out_light")), "solo cambia el plugin"))
    print(f"\nE05e aligned-status gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
