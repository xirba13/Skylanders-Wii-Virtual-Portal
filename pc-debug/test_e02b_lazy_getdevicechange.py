#!/usr/bin/env python3
"""Local gate for E02b: GETDEVICECHANGE is installed only from GETVERSION."""

from __future__ import annotations

import hashlib
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check(name: str, value: bool, detail: str) -> bool:
    print(f"[{'OK' if value else 'FAIL'}] {name}: {detail}")
    return value


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start)
    return source[start:end]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    plugin = root / "plugin/skylanders-hidv5-plugin.elf"
    source_path = root / "plugin/source/main.c"
    xml_path = root / "installer/ciosmaps.xml"
    blob = plugin.read_bytes()
    source = source_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(blob).hexdigest().upper()
    results = []

    results.append(check("ELF32 big-endian", blob[:6] == b"\x7fELF\x01\x02", blob[:6].hex()))
    entry = struct.unpack_from(">I", blob, 24)[0]
    results.append(check("entrada", entry == 0x13970000, f"0x{entry:08x}"))
    results.append(check("literales E02b", bytes.fromhex("13658fb4") in blob and bytes.fromhex("136589e4") in blob, "GETVERSION + GETDEVICECHANGE"))
    results.append(check("sin etapas posteriores", bytes.fromhex("13658d40") not in blob and bytes.fromhex("1365aaec") not in blob, "sin GETDEVPARAMS ni hook de cola"))

    boot_patch = function_body(source, "static s32 patch_getversion_only", "int main(void)")
    lazy_patch = function_body(source, "static s32 install_getdevicechange_patch", "static s32 __attribute__")
    handler = function_body(source, "enumeration_handler(ipcmessage *message)", "static s32 patch_getversion_only")
    results.append(check("arranque toca solo GETVERSION", "DCWrite32(HID_GETVERSION_HANDLER" in boot_patch and "DCWrite32(HID_GETDEVICECHANGE_HANDLER" not in boot_patch, "sin parche temprano de GETDEVICECHANGE"))
    results.append(check("parche diferido aislado", "DCWrite32(HID_GETDEVICECHANGE_HANDLER" in lazy_patch, "instalador lazy independiente"))
    results.append(check("activación desde GETVERSION", "case IOCTL_USBV5_GETVERSION" in handler and "install_getdevicechange_patch" in handler, "después de preparar version 00 05 00 01"))
    results.append(check("caché invalidada", "ICInvalidate()" in lazy_patch, "tras escribir el salto diferido"))
    results.append(check("semántica asíncrona", "if (portal_announced)" in handler and "pending_device_change = message" in handler, "segunda petición pendiente"))

    xml_root = ET.parse(xml_path).getroot()
    base57 = next(node for node in xml_root.findall(".//base") if node.get("ios") == "57")
    hid = next(node for node in base57.findall("content") if int(node.get("id"), 0) == 0xD)
    results.append(check("sin puente offline", not hid.findall("patch"), "HID original durante arranque"))

    print(f"[INFO] SHA-256 E02b: {digest}")
    print(f"\nE02b local gate: {sum(results)}/{len(results)} pruebas correctas")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

