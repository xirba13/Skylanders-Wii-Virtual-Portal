#!/usr/bin/env python3
"""Validate the exact hardware-proven GETVERSION-only checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED_SHA256 = "b96c3315c33902c9e43c924759d0e6f5d4190d1a43a9a76474f840c5253a30a5"
GETVERSION_HANDLER = bytes.fromhex("13658fb4")
LATER_HOOKS = {
    "GETDEVICECHANGE handler": bytes.fromhex("136589e4"),
    "GETDEVPARAMS handler": bytes.fromhex("13658d40"),
    "ReceiveMessage veneer": bytes.fromhex("1365aaec"),
    "HID queue ID": bytes.fromhex("1365c2c0"),
}


def report(name: str, passed: bool, detail: str) -> bool:
    print(f"[{'OK' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--xml", type=Path, default=root / "installer/ciosmaps.xml")
    args = parser.parse_args()

    blob = args.plugin.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    checks = []
    checks.append(report("hash exacto", digest == EXPECTED_SHA256, digest.upper()))
    checks.append(report("ELF32 big-endian", blob[:6] == b"\x7fELF\x01\x02", blob[:6].hex()))
    entry = struct.unpack_from(">I", blob, 24)[0] if len(blob) >= 28 else 0
    checks.append(report("entrada del plugin", entry == 0x13970000, f"0x{entry:08x}"))
    checks.append(report("parche GETVERSION presente", GETVERSION_HANDLER in blob, "literal 0x13658fb4"))
    for name, marker in LATER_HOOKS.items():
        checks.append(report(f"{name} ausente", marker not in blob, "no pertenece a este checkpoint"))

    xml_root = ET.parse(args.xml).getroot()
    base57 = next(node for node in xml_root.findall(".//base") if node.get("ios") == "57")
    hid = next(node for node in base57.findall("content") if int(node.get("id"), 0) == 0xD)
    offline_count = len(hid.findall("patch"))
    checks.append(report("HID sin puente offline", offline_count == 0, f"{offline_count} parches"))

    passed = sum(checks)
    print(f"\nGETVERSION checkpoint: {passed}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

