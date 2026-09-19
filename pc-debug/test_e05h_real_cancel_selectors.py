#!/usr/bin/env python3
"""Static gate for HIDv5 CancelEndpoint selectors."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    handler = SOURCE.split("cancel_endpoint_handler(ipcmessage *message)", 1)[1].split(
        "getdevparams_handler(ipcmessage *message)", 1)[0]
    checks = [
        check("selector IN", "in[8] == 1" in handler, "interrupt IN usa selector 1"),
        check("selector OUT", "in[8] == 2" in handler, "interrupt OUT usa selector 2"),
        check("sin dirección IN", "0x81" not in handler, "CancelEndpoint no confunde dirección y selector"),
        check("probe v29+", any(build in PROBE for build in
              ('PROBE_BUILD "E05h-real-cancel-selectors-v29"',
               'PROBE_BUILD "E05j-control-colour-v30"',
               'PROBE_BUILD "E06a-open-bootstrap-v31"')),
              "build confirmado o sucesor"),
        check("probe selector IN", "lifecycle_in[8] = 1" in PROBE, "prueba valor real 1"),
        check("probe selector OUT", "lifecycle_in[8] = 2" in PROBE, "prueba valor real 2"),
        check("dos cancelaciones", PROBE.count("IOS_Ioctl(fd, 0x11") == 2,
              "IN y OUT siguen aislados"),
    ]
    passed = sum(checks)
    print(f"\nE05h real-CancelEndpoint gate: {passed}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
