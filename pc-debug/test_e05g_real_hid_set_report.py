#!/usr/bin/env python3
"""Static gate for real Skylanders HID SET_REPORT wValue fields."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    control = SOURCE[SOURCE.index("control_transfer_handler("):
                     SOURCE.index("attachfinish_handler(")]
    checks = []
    checks.append(check("SET_REPORT", "header[8] == 0x21" in control and
                        "header[9] == 0x09" in control, "clase HID host->device"))
    checks.append(check("report type output", "header[10] == 0x02" in control,
                        "byte alto wValue = 2"))
    checks.append(check("report ID comando", "header[11] == data[0]" in control,
                        "byte bajo wValue coincide con R/A"))
    checks.append(check("interfaz cero", "header[12] == 0" in control and
                        "header[13] == 0" in control, "wIndex 0"))
    checks.append(check("rechaza cabecera sintética", "header[10] == 0 &&" not in control,
                        "wValue cero retirado"))
    checks.append(check("probe E05g+", any(build in PROBE for build in
                        ('PROBE_BUILD "E05g-real-hid-set-report-v28"',
                         'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                         'PROBE_BUILD "E05j-control-colour-v30"',
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')),
                        "identificador visible"))
    checks.append(check("probe R real", "control_header[10] = 0x02;" in PROBE and
                        "control_header[11] = 'R';" in PROBE,
                        "wValue R = 0x0252"))
    checks.append(check("probe A real", "control_header[11] = 'A';" in PROBE,
                        "wValue A = 0x0241"))
    checks.append(check("secuencia intacta", all(token in PROBE for token in
                        ("reset response: ", "status inactive: ",
                         "activation response: ", "status active: ",
                         "interrupt_out_data[0] = 'L'")), "E05f completo"))

    passed = sum(checks)
    print(f"\nE05g real-SET_REPORT gate: {passed}/{len(checks)} pruebas correctas")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
