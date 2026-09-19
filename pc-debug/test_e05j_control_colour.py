#!/usr/bin/env python3
"""Static gate for the minimal core colour SET_REPORT command."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    handler = SOURCE.split("control_transfer_handler(ipcmessage *message)", 1)[1].split(
        "attachfinish_handler(ipcmessage *message)", 1)[0]
    checks = [
        check("build v30+", any(token in PROBE for token in
              ('PROBE_BUILD "E05j-control-colour-v30"',
               'PROBE_BUILD "E06a-open-bootstrap-v31"')),
              "E05j o sucesor inequívoco"),
        check("C aceptado", "data[0] == 'C'" in handler,
              "el control SET_REPORT admite RGB"),
        check("cabecera real", "header[10] == 0x02" in handler and
              "header[11] == data[0]" in handler,
              "wValue 0x0243 se valida como report type/id"),
        check("sin respuesta", "else if (data[0] == 'A')" in handler,
              "C no encola respuesta interrupt-IN"),
        check("resultado 32", "result = vectors[1].len;" in handler,
              "la transferencia completa los 32 bytes"),
        check("probe wValue", "control_header[11] = 'C';" in PROBE,
              "la probe envía 0x0243"),
        check("probe RGB", all(token in PROBE for token in
              ("control_data[1] = 0x10", "control_data[2] = 0x20",
               "control_data[3] = 0x30")), "RGB de prueba explícito"),
        check("orden aislado", PROBE.index("before_control_colour") <
              PROBE.index("before_interrupt_status_inactive"),
              "R/respuesta -> C -> S inactivo"),
    ]
    passed = sum(checks)
    print(f"\nE05j control-colour gate: {passed}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
