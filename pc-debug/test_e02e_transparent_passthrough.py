#!/usr/bin/env python3
"""Local gate for E02e's transparent two-callsite ABI checkpoint."""

from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "plugin" / "skylanders-hidv5-plugin.elf"
SOURCE = ROOT / "plugin" / "source" / "main.c"


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    blob = ELF.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("dos callsites", all(bytes.fromhex(x) in blob for x in ("13658288", "136582f4")), "solo bucle público"))
    checks.append(check("originales validados", "0xeb0008f7" in source and "0xeb0008dc" in source, "dos BL exactos"))
    checks.append(check("paso directo", "return os_message_queue_receive(queue_id, (u32 *)ret_message, flags);" in source, "sin bucle ni inspección"))
    checks.append(check("hook ARM", 'target("arm")' in source and "hid_receive_passthrough" in source, "ABI ARM"))
    forbidden_text = ("GETVERSION", "GETDEVICECHANGE", "GETDEVPARAMS", "HID_QUEUE_ID", "os_message_queue_ack", "IOCTLV", "pending")
    checks.append(check("sin emulación", all(x not in source for x in forbidden_text), "sin cola, ACK ni IOCTL"))
    forbidden_addr = ("1365a66c", "136590c0", "13659100", "13659c24", "13658fb4", "136589e4", "13658d40", "1365aaec")
    checks.append(check("resto intacto", all(bytes.fromhex(x) not in blob for x in forbidden_addr), "sin stub, trabajadores o handlers"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02e: {digest}")
    print(f"\nE02e local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
