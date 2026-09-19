#!/usr/bin/env python3
"""Verify the IOS57 v6175 GETVERSION and public ReceiveMessage signatures."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from skylanders_lab import address_to_offset, elf_segments

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HID = ROOT / "local-inputs" / "IOS57-v6175-0000000d.app"

SIGNATURES = (
    ("GETVERSION", 0x13658FB4, 0xE1A0C00D),
    ("RECEIVE_FIRST", 0x13658288, 0xEB0008F7),
    ("RECEIVE_NEXT", 0x136582F4, 0xEB0008DC),
)


def read_u32(blob: bytes, segments, address: int) -> int:
    offset = address_to_offset(segments, address, 4)
    return struct.unpack_from(">I", blob, offset)[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba firmas estáticas del HID de IOS57 v6175.")
    parser.add_argument("hid", nargs="?", type=Path, default=DEFAULT_HID,
                        help="ruta al contenido 0000000d.app extraído")
    args = parser.parse_args()

    if not args.hid.is_file():
        parser.error(f"no se encuentra {args.hid}; pasa la ruta como argumento")

    blob = args.hid.read_bytes()
    segments = elf_segments(blob)
    matches = []
    print(f"Fichero: {args.hid} ({len(blob)} bytes)")
    for label, address, expected in SIGNATURES:
        actual = read_u32(blob, segments, address)
        match = actual == expected
        matches.append(match)
        print(f"{label:13} @ 0x{address:08X}: "
              f"esperado=0x{expected:08X} real=0x{actual:08X} "
              f"coincide={match}")

    if all(matches):
        print("PASS: las tres firmas originales coinciden byte a byte.")
        return 0
    print("FAIL: al menos una firma no coincide; no se debe desplegar el hook.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
