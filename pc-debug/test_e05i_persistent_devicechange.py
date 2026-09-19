#!/usr/bin/env python3
"""Static gate for first-immediate/subsequent-pending GETDEVICECHANGE."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "plugin/source/main.c").read_text(encoding="utf-8")


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    handler = SOURCE.split("getdevicechange_handler(ipcmessage *message)", 1)[1].split(
        "supervisor_patch_getdevicechange(void *in, void *out)", 1)[0]
    init = SOURCE.split("int main(void)", 1)[1]
    checks = [
        check("estado propio", "static volatile u8 getdevicechange_initial_delivered;" in SOURCE,
              "una generación inicial explícita"),
        check("inicio limpio", "getdevicechange_initial_delivered = 0;" in init,
              "cada carga de IOS252 empieza sin anunciar"),
        check("primera inmediata", "if (!getdevicechange_initial_delivered)" in handler and
              "getdevicechange_initial_delivered = 1;" in handler and "result = 1;" in handler,
              "la primera petición entrega el portal"),
        check("segunda pendiente", "acknowledge = 0;" in handler and
              "if (message && acknowledge)" in handler,
              "la petición posterior no recibe ACK"),
        check("sin reescritura posterior", handler.index("if (!getdevicechange_initial_delivered)") <
              handler.index("zero_bytes(out, GETDEVICECHANGE_OUTPUT_SIZE)"),
              "solo la primera modifica el buffer"),
        check("validación conservada", all(token in handler for token in
              ("IOCTL_USBV5_GETDEVICECHANGE", "last_length_in == 0",
               "last_length_io == GETDEVICECHANGE_OUTPUT_SIZE", "entry_words[0] = 0x001f0021")),
              "forma HIDv5 y entrada E02t intactas"),
        check("inválidas responden", "u32 acknowledge = 1;" in handler and "s32 result = -4;" in handler,
              "solo una segunda petición válida queda pendiente"),
    ]
    passed = sum(checks)
    print(f"\nE05i persistent-GETDEVICECHANGE gate: {passed}/{len(checks)} pruebas correctas")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
