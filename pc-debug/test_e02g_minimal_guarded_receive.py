#!/usr/bin/env python3
"""Local gate for E02g's minimal framed receive checkpoint."""

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


def main() -> int:
    blob = ELF.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    match = re.search(r"<hid_receive_guarded_passthrough>:(.*?)(?:\n\n|\Z)", disassembly, re.S)
    hook = match.group(1) if match else ""
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("dos callsites", all(bytes.fromhex(x) in blob for x in ("13658288", "136582f4")), "mismos que E02e"))
    checks.append(check("una recepción", source.count("os_message_queue_receive(") == 1, "sin bucle"))
    checks.append(check("guarda compilada", "ff000000" in hook.lower(), "máscara visible en ARM"))
    checks.append(check("marco mínimo", "push" in hook and "pop" in hook, "llamada no terminal con prólogo/epílogo"))
    forbidden = ("GETVERSION", "GETDEVICECHANGE", "GETDEVPARAMS", "os_message_queue_ack", "HID_QUEUE_ID", "pending")
    checks.append(check("sin emulación/estado", all(x not in source for x in forbidden), "solo observación"))
    checks.append(check("salida intacta", "*ret_message =" not in source, "no sustituye mensajes"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02g: {digest}")
    print(f"\nE02g local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
