"""Decode the figure-free E09a runtime summary from an SD card."""
import argparse, struct
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('trace',type=Path)
a=parser.parse_args()
b=a.trace.read_bytes()
if len(b)!=64: raise SystemExit('Expected exactly 64 bytes')
v=struct.unpack('>16I',b)
if v[0]!=0x45303931: raise SystemExit('Unrecognized summary')
labels=['magic','loaded','source_slot','generation','saved_generation','storage_error','busy','sequence','load_attempts','load_phase','empty_statuses','present_statuses','Q_commands','W_commands','last_command','timer_ticks']
for name,value in zip(labels,v):
    if name=='storage_error' and value>=0x80000000: value-=0x100000000
    print(f'{name}: {value}')
