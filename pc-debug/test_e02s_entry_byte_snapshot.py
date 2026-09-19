#!/usr/bin/env python3
"""Local structural gate for E02s's IOS/PPC entry-byte comparison."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    checks = []
    checks.append(check("snapshot ampliada", "diagnostic_snapshot[0x40]" in PLUGIN,
                        "64 bytes en MEM2"))
    checks.append(check("captura pre-sync", "entry_before_sync[i] = out[i]" in PLUGIN and
                        PLUGIN.index("entry_before_sync[i] = out[i]") <
                        PLUGIN.index("os_sync_after_write(out, GETDEVICECHANGE_OUTPUT_SIZE)"),
                        "12 bytes antes del writeback"))
    checks.append(check("captura post-sync", "entry_after_sync[i] = out[i]" in PLUGIN and
                        PLUGIN.index("entry_after_sync[i] = out[i]") >
                        PLUGIN.index("os_sync_after_write(out, GETDEVICECHANGE_OUTPUT_SIZE)"),
                        "12 bytes leídos después del writeback"))
    checks.append(check("publicación acotada", "out[32 + i] = entry_before_sync[i]" in PLUGIN and
                        "out[44 + i] = entry_after_sync[i]" in PLUGIN,
                        "dos copias dentro de 0x40"))
    checks.append(check("probe E02s+", any(token in PROBE for token in
                        ('PROBE_BUILD "E02s-entry-byte-snapshot-v16"',
                         'PROBE_BUILD "E02t-aligned-entry-words-v17"',
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
                         'PROBE_BUILD "E06a-open-bootstrap-v31"')),
                        "build E02s o regresión posterior visible"))
    checks.append(check("snapshot IOS conservado", "entry_before_sync[12]" in PLUGIN and
                        "entry_after_sync[12]" in PLUGIN,
                        "telemetría sigue en el plugin"))
    checks.append(check("entrada PPC compacta", any(token in PROBE for token in
                        ("PPC after ACK:", "portal entry:")),
                        "la probe presenta la entrada entregada"))
    checks.append(check("sin transferencias ajenas", "BULK_TRANSFER" not in PLUGIN and
                        "ISO_TRANSFER" not in PLUGIN, "solo HID"))
    print(f"\nE02s entry-byte gate: {sum(checks)}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
