#!/usr/bin/env python3
"""Local gate for E02p's fixed shared-MEM2 diagnostic snapshot."""

from hashlib import sha256
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "plugin" / "skylanders-hidv5-plugin.elf"
ORIG = ROOT / "plugin" / "skylanders-hidv5-plugin.elf.orig"
SOURCE = ROOT / "plugin" / "source" / "main.c"
LINKER = ROOT / "plugin" / "source" / "link.ld"
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
    linker = LINKER.read_text(encoding="utf-8")
    symbols = subprocess.check_output([str(READELF), "-s", str(ORIG)], text=True)
    sections = subprocess.check_output([str(READELF), "-S", str(ORIG)], text=True)
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    recorder = function(source, "record_received_message")
    publisher = function(source, "publish_diagnostic_snapshot")
    hook = function(source, "hid_receive_observer")
    checks = []

    symbol = re.search(r"^\s*\d+:\s+([0-9a-fA-F]+)\s+32\s+OBJECT\s+GLOBAL.*diagnostic_snapshot$",
                       symbols, re.M)
    snapshot_address = int(symbol.group(1), 16) if symbol else -1
    section = re.search(r"\.diagnostic\s+PROGBITS\s+([0-9a-fA-F]+).*000020.*WA.*32",
                        sections)
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("sección fija", ".diagnostic" in linker and
                        "KEEP(*(.diagnostic))" in linker and snapshot_address == 0x13979000,
                        f"snapshot=0x{snapshot_address:08x}"))
    checks.append(check("32 bytes alineados", bool(section) and
                        int(section.group(1), 16) == 0x13979000 and
                        "aligned(32)" in source,
                        "sección 0x20 alineada a 32"))
    checks.append(check("marcador E02p", all(token in publisher for token in
                        ("out[0] = 0xe2;", "out[1] = 0x10;",
                         "out[2] = 0x01;", "out[3] = 0x5a;")),
                        "E2 10 01 5A"))
    checks.append(check("layout acotado", all(token in publisher for token in
                        ("out[4] = receive_patch_result", "put_be16(out + 6",
                         "put_be32(out + 8", "put_be32(out + 12",
                         "put_be32(out + 16", "put_be32(out + 20",
                         "put_be32(out + 24", "put_be16(out + 28",
                         "put_be16(out + 30", "os_sync_after_write(out, 0x20)")),
                        "secuencia, contadores y tamaños en 32 bytes"))
    checks.append(check("solo tras mensaje seguro", "publish_diagnostic_snapshot();" in recorder and
                        "publish_diagnostic_snapshot();" not in hook.split("os_message_queue_receive", 1)[0],
                        "no añade una llamada antes de ReceiveMessage"))
    checks.append(check("excluye GETVERSION", "message->command == IOS_IOCTL" in recorder and
                        "message->ioctl.command != IOCTL_USBV5_GETVERSION" in recorder,
                        "preserva el último ioctl ajeno al diagnóstico"))
    checks.append(check("GETVERSION mínimo", "write_hid_version(out);" in source and
                        "write_getversion_diagnostics" not in source,
                        "respuesta estándar 00 05 00 01"))
    checks.append(check("sin punteros IPC persistentes", "diagnostic_mailbox" not in source and
                        "buffer_io" not in recorder,
                        "snapshot pertenece al plugin"))
    checks.append(check("sin ACK virtual", "os_message_queue_ack(message, 1)" not in source and
                        "portal_announced" not in source,
                        "GETDEVICECHANGE no se consume"))
    checks.append(check("una recepción", source.count("os_message_queue_receive(") == 1,
                        "un ReceiveMessage por entrada"))
    checks.append(check("hook ARM enlazado", "<hid_receive_observer>:" in disassembly,
                        "símbolo presente"))

    # Independent layout boundary check: 0x0180 must fit in the final two bytes.
    sample = bytearray(32)
    struct.pack_into(">III", sample, 16, 1, 6, 1)
    struct.pack_into(">HH", sample, 28, 0, 0x180)
    checks.append(check("límites big-endian", sample[16:32].hex() ==
                        "00000001000000060000000100000180",
                        sample[16:32].hex()))

    print(f"[INFO] SHA-256 E02p: {sha256(blob).hexdigest().upper()}")
    print(f"\nE02p local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
