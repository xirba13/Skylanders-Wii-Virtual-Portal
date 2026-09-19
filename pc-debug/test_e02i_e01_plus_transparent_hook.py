#!/usr/bin/env python3
"""Local gate for E02i: proven E01 GETVERSION plus E02e tail branch."""

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
    hook = function(disassembly, "hid_receive_passthrough")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("GETVERSION E01", bytes.fromhex("13658fb4") in blob and "HANDLER_PROLOGUE" in source, "manejador directo conocido"))
    checks.append(check("respuesta v5", "out[1] = 5;" in source and "out[3] = 1;" in source and "result = 0;" in source, "00 05 00 01"))
    checks.append(check("dos callsites E02e", all(bytes.fromhex(x) in blob for x in ("13658288", "136582f4")), "solo bucle público"))
    checks.append(check("paso transparente", "return os_message_queue_receive(queue_id, (u32 *)ret_message, flags);" in source, "una llamada sin inspección"))
    checks.append(check("tail branch sin marco", bool(hook) and "push" not in hook and "pop" not in hook, "sin uso adicional de pila"))
    forbidden = ("GETDEVICECHANGE", "GETDEVPARAMS", "HID_QUEUE_ID", "INTERNAL_MESSAGE_MASK", "pending_device_change", "portal_announced")
    checks.append(check("sin fases posteriores", all(x not in source for x in forbidden), "sin enumeración, guarda ni estado"))
    checks.append(check("dos patchers", "{ patch_getversion_handler, 0 }" in source and "{ patch_hid_public_receive_calls, 0 }" in source, "composición explícita"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02i: {digest}")
    print(f"\nE02i local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
