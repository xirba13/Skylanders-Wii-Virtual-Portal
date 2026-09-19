#!/usr/bin/env python3
"""Local gate for E02o's plugin-owned, second-descriptor diagnostics."""

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


def function(source: str, name: str) -> str:
    match = re.search(rf"{name}\([^)]*\)\n\{{(.*?)\n\}}", source, re.S)
    return match.group(1) if match else ""


def main() -> int:
    blob = ELF.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    recorder = function(source, "record_received_message")
    hook = function(source, "hid_receive_observer")
    diagnostics = function(source, "write_getversion_diagnostics")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("sin puntero persistente", "diagnostic_mailbox" not in source and
                        "diagnostic_mailbox = out" not in source,
                        "ningún buffer PPC se conserva entre IPC"))
    checks.append(check("marcador E02o", all(token in diagnostics for token in
                        ("out[4] = 0xe2;", "out[5] = 0x0f;", "out[6] = 0x01;")),
                        "E2 0F 01"))
    fields = ("receive_hook_entries", "receive_safe_messages", "nonversion_messages",
              "last_nonversion_ipc_command", "last_nonversion_ioctl",
              "last_nonversion_length_in", "last_nonversion_length_io")
    checks.append(check("estado propio del plugin", all(f"static volatile" in source[:source.index(field) + len(field)]
                        for field in fields) and all(field in diagnostics for field in fields),
                        "contadores publicados desde memoria del plugin"))
    checks.append(check("layout acotado", all(token in diagnostics for token in
                        ("put_be32(out + 8", "put_be32(out + 12", "put_be32(out + 16",
                         "put_be32(out + 20", "put_be32(out + 24", "put_be16(out + 28",
                         "put_be16(out + 30", "os_sync_after_write(out, 0x20)")),
                        "32 bytes exactos"))
    checks.append(check("excluye GETVERSION", "message->command == IOS_IOCTL" in recorder and
                        "message->ioctl.command != IOCTL_USBV5_GETVERSION" in recorder,
                        "el GETVERSION diagnóstico no pisa el último mensaje observado"))
    checks.append(check("captura no-GETVERSION", all(token in recorder for token in
                        ("nonversion_messages++;", "message->command",
                         "message->ioctl.command", "message->ioctl.length_in",
                         "message->ioctl.length_io")),
                        "IPC, ioctl y tamaños"))
    checks.append(check("guarda interna conservada", "INTERNAL_MESSAGE_MASK" in hook and
                        "record_received_message(message);" in hook,
                        "no desreferencia mensajes internos"))
    checks.append(check("sin tocar change buffer", "message->ioctl.buffer_io" not in recorder and
                        "GETDEVICECHANGE_OUTPUT_SIZE" not in recorder,
                        "solo observa metadatos"))
    checks.append(check("sin ACK virtual", "os_message_queue_ack(message, 1)" not in source and
                        "portal_announced" not in source,
                        "no consume GETDEVICECHANGE"))
    checks.append(check("una recepción", source.count("os_message_queue_receive(") == 1 and
                        "for (;;)" not in source,
                        "una llamada anidada por entrada"))
    checks.append(check("parche runtime conservado", "PATCH_POSTIMAGE_MISMATCH" in source and
                        "receive_call_first_after" in source and
                        "receive_call_next_after" in source,
                        "verificación E02m intacta"))
    checks.append(check("hook ARM enlazado", "<hid_receive_observer>:" in disassembly,
                        "símbolo presente"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02o: {digest}")
    print(f"\nE02o local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
