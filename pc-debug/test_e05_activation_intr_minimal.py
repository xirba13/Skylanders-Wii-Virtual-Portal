#!/usr/bin/env python3
"""Static gate for the isolated activation interrupt-IN response."""

from pathlib import Path
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


def section(start: str, end: str) -> str:
    return SOURCE[SOURCE.index(start):SOURCE.index(end)]


def main() -> int:
    disassembly = subprocess.check_output(
        [str(OBJDUMP), "-d", str(ELF)], text=True, errors="replace")
    handler = section("interrupt_transfer_handler(",
                      "static s32 __attribute__((target(\"arm\"), noinline))\ncontrol_transfer_handler")
    response = section("write_activation_response(",
                       "static s32 __attribute__((target(\"arm\"), noinline))\ninterrupt_transfer_handler")
    supervisor = section("supervisor_patch_interrupt_transfer(",
                         "static s32 install_interrupt_transfer_patch")
    checks = []
    checks.append(check("firma IOS57", "HID_INTERRUPT_TRANSFER_HANDLER 0x13659494" in SOURCE and
                        "HANDLER_PROLOGUE" in supervisor,
                        "ioctlv 0x13 -> 0x13659494"))
    checks.append(check("mensaje IN", all(token in handler for token in
                        ("message->command == IOS_IOCTLV",
                         "message->ioctlv.command == IOCTLV_USBV5_INTR_TRANSFER",
                         "message->ioctlv.num_in == 1",
                         "message->ioctlv.num_io == 1")), "un input y un IO"))
    checks.append(check("vectores exactos", "vectors[0].len == 0x40" in handler and
                        "vectors[1].len == 0x20" in handler,
                        "cabecera 64, respuesta 32"))
    checks.append(check("dirección IN", "header_words[2] == 0" in handler,
                        "campo de dirección cero"))
    checks.append(check("estado acotado", all(token in handler for token in
                        ("PORTAL_DEVICE_ID", "portal_resumed",
                         "activation_response_pending")), "respuesta pendiente"))
    checks.append(check("respuesta exacta", all(token in response for token in
                        ("data[0] = 'A';", "data[1] = portal_activated;",
                         "data[2] = 0xff;", "data[3] = 0x77;")), "41 state ff 77"))
    checks.append(check("coherencia y ACK", "os_sync_after_write(data, vectors[1].len);" in response and
                        "return vectors[1].len;" in response, "32 bytes"))
    checks.append(check("consume una vez", "activation_response_pending = 0;" in response,
                        "retira la respuesta"))
    checks.append(check("parche supervisor", all(token in supervisor for token in
                        ("Perms_Read()", "Perms_Write(0xffffffff)",
                         "DCWrite32(HID_INTERRUPT_TRANSFER_HANDLER", "ICInvalidate()",
                         "Perms_Write(permissions)")), "disciplina confirmada"))
    checks.append(check("readback", "!= branch" in supervisor and
                        "interrupt_transfer_patch_result = PATCH_APPLIED" in supervisor,
                        "salto verificado"))
    checks.append(check("símbolos ARM", all(f"<{name}>:" in disassembly for name in
                        ("interrupt_transfer_handler", "supervisor_patch_interrupt_transfer")),
                        "handler y supervisor enlazados"))
    checks.append(check("probe exacta", any(token in PROBE for token in
                        ('PROBE_BUILD "E05-activation-intr-minimal-v22"',
                         'PROBE_BUILD "E05-intr-out-light-minimal-v23"',
                         'PROBE_BUILD "E05c-pending-in-minimal-v24"',
                         'PROBE_BUILD "E05d-idle-status-minimal-v25"',
                         'PROBE_BUILD "E05e-aligned-status-words-v26"',
                         'PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                         'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                         'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                         'PROBE_BUILD "E05j-control-colour-v30"',
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')) and
                        all(token in PROBE for token in
                        ("IOS_IoctlvAsync(fd, 0x13, 1, 1,",
                         'print_hex(NULL, "activation response: ", interrupt_data, 8)')),
                        "lectura IN visible"))
    if any(build in PROBE for build in
           ('PROBE_BUILD "E05f-giants-reset-handshake-v27"',
            'PROBE_BUILD "E05g-real-hid-set-report-v28"',
            'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
            'PROBE_BUILD "E05j-control-colour-v30"',
            'PROBE_BUILD "E06a-open-bootstrap-v31"')):
        ordered = (PROBE.index("before_control_activate") <
                   PROBE.index("before_interrupt_activation_response"))
        detail = "A antes de leer su respuesta"
    else:
        ordered = (PROBE.index("IOS_IoctlvAsync(fd, 0x13") <
                   PROBE.index("IOS_Ioctlv(fd, 0x12"))
        detail = "IN pendiente antes de control"
    checks.append(check("orden probe", ordered, detail))
    checks.append(check("IN conservado", "message->ioctlv.num_in == 1" in handler and
                        "header_words[2] == 0" in handler, "lectura original intacta"))
    print(f"\nE05 activation interrupt gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
