#!/usr/bin/env python3
"""Local gate for E04's isolated virtual CancelEndpoint handler."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")
ORIG = ROOT / "plugin/skylanders-hidv5-plugin.elf.orig"
IOS57 = ROOT.parent / "work/ios-analysis/IOS57_v6175/0000000d.app"
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def ios_u32(address: int) -> int:
    blob = IOS57.read_bytes()
    offset = 0x108 + address - 0x13658000
    return int.from_bytes(blob[offset:offset + 4], "big")


def main() -> int:
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    handler = SOURCE.split("cancel_endpoint_handler(ipcmessage *message)", 1)[1].split(
        "getdevparams_handler(ipcmessage *message)", 1)[0]
    supervisor = SOURCE.split("supervisor_patch_cancel_endpoint(void *in, void *out)", 1)[1].split(
        "static s32 install_cancel_endpoint_patch", 1)[0]
    checks = []
    checks.append(check("firma IOS57", ios_u32(0x13659588) == 0xE1A0C00D,
                        "0x13659588 = prólogo ARM esperado"))
    checks.append(check("dirección exacta", "HID_CANCEL_ENDPOINT_HANDLER  0x13659588" in SOURCE,
                        "destino exclusivo del ioctl 0x11"))
    checks.append(check("validación estricta", all(token in handler for token in
                        ("IOCTL_USBV5_CANCEL_ENDPOINT", "GETDEVPARAMS_INPUT_SIZE",
                         "length_io == 0", "!message->ioctl.buffer_io",
                         "in_words[0] == PORTAL_DEVICE_ID")),
                        "0x20 de entrada, sin salida, ID virtual"))
    checks.append(check("selectores acotados", "in[8] == 1 || in[8] == 2" in handler,
                        "HIDv5: 1=interrupt IN, 2=interrupt OUT"))
    checks.append(check("parche supervisor", all(token in supervisor for token in
                        ("Perms_Read()", "Perms_Write(0xffffffff)", "HANDLER_PROLOGUE",
                         "DCWrite32(HID_CANCEL_ENDPOINT_HANDLER", "ICInvalidate()",
                         "Perms_Write(permissions)")), "disciplina confirmada"))
    checks.append(check("readback", "!= branch" in supervisor and
                        "cancel_endpoint_patch_result = PATCH_APPLIED" in supervisor,
                        "salto leído tras escritura"))
    checks.append(check("símbolos ARM", all(f"<{name}>:" in disassembly for name in
                        ("cancel_endpoint_handler", "supervisor_patch_cancel_endpoint")),
                        "handler y supervisor enlazados"))
    checks.append(check("probe dos endpoints", PROBE.count("IOS_Ioctl(fd, 0x11") == 2 and
                        "lifecycle_in[8] = 1" in PROBE and
                        "lifecycle_in[8] = 2" in PROBE,
                        "cancelación IN y OUT independiente"))
    checks.append(check("orden probe", PROBE.index("IOS_Ioctl(fd, 3") <
                        PROBE.index("IOS_Ioctl(fd, 0x11"),
                        "descriptores antes de cancelar"))
    checks.append(check("sin transferencias ajenas", "BULK_TRANSFER" not in SOURCE and
                        "ISO_TRANSFER" not in SOURCE, "sin bulk ni isócrona"))
    print(f"\nE04 CancelEndpoint gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
