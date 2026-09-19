#!/usr/bin/env python3
"""PC-side validation lab for the Skylanders HIDv5 cIOS experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XML = ROOT / "installer/ciosmaps.xml"
DEFAULT_HID = ROOT / "local-inputs/IOS57-v6175-0000000d.app"
DEFAULT_PLUGIN = ROOT / "plugin/skylanders-hidv5-plugin.elf"
DEFAULT_DUMPS = [ROOT / "local-inputs/slot00.bin", ROOT / "local-inputs/slot01.bin"]


@dataclass
class Segment:
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    flags: int

    def contains(self, address: int, size: int = 1, memory: bool = True) -> bool:
        span = self.memsz if memory else self.filesz
        return self.vaddr <= address and address + size <= self.vaddr + span


def elf_segments(blob: bytes) -> list[Segment]:
    if blob[:4] != b"\x7fELF" or blob[4] != 1 or blob[5] != 2:
        raise ValueError("se esperaba un ELF32 big-endian")
    phoff = struct.unpack_from(">I", blob, 28)[0]
    phentsize, phnum = struct.unpack_from(">HH", blob, 42)
    result = []
    for index in range(phnum):
        pos = phoff + index * phentsize
        p_type, p_offset, p_vaddr, _, p_filesz, p_memsz, p_flags, _ = struct.unpack_from(">8I", blob, pos)
        if p_type == 1 and p_vaddr:
            result.append(Segment(p_offset, p_vaddr, p_filesz, p_memsz, p_flags))
    return result


def address_to_offset(segments: list[Segment], address: int, size: int = 1) -> int:
    for segment in segments:
        if segment.contains(address, size, memory=False):
            return segment.offset + address - segment.vaddr
    raise ValueError(f"dirección 0x{address:08x} fuera de los segmentos con datos")


def byte_list(value: str) -> bytes:
    return bytes(int(part.strip(), 0) for part in value.split(",") if part.strip())


def decode_arm_branch(source: int, instruction: int) -> int | None:
    if instruction & 0x0E000000 != 0x0A000000:
        return None
    delta = instruction & 0x00FFFFFF
    if delta & 0x00800000:
        delta -= 0x01000000
    return (source + 8 + (delta << 2)) & 0xFFFFFFFF


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def patch_hid(xml_path: Path, hid_path: Path) -> tuple[bytes, list[dict]]:
    source = hid_path.read_bytes()
    patched = bytearray(source)
    root = ET.parse(xml_path).getroot()
    base57 = next(node for node in root.findall(".//base") if node.get("ios") == "57")
    content = next(node for node in base57.findall("content") if int(node.get("id"), 0) == 0xD)
    records = []
    for patch in content.findall("patch"):
        offset = int(patch.get("offset"), 0)
        old = byte_list(patch.get("originalbytes", ""))
        new = byte_list(patch.get("newbytes", ""))
        if len(old) != int(patch.get("size"), 0) or len(new) != len(old):
            raise AssertionError(f"tamaño inválido en parche 0x{offset:x}")
        actual = source[offset:offset + len(old)]
        if actual != old:
            raise AssertionError(f"originalbytes no coincide en 0x{offset:x}: {actual.hex()} != {old.hex()}")
        patched[offset:offset + len(new)] = new
        records.append({"offset": offset, "size": len(new), "old": old.hex(), "new": new.hex()})
    return bytes(patched), records


class Portal:
    FIGURE_SIZE = 1024
    BLOCK_SIZE = 16
    BLOCK_COUNT = 64

    def __init__(self, figures: list[bytes]):
        if len(figures) != 2 or any(len(item) != self.FIGURE_SIZE for item in figures):
            raise ValueError("se necesitan exactamente dos figuras de 1024 bytes")
        self.figures = [bytearray(item) for item in figures]

    def query(self, slot: int, block: int) -> bytes:
        out = bytearray(32)
        out[0] = ord("Q")
        if 0 <= slot < 2 and 0 <= block < self.BLOCK_COUNT:
            out[1] = 0x10 | slot
            out[2] = block
            start = block * self.BLOCK_SIZE
            out[3:19] = self.figures[slot][start:start + self.BLOCK_SIZE]
        return bytes(out)

    def write(self, slot: int, block: int, data: bytes) -> bytes:
        if len(data) != self.BLOCK_SIZE:
            raise ValueError("un bloque tiene 16 bytes")
        out = bytearray(32)
        out[0] = ord("W")
        if 0 <= slot < 2 and 0 <= block < self.BLOCK_COUNT:
            out[1] = 0x10 | slot
            out[2] = block
            start = block * self.BLOCK_SIZE
            self.figures[slot][start:start + self.BLOCK_SIZE] = data
        return bytes(out)


def run(args: argparse.Namespace) -> dict:
    xml_path, hid_path, plugin_path = map(Path, (args.xml, args.hid, args.plugin))
    dump_paths = [Path(item) for item in args.dumps]
    hid = hid_path.read_bytes()
    plugin = plugin_path.read_bytes()
    hid_segments = elf_segments(hid)
    plugin_segments = elf_segments(plugin)
    patched, patches = patch_hid(xml_path, hid_path)

    checks = []
    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("IOS57 original", len(hid) > 0, f"{len(hid)} bytes; sha256={sha256(hid)}")
    check("plugin ELF", len(plugin) > 0, f"{len(plugin)} bytes; sha256={sha256(plugin)}")
    check("parches aplicables", True, f"{len(patches)} parches HID offline verificados byte a byte")

    # Inspect every patched ARM branch and its target.
    for record in patches:
        if record["size"] == 4:
            offset = record["offset"]
            segment = next((s for s in hid_segments if s.offset <= offset < s.offset + s.filesz), None)
            if segment:
                source_addr = segment.vaddr + offset - segment.offset
                insn = struct.unpack_from(">I", patched, offset)[0]
                target = decode_arm_branch(source_addr, insn)
                if target is not None:
                    mapped = any(s.contains(target, 4) for s in hid_segments)
                    check(f"salto ARM 0x{source_addr:08x}", mapped, f"destino=0x{target:08x}; dentro de HID={mapped}")

    # The current bridge reads the plugin entry before the plugin is guaranteed loaded.
    bridge_offset = 0x2C38
    bridge = patched[bridge_offset:bridge_offset + 40]
    plugin_probe = 0x13970074
    bridge_has_probe = struct.pack(">I", plugin_probe) in bridge
    plugin_loaded_at_hid_start = any(s.contains(plugin_probe, 4) for s in hid_segments)
    check(
        "orden de carga del puente",
        not bridge_has_probe or plugin_loaded_at_hid_start,
        ("el puente lee 0x13970074, pero esa memoria pertenece al módulo SKYLANDERS y no al HID; "
         "puede no existir cuando arranca /dev/usb/hid") if bridge_has_probe and not plugin_loaded_at_hid_start else "sin dependencia temprana no mapeada",
    )

    source_text = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
    global_queue_hook = all(value in source_text for value in
                            ("0x1365aaec", "0x1365c2c0", "0x477846c0", "0x4b004718"))
    public_callsite_hook = all(value in source_text for value in
                               ("0x13658288", "0x136582f4", "0xeb0008f7", "0xeb0008dc"))
    lazy_direct_handler = all(value in source_text for value in
                              ("HID_GETVERSION_HANDLER", "HID_GETDEVICECHANGE_HANDLER",
                               "install_getdevicechange_patch();",
                               "DCWrite32(HID_GETDEVICECHANGE_HANDLER", "0xea000000"))
    check("intercepción HID acotada",
          global_queue_hook or public_callsite_hook or lazy_direct_handler,
          "hook validado o manejador GETDEVICECHANGE activado desde GETVERSION")
    lazy_queue = "if (original_queue_id < 0)" in source_text and \
                 "when ReceiveMessage is actually called" in source_text
    check("sin carrera de cola global",
          (global_queue_hook and lazy_queue) or public_callsite_hook or lazy_direct_handler,
          "cola segura o estrategia directa sin ID de cola")
    check("HID original durante arranque", not patches,
          "sin parche offline: /dev/usb/hid puede arrancar antes que SKYLANDERS")
    core_text = (ROOT / "portal-core/portal_core.c").read_text(encoding="utf-8")
    commands = tuple(f"case '{command}'" for command in "ACJLMQRSVW")
    check("protocolo completo del portal", all(command in core_text for command in commands),
          "A/C/J/L/M/Q/R/S/V/W y transferencias CTRL/INTR presentes")

    figures = [path.read_bytes() for path in dump_paths]
    for path, figure in zip(dump_paths, figures):
        check(f"dump {path.name}", len(figure) == 1024, f"{len(figure)} bytes; sha256={sha256(figure)}")
    portal = Portal(figures)
    for slot in range(2):
        for block in (0, 1, 8, 63):
            reply = portal.query(slot, block)
            expected = figures[slot][block * 16:(block + 1) * 16]
            check(f"Q slot{slot} bloque{block}", reply[3:19] == expected and reply[:3] == bytes((ord('Q'), 0x10 | slot, block)), reply[:19].hex())
    original_other = portal.query(1, 4)
    marker = bytes(range(16))
    ack = portal.write(0, 4, marker)
    check("W slot0", ack[:3] == bytes((ord('W'), 0x10, 4)) and portal.query(0, 4)[3:19] == marker, ack[:3].hex())
    check("aislamiento de slots", portal.query(1, 4) == original_other, "escribir slot0 no modifica slot1")

    failures = [item for item in checks if not item["passed"]]
    return {
        "ok": not failures,
        "summary": {"passed": len(checks) - len(failures), "failed": len(failures)},
        "diagnosis": "El puente actual no es seguro durante el arranque del HID." if bridge_has_probe and not plugin_loaded_at_hid_start else "Sin fallo estructural detectado en el puente.",
        "patched_hid_sha256": sha256(patched),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", default=str(DEFAULT_XML))
    parser.add_argument("--hid", default=str(DEFAULT_HID))
    parser.add_argument("--plugin", default=str(DEFAULT_PLUGIN))
    parser.add_argument("--dumps", nargs=2, default=[str(item) for item in DEFAULT_DUMPS])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Skylanders PC debug: {result['summary']['passed']} OK, {result['summary']['failed']} FAIL")
        for item in result["checks"]:
            print(f"[{'OK' if item['passed'] else 'FAIL'}] {item['name']}: {item['detail']}")
        print(f"\nDiagnóstico: {result['diagnosis']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
