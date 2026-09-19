#!/usr/bin/env python3
"""Local gate for E04's minimal HIDv5 AttachFinish/SuspendResume lifecycle."""

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
    attach = SOURCE.split("attachfinish_handler(ipcmessage *message)", 1)[1].split(
        "suspend_resume_handler(ipcmessage *message)", 1)[0]
    suspend = SOURCE.split("suspend_resume_handler(ipcmessage *message)", 1)[1].split(
        "getdevparams_handler(ipcmessage *message)", 1)[0]
    supervisor = SOURCE.split("supervisor_patch_lifecycle(void *in, void *out)", 1)[1].split(
        "static s32 install_lifecycle_patches", 1)[0]
    checks = []
    checks.append(check("firmas IOS57", ios_u32(0x13658CC0) == 0xE1A0C00D and
                        ios_u32(0x13658EE4) == 0xE1A0C00D,
                        "AttachFinish 0x13658cc0 y SuspendResume 0x13658ee4"))
    checks.append(check("direcciones compiladas", all(token in SOURCE for token in
                        ("HID_ATTACHFINISH_HANDLER     0x13658cc0",
                         "HID_SUSPEND_RESUME_HANDLER   0x13658ee4")),
                        "literales exactos IOS57 v6175"))
    checks.append(check("AttachFinish estricto", all(token in attach for token in
                        ("IOCTL_USBV5_ATTACHFINISH", "length_in == 0",
                         "length_io == 0", "!message->ioctl.buffer_in",
                         "!message->ioctl.buffer_io")), "ioctl 6 sin buffers"))
    checks.append(check("SuspendResume estricto", all(token in suspend for token in
                        ("IOCTL_USBV5_SUSPEND_RESUME", "GETDEVPARAMS_INPUT_SIZE",
                         "length_io == 0", "in_words[0] == PORTAL_DEVICE_ID",
                         "in[11] <= 1", "portal_resumed = in[11]")),
                        "0x20, ID virtual y estado 0/1"))
    checks.append(check("preflight atómico", supervisor.index("HID_ATTACHFINISH_HANDLER") <
                        supervisor.index("HID_SUSPEND_RESUME_HANDLER") <
                        supervisor.index("DCWrite32(HID_ATTACHFINISH_HANDLER"),
                        "comprueba ambas firmas antes de escribir"))
    checks.append(check("disciplina supervisor", all(token in supervisor for token in
                        ("Perms_Read()", "Perms_Write(0xffffffff)", "DCWrite32",
                         "ICInvalidate()", "Perms_Write(permissions)")),
                        "mismo mecanismo confirmado E02/E03"))
    checks.append(check("readback doble", all(token in supervisor for token in
                        ("!= attach_branch", "!= suspend_branch",
                         "attachfinish_patch_result = PATCH_APPLIED",
                         "suspend_resume_patch_result = PATCH_APPLIED")),
                        "ambos saltos verificados"))
    checks.append(check("símbolos ARM", all(f"<{name}>:" in disassembly for name in
                        ("attachfinish_handler", "suspend_resume_handler",
                         "supervisor_patch_lifecycle")), "handlers enlazados"))
    checks.append(check("orden probe", PROBE.index("IOS_Ioctl(fd, 6") <
                        PROBE.index("IOS_Ioctl(fd, 0x10") <
                        PROBE.index("IOS_Ioctl(fd, 3"),
                        "AttachFinish -> resume -> GETDEVPARAMS"))
    checks.append(check("sin transferencias ajenas", "BULK_TRANSFER" not in SOURCE and
                        "ISO_TRANSFER" not in SOURCE, "sin bulk ni isócrona"))
    print(f"\nE04 lifecycle gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
