"""Extract a private replay fixture from the user's instrumented Dolphin log.
USB_RESPONSE <=27 contains the original control payload plus8 completion bytes.
32-byte responses are interrupt packets. This is a content/order test, not an
IOS scheduling simulation. Reconstruct only observed initial figure blocks.
"""
from pathlib import Path
import argparse,re,json,collections
p=argparse.ArgumentParser();p.add_argument('log',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
events=[];blocks={};written=set();counts=collections.Counter();states=collections.Counter()
for line_no,line in enumerate(a.log.read_text().splitlines(),1):
 if 'PORTALTRACE USB_RESPONSE ' not in line:continue
 m=re.search(r'result=(\d+) expected_us=(\d+) hex=([0-9a-f]+)',line)
 if not m:continue
 size=int(m[1]);b=bytes.fromhex(m[3]);counts[f'{size}:{b[0]:02x}']+=1
 if size==8:continue # idle/protocol setup, no figure traffic
 if size==32:
  events.append(f'I {line_no} {b.hex()}')
  if b[0]==83:states[b[1:5].hex()+':'+str(b[6])]+=1
  if b[0]==81 and b[1]&16 and b[2] not in blocks and b[2] not in written:blocks[b[2]]=b[3:19]
 else:
  assert size==len(b) and b[0] in b'RACQWS'
  events.append(f'C {line_no} {b[:size-8].hex()}')
  if b[0]==87:written.add(b[2])
figure=bytearray(1024)
for i,b in blocks.items():figure[i*16:i*16+16]=b
a.out.mkdir(parents=True,exist_ok=True)
(a.out/'figure.bin').write_bytes(figure)
(a.out/'events.txt').write_text('\n'.join(events)+'\n')
(a.out/'summary.json').write_text(json.dumps({'events':len(events),'response_counts':dict(counts),'statuses':dict(states),'observed_initial_blocks':sorted(blocks)},indent=2))
print('Extracted',len(events),'events;',len(blocks),'initial blocks. Private fixture retained locally.')
