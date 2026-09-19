#!/usr/bin/env python3
"""Static gate for the isolated interrupt-OUT light command."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    start = SOURCE.index("interrupt_transfer_handler(")
    end = SOURCE.index("control_transfer_handler(")
    handler = SOURCE[start:end]
    response = SOURCE[SOURCE.index("write_activation_response("):start]
    checks = []
    checks.append(check("mismo handler confirmado", "HID_INTERRUPT_TRANSFER_HANDLER 0x13659494" in SOURCE,
                        "sin nuevo punto de parche"))
    checks.append(check("mensaje OUT", "message->ioctlv.num_in == 2" in handler and
                        "message->ioctlv.num_io == 0" in handler,
                        "dos vectores input"))
    checks.append(check("vectores exactos", "vectors[0].len == 0x40" in handler and
                        "vectors[1].len == 0x20" in handler, "64 + 32 bytes"))
    checks.append(check("dirección OUT", "header_words[2] != 0" in handler,
                        "selector no nulo"))
    checks.append(check("validación portal", "PORTAL_DEVICE_ID" in handler and
                        "portal_resumed" in handler, "ID y resume"))
    checks.append(check("comando acotado", "data[0] == 'L'" in handler and
                        "data[1] <= 2" in handler, "solo luz y posición válida"))
    checks.append(check("ACK transferido", "result = vectors[1].len;" in handler,
                        "32 bytes"))
    checks.append(check("IN conservado", "activation_response_pending" in handler and
                        "data[2] = 0xff;" in response, "respuesta A intacta"))
    checks.append(check("probe exacta",
                        any(token in PROBE for token in
                            ('PROBE_BUILD "E05j-control-colour-v30"',
                             'PROBE_BUILD "E06a-open-bootstrap-v31"')) and
                        all(token in PROBE for token in
                            ("IOS_Ioctlv(fd, 0x13, 2, 0,",
                             "interrupt_out_data[0] = 'L';",
                             "interrupt_out_data[4] = 0x30;")),
                        "L 00 10 20 30"))
    checks.append(check("orden probe", PROBE.index("IOS_IoctlvAsync(fd, 0x13, 1, 1") <
                        PROBE.index("IOS_Ioctlv(fd, 0x13, 2, 0"),
                        "IN confirmado antes de OUT"))
    checks.append(check("sin respuesta nueva", "light_response_pending" not in SOURCE,
                        "L no encola respuesta"))
    print(f"\nE05 interrupt OUT light gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
