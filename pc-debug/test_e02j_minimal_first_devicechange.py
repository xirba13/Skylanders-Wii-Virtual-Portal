#!/usr/bin/env python3
"""Local gate for E02j's single immediate GETDEVICECHANGE response."""

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
    hook = function(disassembly, "hid_receive_first_change")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("GETVERSION E02i", bytes.fromhex("13658fb4") in blob and
                        "out[1] = 5;" in source and "out[3] = 1;" in source,
                        "checkpoint confirmado conservado"))
    checks.append(check("callsites públicos", all(bytes.fromhex(x) in blob for x in
                        ("13658288", "136582f4")), "sin stub ni trabajadores"))
    guard = "(((u32)message & INTERNAL_MESSAGE_MASK) == INTERNAL_MESSAGE_MASK)"
    checks.append(check("guarda interna", guard in source, "antes del helper"))
    checks.append(check("primera respuesta", "portal_announced" in source and
                        "os_message_queue_ack(message, 1)" in source,
                        "estado único y ACK=1"))
    expected_entry = ("out[1] = 31;", "put_be16(out + 2, 0x21);",
                      "put_be16(out + 4, PORTAL_VID);",
                      "put_be16(out + 6, PORTAL_PID);",
                      "put_be16(out + 8, 0x21);", "out[11] = 1;")
    checks.append(check("entrada portal", all(item in source for item in expected_entry),
                        "00 1f 00 21 14 30 01 50 00 21 00 01"))
    checks.append(check("búfer y caché", "length_io != 0x180" in source and
                        "zero_bytes(out, 0x180)" in source and
                        "os_sync_after_write(out, 0x180)" in source,
                        "384 bytes validados, limpiados y sincronizados"))
    checks.append(check("sin bucle", "for (;;)" not in source and
                        source.count("os_message_queue_receive(") == 2,
                        "máximo dos recepciones"))
    forbidden = ("pending_device_change", "HID_QUEUE_ID", "resolved_hid_queue",
                 "GETDEVPARAMS", "IOCTLV", "SUSPEND_RESUME")
    checks.append(check("sin fases posteriores", all(item not in source for item in forbidden),
                        "sin cola persistente ni transferencias"))
    saved = re.search(r"push\s+\{([^}]+)\}", hook)
    saved_count = len(saved.group(1).split(",")) if saved else 0
    checks.append(check("marco ARM acotado", bool(hook) and saved_count <= 4,
                        f"registros guardados={saved_count}"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02j: {digest}")
    print(f"\nE02j local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
