#!/usr/bin/env python3
"""Local gate for E02f enumeration with the stock internal-message guard."""

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
    checks.append(check("callsites E02e", all(bytes.fromhex(x) in blob for x in ("13658288", "136582f4")), "dos saltos hardware-safe"))
    checks.append(check("stub y trabajadores intactos", all(bytes.fromhex(x) not in blob for x in ("1365a66c", "136590c0", "13659100", "13659c24")), "sin colas internas"))
    guard = "if (((u32)message & INTERNAL_MESSAGE_MASK) == INTERNAL_MESSAGE_MASK)"
    checks.append(check("guarda 0xFF", guard in source and "#define INTERNAL_MESSAGE_MASK        0xff000000" in source, "idéntica al bucle stock"))
    message_assignment = source.index("message = *ret_message;")
    guard_position = source.index(guard)
    handler_position = source.index("if (!handle_enumeration(message))")
    checks.append(check("orden seguro", message_assignment < guard_position < handler_position, "guarda antes de desreferenciar en handler"))
    checks.append(check("GETVERSION", "put_be32(out, 0x00050001)" in source and "os_message_queue_ack(message, 0)" in source, "00050001 / result 0"))
    checks.append(check("GETDEVICECHANGE", "os_message_queue_ack(message, 1)" in source and "pending_device_change = message" in source, "primero inmediato, segundo pendiente"))
    checks.append(check("entrada portal", all(x in source for x in ("PORTAL_VID 0x1430", "PORTAL_PID 0x0150", "out[1] = 31")), "12 bytes HIDv5"))
    checks.append(check("sin fases posteriores", "GETDEVPARAMS" not in source and "IOCTLV" not in source, "solo enumeración"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02f: {digest}")
    print(f"\nE02f local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
