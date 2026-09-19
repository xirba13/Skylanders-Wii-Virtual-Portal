#!/usr/bin/env python3
"""Local structural gate for E04's compact no-SD lifecycle probe."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "probe" / "source" / "main.c"
DOL = ROOT / "probe" / "skylanders-hid-probe.dol"


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    dol = DOL.read_bytes()
    reload_pos = source.index("IOS_ReloadIOS(252)")
    open_pos = source.index('IOS_Open("/dev/usb/hid", 0)')
    submit_pos = source.index("IOS_IoctlAsync(fd, 1")
    attach_pos = source.index("IOS_Ioctl(fd, 6")
    resume_pos = source.index("IOS_Ioctl(fd, 0x10")
    params_pos = source.index("IOS_Ioctl(fd, 3")
    checks = []
    checks.append(check("DOL generado", len(dol) > 0, f"{len(dol)} bytes"))
    checks.append(check("orden diagnóstico", reload_pos < open_pos < submit_pos < attach_pos <
                        resume_pos < params_pos,
                        "reload < open < change < attachfinish < resume < params"))
    checks.append(check("build visible", any(token in source for token in
                        ('PROBE_BUILD "E04-cancelendpoint-minimal-v20"',
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
                        "identificador en pantalla"))
    phases = ("before_open", "after_open", "before_getversion", "after_getversion",
              "before_getdevicechange_submit", "after_getdevicechange_wait",
              "before_attachfinish", "after_attachfinish",
              "before_resume", "after_resume",
              "before_getdevparams", "after_getdevparams")
    checks.append(check("fases visibles", all(phase in source for phase in phases),
                        "límites HID sin FAT"))
    checks.append(check("cierre seguro", "if (change_done)" in source and
                        "phase=skip_close_pending_change" in source,
                        "no cierra con GETDEVICECHANGE pendiente"))
    sd_tokens = ("fatInitDefault", "fatMountSimple", "__io_wiisd",
                 "sd:/", "fopen(", "log_hex")
    checks.append(check("sin SD/FAT", all(token not in source for token in sd_tokens) and
                        "<fat.h>" not in source and "<sdcard/wiisd_io.h>" not in source,
                        "ningún montaje ni escritura de informe"))
    checks.append(check("salida automática segura", "if (change_done)" in source and
                        "salida automatica en 10 segundos" in source and
                        "sleep(10);" in source,
                        "solo después de callback y cierre seguro"))
    checks.append(check("un descriptor HID", source.count('IOS_Open("/dev/usb/hid", 0)') == 1 and
                        "fd_diag" not in source and "before_open_diagnostic" not in source,
                        "no repite el bloqueo E02o"))
    checks.append(check("GETVERSION único", source.count("IOS_Ioctl(fd, 0, NULL") == 1 and
                        "IOS_IoctlAsync(fd, 0" not in source,
                        "sin segundo diagnóstico HID"))
    checks.append(check("salida compacta", "snapshot before:" not in source and
                        "snapshot after:" not in source and
                        'print_hex(NULL, "version: ", version_buffer, 4)' in source,
                        "sin volcado diagnóstico que desborde la pantalla"))
    checks.append(check("AttachFinish mínimo", source.count("IOS_Ioctl(fd, 6") == 1 and
                        "NULL, 0, NULL, 0" in source,
                        "ioctl 6 sin buffers"))
    checks.append(check("Resume realista", "lifecycle_in[0x20]" in source and
                        "((u32 *)lifecycle_in)[0] = 0x001f0021" in source and
                        "lifecycle_in[11] = 1" in source,
                        "ID virtual + estado resume en byte 11"))
    checks.append(check("GETDEVPARAMS mínimo", source.count("IOS_Ioctl(fd, 3") == 1 and
                        "params_in[0x20]" in source and "params_out[0x60]" in source and
                        "((u32 *)params_in)[0] = 0x001f0021" in source,
                        "una petición para el ID virtual confirmado"))
    checks.append(check("GETDEVICECHANGE aislado", source.count("IOS_IoctlAsync(fd, 1") == 1 and
                        "change_buffer[0x180]" in source and
                        "while (!change_done && waited_ms < 5000)" in source,
                        "una enumeración con timeout"))
    checks.append(check("resultado en pantalla", "Diagnostico completo; esta build no accede a SD." in source,
                        "no depende de un informe"))

    print(f"\nProbe HID-before-FAT gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
