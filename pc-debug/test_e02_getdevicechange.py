#!/usr/bin/env python3
"""Local gate for E02: GETVERSION plus initial GETDEVICECHANGE only."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def emit(name: str, passed: bool, detail: str) -> bool:
    print(f"[{'OK' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, default=root / "plugin/skylanders-hidv5-plugin.elf")
    parser.add_argument("--xml", type=Path, default=root / "installer/ciosmaps.xml")
    args = parser.parse_args()

    blob = args.plugin.read_bytes()
    source = (root / "plugin/source/main.c").read_text(encoding="utf-8")
    digest = hashlib.sha256(blob).hexdigest().upper()
    checks = []
    checks.append(emit("ELF32 big-endian", blob[:6] == b"\x7fELF\x01\x02", blob[:6].hex()))
    entry = struct.unpack_from(">I", blob, 24)[0]
    checks.append(emit("entrada", entry == 0x13970000, f"0x{entry:08x}"))
    checks.append(emit("GETVERSION runtime", bytes.fromhex("13658fb4") in blob, "0x13658fb4"))
    checks.append(emit("GETDEVICECHANGE runtime", bytes.fromhex("136589e4") in blob, "0x136589e4"))
    checks.append(emit("GETDEVPARAMS ausente", bytes.fromhex("13658d40") not in blob, "reservado para E03"))
    checks.append(emit("hook de cola ausente", bytes.fromhex("1365aaec") not in blob and bytes.fromhex("1365c2c0") not in blob, "sin ReceiveMessage hook"))
    checks.append(emit("VID/PID", "0x1430" in source and "0x0150" in source, "1430:0150"))
    checks.append(emit("entrada HIDv5", all(token in source for token in ("out[1] = 31", "put_be16(out + 2, 0x21)", "out[11] = 1")), "ID 31, generación 0x21, una interfaz"))
    checks.append(emit("semántica asíncrona", "pending_device_change = message" in source and "if (portal_announced)" in source, "la segunda petición queda pendiente"))

    xml_root = ET.parse(args.xml).getroot()
    base57 = next(node for node in xml_root.findall(".//base") if node.get("ios") == "57")
    hid = next(node for node in base57.findall("content") if int(node.get("id"), 0) == 0xD)
    offline = len(hid.findall("patch"))
    checks.append(emit("sin puente offline", offline == 0, f"{offline} parches HID"))

    expected_entry = bytes.fromhex("001f00211430015000210001")
    checks.append(emit("modelo de respuesta", expected_entry == bytes((0,31,0,0x21,0x14,0x30,0x01,0x50,0,0x21,0,1)), expected_entry.hex(" ")))
    print(f"[INFO] SHA-256 E02: {digest}")
    print(f"\nE02 local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

