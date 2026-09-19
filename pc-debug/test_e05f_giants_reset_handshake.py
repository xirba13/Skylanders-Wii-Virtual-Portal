#!/usr/bin/env python3
"""Static/disassembly gate for the minimal Giants R handshake."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")
ELF = ROOT / "plugin/skylanders-hidv5-plugin.elf.orig"
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    disassembly = subprocess.check_output(
        [str(OBJDUMP), "-d", str(ELF)], text=True, errors="replace"
    ).lower()
    reset = SOURCE[SOURCE.index("write_reset_response("):
                   SOURCE.index("write_status_response(")]
    control = SOURCE[SOURCE.index("control_transfer_handler("):
                     SOURCE.index("attachfinish_handler(")]
    intr = SOURCE[SOURCE.index("interrupt_transfer_handler("):
                  SOURCE.index("control_transfer_handler(")]

    checks = []
    checks.append(check("respuesta Giants", "data_words[0] = 0x52013d00;" in reset,
                        "R 01 3d mediante palabra alineada"))
    checks.append(check("buffer completo", "for (i = 0; i < 8; ++i)" in reset and
                        "data_words[i] = 0;" in reset, "32 bytes inicializados"))
    checks.append(check("control R estricto", "data[0] == 'R'" in control and
                        "reset_response_pending = 1;" in control,
                        "R aceptado solo en el control HID confirmado"))
    checks.append(check("desactiva al reiniciar", "portal_activated = 0;" in control,
                        "estado inicial reproducible"))
    checks.append(check("prioridad interrupt", intr.index("reset_response_pending") <
                        intr.index("activation_response_pending"), "R antes de A y S"))
    checks.append(check("consume una vez", "reset_response_pending = 0;" in reset,
                        "respuesta retirada tras IN"))
    checks.append(check("writeback", "os_sync_after_write((void *)data_words" in reset,
                        "coherencia IOS/PPC"))
    checks.append(check("STR ARM", "<write_reset_response>" in disassembly and
                        "str" in disassembly[disassembly.index("<write_reset_response>"):
                                             disassembly.index("<write_status_response>")],
                        "stores de palabra presentes"))
    checks.append(check("probe E05f+", any(build in PROBE for build in
                        ('PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                         'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                         'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                         'PROBE_BUILD "E05j-control-colour-v30"',
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')),
                        "identificador visible"))
    checks.append(check("secuencia R", all(token in PROBE for token in
                        ("before_control_reset", "reset response: ",
                         "before_interrupt_status_inactive", "before_control_activate")) and
                        PROBE.index("before_control_reset") <
                        PROBE.index("before_interrupt_status_inactive") <
                        PROBE.index("before_control_activate"), "R -> respuesta -> S -> A"))

    passed = sum(checks)
    print(f"\nE05f Giants-reset gate: {passed}/{len(checks)} pruebas correctas")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
