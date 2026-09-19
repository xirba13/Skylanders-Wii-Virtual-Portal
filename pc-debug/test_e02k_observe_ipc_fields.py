#!/usr/bin/env python3
"""Local gate for E02k's read-only public-loop diagnostics."""

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
    checks.append(check("marcador diagnóstico", "out[4] = 0xe2;" in source and
                        "out[5] = 0x0b;" in source and "out[6] = 1;" in source,
                        "E2 0B / esquema 1"))
    fields = ("hook_entries", "safe_messages", "nonversion_messages",
              "last_nonversion_ipc_command", "last_nonversion_ioctl",
              "last_nonversion_length_in", "last_nonversion_length_io",
              "last_nonversion_has_output")
    checks.append(check("campos observados", all(field in source for field in fields),
                        "contador, comando, ioctl, tamaños y salida"))
    checks.append(check("GETVERSION no pisa muestra", "message->ioctl.command != IOCTL_USBV5_GETVERSION" in source,
                        "la segunda lectura conserva el último ioctl no cero"))
    checks.append(check("solo observación", "os_message_queue_ack(message, 1)" not in source and
                        "zero_bytes(out, 0x180)" not in source,
                        "sin respuesta virtual"))
    checks.append(check("una recepción", source.count("os_message_queue_receive(") == 1 and
                        "for (;;)" not in source, "sin reemplazo ni bucle"))
    forbidden = ("pending_device_change", "HID_QUEUE_ID", "GETDEVPARAMS",
                 "IOCTLV", "SUSPEND_RESUME")
    checks.append(check("sin fases posteriores", all(item not in source for item in forbidden),
                        "instrumentación aislada"))
    saved = re.search(r"push\s+\{([^}]+)\}", hook)
    saved_count = len(saved.group(1).split(",")) if saved else 0
    checks.append(check("marco ARM acotado", bool(hook) and saved_count <= 4,
                        f"registros guardados={saved_count}"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02k: {digest}")
    print(f"\nE02k local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
