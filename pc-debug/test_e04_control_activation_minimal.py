#!/usr/bin/env python3
"""Static gate for the isolated HIDv5 control activation candidate."""

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
    handler = section("control_transfer_handler(",
                      "static s32 __attribute__((target(\"arm\"), noinline))\nattachfinish_handler")
    supervisor = section("supervisor_patch_control_transfer(",
                         "static s32 install_control_transfer_patch")
    checks = []
    checks.append(check("firma IOS57", "HID_CONTROL_TRANSFER_HANDLER 0x13659300" in SOURCE and
                        "HANDLER_PROLOGUE" in supervisor,
                        "ioctlv 0x12 -> 0x13659300 con prólogo verificado"))
    checks.append(check("mensaje IOCTLV", all(token in handler for token in
                        ("message->command == IOS_IOCTLV",
                         "message->ioctlv.command == IOCTLV_USBV5_CTRL_TRANSFER",
                         "message->ioctlv.num_in == 2",
                         "message->ioctlv.num_io == 0")),
                        "dos vectores de entrada, ninguno de salida"))
    checks.append(check("vectores exactos", all(token in handler for token in
                        ("vectors[0].len == 0x40", "vectors[1].len == 0x20",
                         "vectors[0].data", "vectors[1].data")),
                        "cabecera 64 y comando 32 bytes"))
    checks.append(check("portal reanudado", "portal_resumed" in handler and
                        "header_words[0] == PORTAL_DEVICE_ID" in handler,
                        "ID virtual y estado resume obligatorios"))
    checks.append(check("petición HID", all(token in handler for token in
                        ("header[8] == 0x21", "header[9] == 0x09",
                         "data[0] == 'A'", "data[1] <= 1")),
                        "SET_REPORT de activación acotado"))
    checks.append(check("ACK transferido", "result = vectors[1].len;" in handler,
                        "devuelve 32 bytes transferidos"))
    checks.append(check("parche supervisor", all(token in supervisor for token in
                        ("Perms_Read()", "Perms_Write(0xffffffff)",
                         "DCWrite32(HID_CONTROL_TRANSFER_HANDLER", "ICInvalidate()",
                         "Perms_Write(permissions)")), "disciplina E04b conservada"))
    checks.append(check("readback", "!= branch" in supervisor and
                        "control_transfer_patch_result = PATCH_APPLIED" in supervisor,
                        "salto verificado tras escribir"))
    checks.append(check("símbolos ARM", all(f"<{name}>:" in disassembly for name in
                        ("control_transfer_handler", "supervisor_patch_control_transfer")),
                        "handler y supervisor enlazados"))
    checks.append(check("probe exacta", any(token in PROBE for token in
                        ('PROBE_BUILD "E04-control-activation-minimal-v21"',
                         'PROBE_BUILD "E05-activation-intr-minimal-v22"',
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
                        ("IOS_Ioctlv(fd, 0x12, 2, 0, control_vectors)",
                         "control_data[0] = 'A';", "control_data[1] = 1;")),
                        "activa mediante dos vectores"))
    checks.append(check("orden probe", PROBE.index("IOS_Ioctl(fd, 0x10") <
                        PROBE.index("IOS_Ioctlv(fd, 0x12"),
                        "resume antes de control"))
    checks.append(check("control conservado", "activation_response_pending = 1;" in handler,
                        "la activación prepara una respuesta"))
    print(f"\nE04 control activation gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
