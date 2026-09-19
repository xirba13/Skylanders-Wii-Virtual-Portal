#!/usr/bin/env python3
"""Local gate for E03's minimal HIDv5 GETDEVPARAMS response."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")
ORIG = ROOT / "plugin/skylanders-hidv5-plugin.elf.orig"
OBJDUMP = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-objdump.exe")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    disassembly = subprocess.check_output([str(OBJDUMP), "-d", str(ORIG)], text=True)
    handler = SOURCE.split("getdevparams_handler(ipcmessage *message)", 1)[1].split(
        "static s32 __attribute__((target(\"arm\"), noinline))\ngetdevicechange_handler", 1)[0]
    supervisor = SOURCE.split("supervisor_patch_getdevparams(void *in, void *out)", 1)[1].split(
        "static s32 install_getdevparams_patch", 1)[0]
    handler_asm = disassembly.split("<getdevparams_handler>:", 1)[1].split(
        "<supervisor_patch_getdevparams>:", 1)[0]
    words = (0x00000001, 0x12010002, 0x00000040,
             0x30145001, 0x00010102, 0x00010000, 0x09020029,
             0x01010080, 0xFA000000, 0x09040000, 0x02030000,
             0x00000000, 0x07058103, 0x00400001, 0x07050203,
             0x00400001)
    expected = bytes.fromhex(
        "001f002100000001" + "00" * 28 +
        "1201000200000040301450010001010200010000" +
        "0902002901010080fa000000" +
        "090400000203000000000000" +
        "0705810300400001" + "0705020300400001")
    checks = []
    checks.append(check("tamaño del modelo", len(expected) == 0x60,
                        f"{len(expected)} bytes"))
    checks.append(check("dirección IOS57", "HID_GETDEVPARAMS_HANDLER     0x13658d40" in SOURCE,
                        "handler corregido"))
    checks.append(check("validación exacta", all(token in handler for token in
                        ("IOCTL_USBV5_GETDEVPARAMS", "GETDEVPARAMS_INPUT_SIZE",
                         "GETDEVPARAMS_OUTPUT_SIZE", "in_words[0] == PORTAL_DEVICE_ID")),
                        "ioctl 3, 0x20/0x60, ID virtual"))
    checks.append(check("descriptores completos", all(f"0x{word:08x}" in handler.lower()
                        for word in words), "cabecera + device/config/interface/endpoints"))
    checks.append(check("salida por palabras", "volatile u32 *out_words" in handler and
                        "out_words[23]" in handler and "put_be16" not in handler,
                        "24 palabras alineadas"))
    checks.append(check("STR de salida", all(f"[r5, #{offset}]" in handler_asm
                        for offset in (36, 40, 44, 48, 52, 56, 60, 64, 68, 72,
                                       76, 80, 84, 88, 92)),
                        "desensamblado con offsets de descriptor"))
    checks.append(check("parche supervisor", all(token in supervisor for token in
                        ("Perms_Read()", "Perms_Write(0xffffffff)", "HANDLER_PROLOGUE",
                         "DCWrite32(HID_GETDEVPARAMS_HANDLER", "ICInvalidate()",
                         "Perms_Write(permissions)")), "misma disciplina E02r"))
    checks.append(check("estado visible", "out[5] = getdevparams_patch_result" in SOURCE,
                        "byte 5 del snapshot"))
    checks.append(check("probe ordenada", PROBE.index("IOS_IoctlAsync(fd, 1") <
                        PROBE.index("IOS_Ioctl(fd, 3") and any(token in PROBE for token in
                        ('PROBE_BUILD "E03-getdevparams-minimal-v18"',
                         'PROBE_BUILD "E04-lifecycle-minimal-v19"',
                         'PROBE_BUILD "E04-cancelendpoint-minimal-v20"',
                         'PROBE_BUILD "E04-control-activation-minimal-v21"',
                         'PROBE_BUILD "E05-activation-intr-minimal-v22"',
                         'PROBE_BUILD "E05-intr-out-light-minimal-v23"',
                         'PROBE_BUILD "E05c-pending-in-minimal-v24"',
                         'PROBE_BUILD "E05d-idle-status-minimal-v25"',
                         'PROBE_BUILD "E05e-aligned-status-words-v26"',
                         'PROBE_BUILD "E05f-giants-reset-handshake-v27"',
                         'PROBE_BUILD "E05g-real-hid-set-report-v28"',
                         'PROBE_BUILD "E05h-real-cancel-selectors-v29"',
                         'PROBE_BUILD "E05j-control-colour-v30"',
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')),
                        "enumeración antes de parámetros"))
    checks.append(check("sin transferencias ajenas", "BULK_TRANSFER" not in SOURCE and
                        "ISO_TRANSFER" not in SOURCE, "sin bulk ni isócrona"))
    print(f"\nE03 GETDEVPARAMS gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
