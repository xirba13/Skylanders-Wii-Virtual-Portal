#!/usr/bin/env python3
"""Static gate for the minimal idle Skylanders status response."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    status = SOURCE[SOURCE.index("write_status_response("):
                    SOURCE.index("interrupt_transfer_handler(")]
    intr = SOURCE[SOURCE.index("interrupt_transfer_handler("):
                  SOURCE.index("control_transfer_handler(")]
    checks = []
    aligned = any(build in PROBE for build in
                  ('PROBE_BUILD "E05e-aligned-status-words-v26"',
                   'PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                   'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                   'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                   'PROBE_BUILD "E05j-control-colour-v30"',
                   'PROBE_BUILD "E06a-open-bootstrap-v31"'))
    checks.append(check("mismo handler", "HID_INTERRUPT_TRANSFER_HANDLER 0x13659494" in SOURCE,
                        "sin nuevo punto de parche"))
    checks.append(check("estado exacto", all(token in status for token in
                        ("zero_bytes(data, vectors[1].len);", "data[0] = 'S';",
                         "data[5] = status_counter++;", "data[6] = portal_activated;")),
                        "S, contador y activación") if not aligned else
                        check("estado alineado sucesor", "data_words[0] = 0x53000000;" in status and
                              "data_words[1] =" in status, "S, contador y activación"))
    checks.append(check("figuras vacías", not any(f"data[{i}] =" in status for i in range(1, 5)),
                        "bits de slots permanecen cero"))
    checks.append(check("coherencia", "os_sync_after_write(data, vectors[1].len);" in status and
                        "return vectors[1].len;" in status, "writeback y 32 bytes"))
    checks.append(check("prioridad A", intr.index("activation_response_pending") <
                        intr.index("write_status_response(message)"), "A antes de S"))
    checks.append(check("IN estricto", all(token in intr for token in
                        ("message->ioctlv.num_in == 1", "message->ioctlv.num_io == 1",
                         "header_words[0] == PORTAL_DEVICE_ID", "header_words[2] == 0",
                         "portal_resumed")), "solo portal IN reanudado"))
    checks.append(check("sin puntero pendiente", "pending_interrupt_in" not in SOURCE,
                        "E05d responde cada IN"))
    checks.append(check("contador inicial", "status_counter = 0;" in SOURCE,
                        "secuencia reproducible"))
    checks.append(check("probe E05d+", 'PROBE_BUILD "E05d-idle-status-minimal-v25"' in PROBE or aligned,
                        "identificador visible"))
    checks.append(check("estado inactivo", "status inactive:" in PROBE and
                        "before_interrupt_status_inactive" in PROBE,
                        "S antes de A"))
    checks.append(check("respuesta A", "activation response:" in PROBE and
                        "before_interrupt_activation_response" in PROBE,
                        "respuesta prioritaria tras A"))
    checks.append(check("estado activo", "status active:" in PROBE and
                        "before_interrupt_status_active" in PROBE,
                        "S después de A"))
    checks.append(check("orden probe", PROBE.index("before_interrupt_status_inactive") <
                        PROBE.index("before_control_activate") <
                        PROBE.index("before_interrupt_activation_response") <
                        PROBE.index("before_interrupt_status_active"),
                        "S0 -> A -> respuesta A -> S1"))
    checks.append(check("esperas acotadas", PROBE.count("waited_ms < 1000") >= 3,
                        "ninguna lectura bloquea indefinidamente"))
    print(f"\nE05d idle-status gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
