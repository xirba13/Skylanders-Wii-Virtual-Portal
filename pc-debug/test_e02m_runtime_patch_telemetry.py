#!/usr/bin/env python3
"""Local gate for E02m runtime callsite patch telemetry."""

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
    patch = function(source, "patch_hid_public_receive_calls")
    observer = function(source, "observe_change_buffer")
    checks = []
    checks.append(check("ELF IOS", blob[:4] == b"\x7fELF", str(ELF)))
    checks.append(check("firmas estáticas", all(token in source for token in
                        ("0xeb0008f7", "0xeb0008dc", "0xe1a0c00d")),
                        "dos callsites y GETVERSION"))
    checks.append(check("marcador E02m", all(token in source for token in
                        ("out[4] = 0xe2;", "out[5] = 0x0d;",
                         "out[6] = 0x01;", "out[7] = 0x5a;")),
                        "E2 0D 01 5A"))
    checks.append(check("estados explícitos", all(token in source for token in
                        ("PATCH_NOT_EVALUATED", "PATCH_PREIMAGE_MISMATCH",
                         "PATCH_POSTIMAGE_MISMATCH", "PATCH_APPLIED")),
                        "EE, FF, FE y 00"))
    checks.append(check("snapshot antes", patch.find("receive_call_first_before =") <
                        patch.find("receive_call_first_before !=") and
                        patch.find("receive_call_next_before =") <
                        patch.find("receive_call_next_before !="),
                        "lectura anterior a la comparación"))
    checks.append(check("snapshot después", "receive_call_first_after =" in patch and
                        "receive_call_next_after =" in patch and
                        "PATCH_POSTIMAGE_MISMATCH" in patch,
                        "verifica ambas ramas escritas"))
    telemetry = ("receive_patch_result", "receive_call_first_before",
                 "receive_call_next_before", "receive_call_first_after",
                 "receive_call_next_after", "receive_hook_target")
    checks.append(check("telemetría GETVERSION", all(f"put_be32(out + {offset}" in source
                        for offset in (12, 16, 20, 24, 28)) and
                        "out[8] = receive_patch_result;" in source and
                        all(field in source for field in telemetry),
                        "estado, preimagen, postimagen y destino"))
    checks.append(check("GETDEVICECHANGE sin ACK", "os_message_queue_ack(message, 1)" not in source and
                        "portal_announced" not in source,
                        "ninguna respuesta virtual"))
    checks.append(check("observador E02l conservado", "message->ioctl.length_in != 0" in observer and
                        "message->ioctl.length_io != GETDEVICECHANGE_OUTPUT_SIZE" in observer and
                        "out[0] = 0xe2;" in observer and "out[1] = 0x0c;" in observer,
                        "mismas condiciones y firma inline"))
    checks.append(check("dos ramas públicas", disassembly.count("<hid_receive_observer>") >= 1 and
                        all(bytes.fromhex(x) in blob for x in ("13658288", "136582f4")),
                        "callsite patch acotado"))

    digest = sha256(blob).hexdigest().upper()
    print(f"[INFO] SHA-256 E02m: {digest}")
    print(f"\nE02m local gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
