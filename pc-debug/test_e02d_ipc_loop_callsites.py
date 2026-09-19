#!/usr/bin/env python3
"""Local structural gate for E02d's two public IPC-loop call-site hooks."""

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
    checks.append(check("primer callsite", bytes.fromhex("13658288") in blob and "0xeb0008f7" in source, "BL público inicial"))
    checks.append(check("segundo callsite", bytes.fromhex("136582f4") in blob and "0xeb0008dc" in source, "BL público siguiente"))
    checks.append(check("stub compartido intacto", bytes.fromhex("1365a66c") not in blob, "no se escribe el syscall compartido"))
    worker_sites = ("136590c0", "13659100", "13659c24")
    checks.append(check("trabajadores intactos", all(bytes.fromhex(x) not in blob for x in worker_sites), "sin parches en tres colas internas"))
    checks.append(check("parches directos ARM", source.count("make_arm_branch(") == 3 and source.count("DCWrite32(HID_RECEIVE_CALL_") == 2, "dos BL al hook ARM"))
    checks.append(check("filtro de cola", "queue_id != resolved_hid_queue" in source and "HID_QUEUE_ID                 0x1365c2c0" in source, "solo cola pública HID"))
    checks.append(check("GETVERSION", "put_be32(out, 0x00050001)" in source and "os_message_queue_ack(message, 0)" in source, "00050001 / result 0"))
    checks.append(check("GETDEVICECHANGE", "os_message_queue_ack(message, 1)" in source and "pending_device_change = message" in source, "primero inmediato, segundo pendiente"))
    forbidden = ("13658fb4", "136589e4", "13658d40", "1365aaec")
    checks.append(check("handlers intactos", all(bytes.fromhex(x) not in blob for x in forbidden), "sin handler directo ni veneer Thumb"))
    checks.append(check("alcance", "GETDEVPARAMS" not in source and "IOCTLV" not in source, "sin fases posteriores"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02d: {digest}")
    print(f"\nE02d local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
