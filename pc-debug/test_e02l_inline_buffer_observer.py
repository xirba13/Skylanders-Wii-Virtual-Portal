#!/usr/bin/env python3
"""Local gate for E02l's non-acknowledging inline buffer observer."""

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


def function(disassembly: str, name: str) -> str:
    match = re.search(rf"<{name}>:(.*?)(?:\n\n|\Z)", disassembly, re.S)
    return match.group(1) if match else ""


def main() -> int:
    blob = ELF.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    hook = function(disassembly, "hid_receive_observer")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("GETVERSION estable", bytes.fromhex("13658fb4") in blob and
                        "out[1] = 5;" in source and "out[3] = 1;" in source,
                        "00 05 00 01 conservado"))
    checks.append(check("callsites públicos", all(bytes.fromhex(x) in blob for x in
                        ("13658288", "136582f4")), "dos callsites solamente"))
    checks.append(check("marcador E02l", all(token in source for token in
                        ("out[0] = 0xe2;", "out[1] = 0x0c;",
                         "out[2] = 0x01;", "out[3] = 0xa5;")),
                        "E2 0C 01 A5"))
    checks.append(check("forma GETDEVICECHANGE", "message->ioctl.length_in != 0" in source and
                        "message->ioctl.length_io != GETDEVICECHANGE_OUTPUT_SIZE" in source and
                        "#define GETDEVICECHANGE_OUTPUT_SIZE  0x180" in source,
                        "sin entrada, salida 0x180"))
    checks.append(check("puntero IOS seguro", "out_address <= IOS_BUFFER_MIN_ADDRESS" in source and
                        "out_address & (IPC_BUFFER_ALIGNMENT - 1)" in source,
                        "dirección IOS y alineación 32"))
    encoded = ("message->command", "message->ioctl.command",
               "message->ioctl.length_in", "message->ioctl.length_io",
               "message->ioctl.buffer_in", "out_address", "(u32)message")
    checks.append(check("campos codificados", all(field in source for field in encoded),
                        "IPC, ioctl, tamaños y punteros"))
    checks.append(check("caché de salida", "os_sync_after_write(out, 0x20);" in source,
                        "firma visible para PPC"))
    checks.append(check("sin respuesta virtual", "os_message_queue_ack(message, 1)" not in source and
                        "portal_announced" not in source,
                        "observa sin ACK ni estado de portal"))
    checks.append(check("una recepción", source.count("os_message_queue_receive(") == 1 and
                        "for (;;)" not in source, "sin reemplazo ni bucle"))
    saved = re.search(r"push\s+\{([^}]+)\}", hook)
    saved_count = len(saved.group(1).split(",")) if saved else 0
    checks.append(check("marco ARM acotado", bool(hook) and saved_count <= 4,
                        f"registros guardados={saved_count}"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02l: {digest}")
    print(f"\nE02l local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
