#!/usr/bin/env python3
"""Static gate for one pending interrupt-IN completed by activation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    intr = SOURCE[SOURCE.index("interrupt_transfer_handler("):
                  SOURCE.index("control_transfer_handler(")]
    control = SOURCE[SOURCE.index("control_transfer_handler("):
                     SOURCE.index("attachfinish_handler(")]
    checks = []
    successor = any(token in PROBE for token in
                    ('PROBE_BUILD "E05d-idle-status-minimal-v25"',
                     'PROBE_BUILD "E05e-aligned-status-words-v26"',
                     'PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                     'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                     'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                     'PROBE_BUILD "E05j-control-colour-v30"',
                     'PROBE_BUILD "E06a-open-bootstrap-v31"'))
    checks.append(check("transición explícita", ("static ipcmessage *pending_interrupt_in;" in SOURCE and
                        "!pending_interrupt_in" in intr) or
                        (successor and "write_status_response(message)" in intr),
                        "E05c pendiente o sucesor E05d con estado inmediato"))
    checks.append(check("solo IN válido", all(token in intr for token in
                        ("message->ioctlv.num_in == 1", "message->ioctlv.num_io == 1",
                         "header_words[0] == PORTAL_DEVICE_ID", "header_words[2] == 0",
                         "portal_resumed")), "portal reanudado, dirección IN"))
    checks.append(check("sin ACK prematuro", ("pending_interrupt_in = message;" in intr and
                        "acknowledge = 0;" in intr and "if (message && acknowledge)" in intr) or
                        (successor and "write_status_response(message)" in intr),
                        "espera E05c o sustitución deliberada E05d"))
    checks.append(check("A completa o se encola", all(token in control for token in
                        ("if (pending_interrupt_in)", "pending_interrupt_in = 0;",
                         "write_activation_response(pending)",
                         "os_message_queue_ack(pending")) or
                        (successor and "activation_response_pending = 1;" in control),
                        "respuesta A conservada"))
    checks.append(check("estado inicial limpio", ("pending_interrupt_in = 0;" in
                        SOURCE[SOURCE.index("IOS_InitSystem") - 600:]) or
                        (successor and "status_counter = 0;" in SOURCE), "sin estado heredado"))
    checks.append(check("sin nuevo parche", SOURCE.count("HID_INTERRUPT_TRANSFER_HANDLER 0x13659494") == 1,
                        "reutiliza handler confirmado"))
    checks.append(check("probe E05c+", 'PROBE_BUILD "E05c-pending-in-minimal-v24"' in PROBE or successor,
                        "identificador visible"))
    checks.append(check("submit asíncrono", "IOS_IoctlvAsync(fd, 0x13, 1, 1," in PROBE and
                        "interrupt_callback" in PROBE, "la probe no se bloquea"))
    if successor:
        checks.append(check("estado sucesor", "status inactive:" in PROBE,
                            "E05d reemplaza la espera por S"))
    else:
        checks.append(check("espera pendiente", "usleep(100000);" in PROBE and
                            "after_interrupt_pending_wait done=%d result=%d wait=100ms" in PROBE,
                            "observación antes de A"))
    if successor:
        causal = (PROBE.index("before_interrupt_status_inactive") <
                  PROBE.index("before_control_activate"))
    else:
        causal = (PROBE.index("IOS_IoctlvAsync(fd, 0x13") <
                  PROBE.index("IOS_Ioctlv(fd, 0x12"))
    checks.append(check("orden causal", causal, "IN/estado antes de A"))
    checks.append(check("espera acotada", "while (!interrupt_done && waited_ms < 1000)" in PROBE,
                        "callback máximo 1 s"))
    checks.append(check("respuesta visible", "DCInvalidateRange(interrupt_data" in PROBE and
                        'print_hex(NULL, "activation response: ", interrupt_data, 8)' in PROBE,
                        "ACK y bytes comprobables"))
    print(f"\nE05c pending-IN gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
