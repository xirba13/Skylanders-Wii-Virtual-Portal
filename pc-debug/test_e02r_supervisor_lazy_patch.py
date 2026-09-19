#!/usr/bin/env python3
"""Local gate for E02r's supervisor-mode lazy handler patch."""

from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "plugin" / "skylanders-hidv5-plugin.elf"
ORIG = ROOT / "plugin" / "skylanders-hidv5-plugin.elf.orig"
SOURCE = ROOT / "plugin" / "source" / "main.c"
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def function(source: str, name: str) -> str:
    match = re.search(rf"{name}\([^)]*\)\n\{{(.*?)\n\}}", source, re.S)
    return match.group(1) if match else ""


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    blob = ELF.read_bytes()
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    supervisor = function(source, "supervisor_patch_getdevicechange")
    lazy = function(source, "install_getdevicechange_patch")
    getversion = function(source, "getversion_handler")
    change = function(source, "getdevicechange_handler")
    checks = []

    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("entrada supervisor", "Swi_CallFunc(supervisor_patch_getdevicechange, 0, 0)" in lazy,
                        "misma SWI usada por IOS_InitSystem"))
    checks.append(check("permisos temporales", all(token in supervisor for token in
                        ("permissions = Perms_Read();", "Perms_Write(0xffffffff);",
                         "Perms_Write(permissions);")),
                        "guarda, eleva y restaura"))
    checks.append(check("parche solo en supervisor", "DCWrite32(HID_GETDEVICECHANGE_HANDLER" in supervisor and
                        "DCWrite32" not in lazy,
                        "ninguna escritura desde el hilo HID"))
    checks.append(check("preimagen/postimagen", all(token in supervisor for token in
                        ("getdevicechange_before", "HANDLER_PROLOGUE", "ICInvalidate()",
                         "getdevicechange_after", "branch")),
                        "lectura, escritura e invalidación privilegiadas"))
    checks.append(check("publicación normal", "publish_diagnostic_snapshot();" in lazy and
                        "publish_diagnostic_snapshot" not in supervisor,
                        "sin llamadas de servicio dentro del callback supervisor"))
    checks.append(check("orden GETVERSION", getversion.index("os_sync_after_write") <
                        getversion.index("install_getdevicechange_patch") <
                        getversion.index("os_message_queue_ack"),
                        "versión, SWI, ACK"))
    checks.append(check("validación GETDEVICECHANGE", all(token in change for token in
                        ("IOCTL_USBV5_GETDEVICECHANGE", "last_length_in == 0",
                         "last_length_io == GETDEVICECHANGE_OUTPUT_SIZE", "result = 1;")),
                        "ioctl 1, entrada 0, salida 0x180"))
    checks.append(check("ReceiveMessage acotado", ("os_message_queue_receive" not in source and
                        "hid_receive" not in source) or
                        ("hid_receive_open_bootstrap" in source and
                         "message->command == IOS_OPEN" in source),
                        "ausente en E02r o bootstrap IOS_OPEN deliberado en E06a"))
    checks.append(check("sin transferencias ajenas", "BULK_TRANSFER" not in source and
                        "ISO_TRANSFER" not in source, "solo HID"))
    checks.append(check("símbolos enlazados", "<supervisor_patch_getdevicechange>:" in disassembly and
                        "<getdevicechange_handler>:" in disassembly,
                        "callback y handler presentes"))

    print(f"[INFO] SHA-256 E02r: {sha256(blob).hexdigest().upper()}")
    print(f"\nE02r local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
