#!/usr/bin/env python3
"""Local gate for E02q's lazy direct GETDEVICECHANGE handler."""

from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "plugin" / "skylanders-hidv5-plugin.elf"
ORIG = ROOT / "plugin" / "skylanders-hidv5-plugin.elf.orig"
SOURCE = ROOT / "plugin" / "source" / "main.c"
READELF = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-readelf.exe")
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def function(source: str, name: str) -> str:
    match = re.search(rf"{name}\([^)]*\)\n\{{(.*?)\n\}}", source, re.S)
    return match.group(1) if match else ""


def main() -> int:
    blob = ELF.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    symbols = subprocess.check_output([str(READELF), "-s", str(ORIG)], text=True)
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    startup = function(source, "patch_getversion_handler")
    lazy = function(source, "install_getdevicechange_patch")
    getversion = function(source, "getversion_handler")
    change = function(source, "getdevicechange_handler")
    publish = function(source, "publish_diagnostic_snapshot")
    checks = []

    symbol = re.search(r"^\s*\d+:\s+([0-9a-fA-F]+)\s+32\s+OBJECT\s+GLOBAL.*diagnostic_snapshot$",
                       symbols, re.M)
    address = int(symbol.group(1), 16) if symbol else -1
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("snapshot fija", address == 0x13979000,
                        f"0x{address:08x}"))
    checks.append(check("arranque solo GETVERSION",
                        "DCWrite32(HID_GETVERSION_HANDLER" in startup and
                        "HID_GETDEVICECHANGE_HANDLER" not in startup,
                        "sin parche temprano de change"))
    checks.append(check("activación tras GETVERSION",
                        "install_getdevicechange_patch();" in getversion and
                        getversion.index("os_sync_after_write") <
                        getversion.index("install_getdevicechange_patch"),
                        "HID ya abierto y versión preparada"))
    checks.append(check("preimagen y postimagen", all(token in lazy for token in
                        ("getdevicechange_before", "HANDLER_PROLOGUE",
                         "DCWrite32(HID_GETDEVICECHANGE_HANDLER",
                         "ICInvalidate()", "getdevicechange_after", "branch")),
                        "verificación runtime completa"))
    checks.append(check("salto directo ARM", "return 0xea000000" in source,
                        "B, no BL"))
    checks.append(check("validación HIDv5", all(token in change for token in
                        ("message->command == IOS_IOCTL",
                         "message->ioctl.command == IOCTL_USBV5_GETDEVICECHANGE",
                         "last_length_in == 0",
                         "last_length_io == GETDEVICECHANGE_OUTPUT_SIZE")),
                        "ioctl 1, input 0, output 0x180"))
    entry_tokens = ("out[1] = 31;", "put_be16(out + 2, 0x21)",
                    "put_be16(out + 4, PORTAL_VID)",
                    "put_be16(out + 6, PORTAL_PID)",
                    "put_be16(out + 8, 0x21)", "out[11] = 1;")
    checks.append(check("entrada virtual", all(token in change for token in entry_tokens),
                        "id 31, VID 1430, PID 0150"))
    checks.append(check("ACK único", "os_message_queue_ack(message, result)" in change and
                        "result = 1;" in change and "pending_device_change" not in source,
                        "solo primera respuesta de diagnóstico"))
    checks.append(check("telemetría E02q", all(token in publish for token in
                        ("out[1] = 0x11;", "getdevicechange_patch_result",
                         "getdevicechange_entries", "getdevicechange_valid_requests",
                         "getdevicechange_before", "getdevicechange_after",
                         "getdevicechange_target", "last_length_in", "last_length_io")),
                        "estado, ejecución y longitudes"))
    checks.append(check("sin hook ReceiveMessage", "hid_receive" not in source and
                        "os_message_queue_receive" not in source,
                        "ruta E02p retirada"))
    checks.append(check("sin etapas posteriores", "GETDEVPARAMS" not in source and
                        "IOCTLV" not in source and "slot00" not in source,
                        "solo GETVERSION + GETDEVICECHANGE"))
    checks.append(check("handlers ARM enlazados", "<getversion_handler>:" in disassembly and
                        "<getdevicechange_handler>:" in disassembly,
                        "dos destinos presentes"))

    print(f"[INFO] SHA-256 E02q: {sha256(blob).hexdigest().upper()}")
    print(f"\nE02q local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
