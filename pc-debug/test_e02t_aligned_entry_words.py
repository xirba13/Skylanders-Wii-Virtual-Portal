#!/usr/bin/env python3
"""Local gate for E02t's aligned 32-bit GETDEVICECHANGE entry stores."""

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
    handler_asm = disassembly.split("<getdevicechange_handler>:", 1)[1].split(
        "<getversion_handler>:", 1)[0]
    source_start = SOURCE.index("getdevicechange_handler(ipcmessage *message)")
    source_end = SOURCE.index("static s32 supervisor_patch_getdevicechange")
    handler = SOURCE[source_start:source_end]
    checks = []
    checks.append(check("puntero alineado", "volatile u32 *entry_words" in handler,
                        "escrituras de palabra explícitas"))
    checks.append(check("palabras exactas", all(token in handler for token in
                        ("entry_words[0] = 0x001f0021;",
                         "((u32)PORTAL_VID << 16) | PORTAL_PID",
                         "entry_words[2] = 0x00210001;")),
                        "001f0021 14300150 00210001"))
    forbidden = ("out[0] =", "out[1] =", "put_be16(out + 2", "put_be16(out + 4",
                 "put_be16(out + 6", "put_be16(out + 8", "out[10] =", "out[11] =")
    checks.append(check("sin construcción byte a byte", all(token not in handler for token in forbidden),
                        "retiradas las doce strb de campos"))
    aligned_stores = ("str\tr3, [r6]", "str\tr3, [r6, #4]", "str\tr3, [r6, #8]")
    checks.append(check("stores ARM de palabra", all(token in handler_asm for token in aligned_stores),
                        "STR a offsets 0, 4 y 8"))
    checks.append(check("telemetría conservada", "entry_before_sync[i] = out[i]" in handler and
                        "entry_after_sync[i] = out[i]" in handler,
                        "tres vistas E02s intactas"))
    checks.append(check("probe E02t+", any(token in PROBE for token in
                        ('PROBE_BUILD "E02t-aligned-entry-words-v17"',
                         'PROBE_BUILD "E03-getdevparams-minimal-v18"',
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
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')) and
                        any(token in PROBE for token in ("PPC after ACK:", "portal entry:")),
                        "identificador y entrada PPC visibles"))
    print(f"\nE02t aligned-word gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
