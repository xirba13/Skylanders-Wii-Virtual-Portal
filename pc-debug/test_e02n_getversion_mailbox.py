#!/usr/bin/env python3
"""Local gate for E02n's persistent GETVERSION diagnostic mailbox."""

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
    handler = function(source, "getversion_handler")
    recorder = function(source, "record_received_message")
    hook = function(source, "hid_receive_observer")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("buzón persistente", "static u8 *diagnostic_mailbox;" in source and
                        "diagnostic_mailbox = out;" in handler,
                        "conserva salida GETVERSION"))
    checks.append(check("marcador E02n", all(token in source for token in
                        ("out[4] = 0xe2;", "out[5] = 0x0e;", "out[6] = 0x01;")),
                        "E2 0E 01"))
    fields = ("receive_hook_entries", "receive_safe_messages", "last_ipc_command",
              "last_ioctl_command", "last_length_in", "last_length_io")
    checks.append(check("campos publicados", all(field in source for field in fields) and
                        all(f"put_be32(out + {offset}" in source for offset in
                            (8, 12, 16, 20, 24, 28)),
                        "contadores, IPC, ioctl y tamaños"))
    checks.append(check("registro antes de dispatch", "receive_hook_entries++;" in hook and
                        "record_received_message(message);" in hook,
                        "observa cada recepción segura"))
    checks.append(check("ioctl completo", all(token in recorder for token in
                        ("message->command", "message->ioctl.command",
                         "message->ioctl.length_in", "message->ioctl.length_io")),
                        "captura GETDEVICECHANGE sin filtrarlo"))
    checks.append(check("sin tocar change buffer", "message->ioctl.buffer_io" not in recorder and
                        "GETDEVICECHANGE_OUTPUT_SIZE" not in recorder,
                        "buzón independiente del buffer stock"))
    checks.append(check("sin ACK virtual", "os_message_queue_ack(message, 1)" not in source and
                        "portal_announced" not in source,
                        "solo telemetría"))
    checks.append(check("sin segunda recepción", source.count("os_message_queue_receive(") == 1 and
                        "for (;;)" not in source,
                        "un ReceiveMessage por entrada"))
    checks.append(check("sin segunda GETVERSION", source.count("getversion_handler(ipcmessage") == 1,
                        "un único handler"))
    checks.append(check("parche runtime conservado", "PATCH_POSTIMAGE_MISMATCH" in source and
                        "receive_call_first_after" in source and
                        "receive_call_next_after" in source,
                        "verificación E02m intacta"))
    checks.append(check("hook ARM presente", "<hid_receive_observer>:" in disassembly,
                        "símbolo enlazado"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02n: {digest}")
    print(f"\nE02n local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
