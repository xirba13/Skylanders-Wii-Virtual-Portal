#!/usr/bin/env python3
"""Static gate for E06a's HID-open bootstrap."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")
PROBE = (ROOT / "probe/source/main.c").read_text(encoding="utf-8")


def check(name: str, ok: bool) -> bool:
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
    return ok


checks = [
    check("callsites públicos IOS57",
          "#define HID_RECEIVE_CALL_FIRST       0x13658288" in SOURCE and
          "#define HID_RECEIVE_CALL_NEXT        0x136582f4" in SOURCE),
    check("firmas originales",
          "0xeb0008f7" in SOURCE and "0xeb0008dc" in SOURCE),
    check("hook conserva ReceiveMessage",
          "result = os_message_queue_receive(queue_id, (u32 *)ret_message, flags);" in SOURCE and
          "return result;" in SOURCE),
    check("bootstrap limitado a IOS_OPEN",
          "message && message->command == IOS_OPEN" in SOURCE),
    check("instala enumeración y protocolo",
          all(token in SOURCE.split("hid_receive_open_bootstrap", 1)[1].split(
              "patch_hid_public_receive_calls", 1)[0]
              for token in ("install_getdevicechange_patch();",
                            "install_getdevparams_patch();",
                            "install_lifecycle_patches();",
                            "install_cancel_endpoint_patch();",
                            "install_control_transfer_patch();",
                            "install_interrupt_transfer_patch();"))),
    check("dos BL al hook",
          SOURCE.count("make_arm_call(HID_RECEIVE_CALL_") == 2),
    check("patcher antes de GETVERSION",
          SOURCE.index("{ patch_hid_public_receive_calls, 0 }") <
          SOURCE.index("{ patch_getversion_handler, 0 }")),
    check("probe v31", 'PROBE_BUILD "E06a-open-bootstrap-v31"' in PROBE),
]

passed = sum(checks)
print(f"\nE06a open-bootstrap gate: {passed}/{len(checks)} pruebas correctas")
raise SystemExit(0 if passed == len(checks) else 1)
