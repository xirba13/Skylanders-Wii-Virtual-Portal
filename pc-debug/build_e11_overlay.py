from pathlib import Path
import argparse,struct,subprocess,hashlib,json
R=Path(__file__).resolve().parents[1];sdk=Path('C:/devkitPro');cc=sdk/'devkitPPC/bin/powerpc-eabi-gcc.exe'
p=argparse.ArgumentParser();p.add_argument('dol',type=Path);p.add_argument('output',type=Path);p.add_argument('--multi-slot',action='store_true');p.add_argument('--sync-copy',action='store_true',help='Experimental render-thread GPU fence; requires --multi-slot');a=p.parse_args()
if a.sync_copy and not a.multi_slot:raise SystemExit('--sync-copy requires --multi-slot')
b=bytearray(a.dol.read_bytes());h=list(struct.unpack_from('>64I',b));out=a.output;out.mkdir(parents=True,exist_ok=True)
# Fingerprint generated from the inspected user-supplied executable, never guess another region/revision.
EXPECTED=hashlib.sha256(b).hexdigest()
profiles=json.loads((R/'overlay/profiles.json').read_text())
match=[(game,profile) for game,profile in profiles.items() if profile['sha256']==EXPECTED]
if len(match)!=1:raise SystemExit('Unsupported DOL fingerprint; no output patched')
game,profile=match[0]
original=bytes(b)
flags=['-mcpu=750','-meabi','-msoft-float','-msdata=none','-Os','-ffreestanding','-fno-builtin','-fno-asynchronous-unwind-tables','-fno-unwind-tables','-Wall','-Wextra','-Werror']
flags.extend(['-DGAME_MEMCPY='+hex(profile['memcpy'])+'u','-DGAME_WPAD_TABLE='+hex(profile['wpad_table'])+'u'])
if a.multi_slot:flags.append('-DE12_MENU')
if a.sync_copy:flags.extend(['-DE13_SYNC_COPY','-DGAME_COPY_DISP='+hex(profile['copy_disp'])+'u','-DGAME_DRAW_DONE='+hex(profile['draw_done'])+'u'])
if a.sync_copy and profile.get('copy_entry'):flags.append('-DGAME_COPY_ENTRY')
if a.sync_copy and profile.get('render_poll'):flags.append('-DGAME_RENDER_POLL')
if a.sync_copy and profile.get('hold_frame'):
 if not profile.get('render_poll'):raise SystemExit('Held-frame menu requires render polling')
 flags.append('-DGAME_HOLD_FRAME')
if a.sync_copy and profile.get('gx_data_pointer'):flags.append('-DGAME_GX_DATA_POINTER='+hex(profile['gx_data_pointer'])+'u')
objs=[]
for name in ['menu.c','trampoline.S']:
 obj=out/(name+'.o');subprocess.run([str(cc),*flags,'-c',str(R/'overlay'/name),'-o',str(obj)],check=True);objs.append(str(obj))
elf=out/'overlay.elf';raw=out/'overlay.bin'
subprocess.run([str(cc),*flags,'-nostdlib','-Wl,-T,'+str(R/'overlay/link.ld'),'-Wl,--defsym,vi_continue='+hex(profile['vi']+4),'-Wl,--defsym,read_continue='+hex(profile['read']+4),'-Wl,--defsym,copy_continue='+hex(profile['copy_disp']+4),*objs,'-lgcc','-o',str(elf)],check=True)
subprocess.run([str(sdk/'devkitPPC/bin/powerpc-eabi-objcopy.exe'),'-O','binary',str(elf),str(raw)],check=True)
nm=subprocess.check_output([str(sdk/'devkitPPC/bin/powerpc-eabi-nm.exe'),str(elf)],text=True)
symbols={row.split()[2]:int(row.split()[0],16) for row in nm.splitlines() if len(row.split())==3}
payload=raw.read_bytes();assert len(payload)<=0x1400 and symbols['overlay_end']<=0x80002c00
# Include zero-filled BSS and the shared mailbox as loaded bytes, not a new global BSS range.
payload+=bytes(0x1800-len(payload));base=0x80001800
segs=[(h[i],h[18+i],h[36+i]) for i in range(18) if h[36+i]]
assert all(not(base<v+n and v<base+len(payload)) for o,v,n in segs)
assert not(base<h[54]+h[55] and h[54]<base+len(payload))
def offset(addr):
 for o,v,n in segs:
  if v<=addr<v+n:return o+addr-v
 raise ValueError(hex(addr))
def hook(addr,old,dest,link=False):
 o=offset(addr);assert struct.unpack_from('>I',b,o)[0]==old
 delta=dest-addr;assert delta%4==0 and -0x2000000<=delta<0x2000000
 struct.pack_into('>I',b,o,0x48000000|(delta&0x3fffffc)|int(link))
hook(profile['vi'],0x9421fff0,symbols['vi_hook'])
hook(profile['read'],0x9421ffe0,symbols['read_hook'])
hook(profile['sample'],profile['sample_instruction'],symbols['sample_hook'],True)
if a.sync_copy:
 if profile.get('copy_entry'):hook(profile['copy_disp'],0x2c040000,symbols['copy_hook'])
 for site in profile['copy_sites']:
  original_call=0x48000001|((profile['copy_disp']-site)&0x3fffffc)
  hook(site,original_call,symbols['copy_hook'],True)

i=next(i for i in range(7) if h[36+i]==0)
while len(b)%32:b.append(0)
h[i]=len(b);h[18+i]=base;h[36+i]=len(payload);struct.pack_into('>64I',b,0,*h);b.extend(payload)
(out/(game+'.dol')).write_bytes(b)
report={'game_id':game,'sync_copy':a.sync_copy,'profile':profile,'original_sha256':EXPECTED,'patched_sha256':hashlib.sha256(b).hexdigest(),'payload_bytes':len(raw.read_bytes()),'reserved_bytes':len(payload),'symbols':{k:hex(v) for k,v in symbols.items()},'hardware_tested':False}
(out/'build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))



# Portable sparse patch: replacement bytes plus our appended overlay, no full game.
writes=[];start=None
for pos in range(len(original)):
 if b[pos]!=original[pos]:
  if start is None:start=pos
 elif start is not None:
  writes.append({'offset':start,'hex':b[start:pos].hex()});start=None
if start is not None:writes.append({'offset':start,'hex':b[start:len(original)].hex()})
if len(b)>len(original):writes.append({'offset':len(original),'hex':b[len(original):].hex()})
patch={'format':'skylanders-dol-patch-v1','game_id':game,'input_sha256':EXPECTED,'output_sha256':hashlib.sha256(b).hexdigest(),'input_size':len(original),'output_size':len(b),'writes':writes}
(out/(game+'.patch.json')).write_text(json.dumps(patch,indent=2)+'\n')
