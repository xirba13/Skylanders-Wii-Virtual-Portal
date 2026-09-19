#!/usr/bin/env python3
"""Local structural gate for E02c's IOS57 ARM ReceiveMessage hook."""

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
    checks.append(check("stub ARM real", bytes.fromhex("1365a66c") in blob, "0x1365a66c"))
    queue_literal = bytes.fromhex("1365c2c0") in blob
    queue_split = bytes.fromhex("1365c000") in blob and "HID_QUEUE_ID                 0x1365c2c0" in source
    checks.append(check("cola HID", queue_literal or queue_split, "0x1365c2c0 directo o base 0x1365c000 + 0x2c0"))
    checks.append(check("trampolín ARM", bytes.fromhex("e51ff004") in blob, "ldr pc,[pc,#-4]"))
    checks.append(check("valida syscall", "RECEIVE_SYSCALL_ORIGINAL" in source and "ARM_RETURN_ORIGINAL" in source, "valida ambas instrucciones"))
    checks.append(check("filtro exacto", "queue_id != resolved_hid_queue" in source, "otras colas pasan al syscall propio"))
    checks.append(check("GETVERSION", "put_be32(out, 0x00050001)" in source and "os_message_queue_ack(message, 0)" in source, "00050001 / result 0"))
    checks.append(check("GETDEVICECHANGE", "os_message_queue_ack(message, 1)" in source and "pending_device_change = message" in source, "anuncio inicial y segundo pendiente"))
    checks.append(check("entrada portal", all(token in source for token in ("PORTAL_VID 0x1430", "PORTAL_PID 0x0150", "out[1] = 31")), "VID/PID y clase HID"))
    forbidden = ("13658fb4", "136589e4", "13658d40", "1365aaec")
    checks.append(check("manejadores intactos", all(bytes.fromhex(x) not in blob for x in forbidden), "sin handlers ni veneer Thumb"))
    checks.append(check("alcance E02c", "GETDEVPARAMS" not in source and "IOCTLV" not in source, "sin endpoints ni fases posteriores"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02c: {digest}")
    print(f"\nE02c local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
