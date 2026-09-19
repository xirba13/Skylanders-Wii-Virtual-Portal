from pathlib import Path
import subprocess,struct,re
root=Path.cwd();src=(root/'plugin/source/main.c').read_text();out=root/'work/e06d-build'
a=src.index('hid_discovery_bootstrap(ipcmessage *message)');b=src.index('\nstatic s32 ',a)
body='static s32\n'+src[a:b]
head='''#include <stdio.h>
#include <stdlib.h>
typedef int s32;
typedef struct {int x;} ipcmessage;
static int fail, calls, handled, ack;
static int install(int n){calls++;return fail==n?-1:0;}
#define install_getdevicechange_patch() install(1)
#define install_getdevparams_patch() install(2)
#define install_lifecycle_patches() install(3)
#define install_cancel_endpoint_patch() install(4)
#define install_control_transfer_patch() install(5)
#define install_interrupt_transfer_patch() install(6)
static int getdevicechange_handler(ipcmessage *m){(void)m;handled++;return 0;}
static void os_message_queue_ack(ipcmessage *m,int r){if(!m||r!=-4)abort();ack++;}
'''
tail='''
int main(void){ipcmessage m={0};
for(fail=0;fail<=6;fail++){calls=handled=ack=0;hid_discovery_bootstrap(&m);
if(calls!=(fail?fail:6)||handled!=(fail==0)||ack!=(fail!=0))abort();}
fail=1;ack=0;hid_discovery_bootstrap(NULL);if(ack)abort();
puts("PASS: bootstrap success, six installer failures, null-message failure");return 0;}
'''
(out/'bootstrap_test.c').write_text(head+body+tail)
cc=root.parent/'work/toolchains/llvm-mingw-20260616/llvm-mingw-20260616-msvcrt-x86_64/bin/clang.exe'
subprocess.run([str(cc),'-std=c11','-Wall','-Wextra','-Werror',str(out/'bootstrap_test.c'),'-o',str(out/'bootstrap_test.exe')],check=True)
subprocess.run([str(out/'bootstrap_test.exe')],check=True)
import sys
sys.path.insert(0,str(root/'pc-debug'))
from skylanders_lab import elf_segments,address_to_offset,decode_arm_branch
hid=(root.parent/'work/ios-analysis/IOS57_v6175/0000000d.app').read_bytes()
site=0x13658180;word=struct.unpack_from('>I',hid,address_to_offset(elf_segments(hid),site,4))[0]
assert word==0xeb000217 and decode_arm_branch(site,word)==0x136589e4
nm=subprocess.check_output(['C:/devkitPro/devkitARM/bin/arm-none-eabi-nm.exe',str(out/'SKYLANDERS.elf')],text=True)
target=int(re.search(r'^([0-9a-f]+) t hid_discovery_bootstrap$',nm,re.M)[1],16)
assert target%4==0 and -(1<<25)<=target-site-8<(1<<25)
branch=0xeb000000|(((target-site-8)>>2)&0xffffff)
assert decode_arm_branch(site,branch)==target
segments=elf_segments((out/'SKYLANDERS.app').read_bytes())
assert any(s.contains(target,4) and s.flags&1 for s in segments)
old=subprocess.check_output(['C:/Program Files/Git/cmd/git.exe','show','ce5dcb3:plugin/source/main.c'],text=True)
for name in ['control_transfer_handler','interrupt_transfer_handler','getdevicechange_handler','getdevparams_handler','getversion_handler','supervisor_patch_getdevicechange']:
 def extract(s):
  start=s.index(name+'(');end=s.index('\nstatic ',start);return s[start:end]
 assert extract(src)==extract(old),name
assert '{ patch_hid_public_receive_calls, 0 }' not in src
print(f'PASS: IOS57 original BL -> discovery; ARM target {target:08x}; branch {branch:08x}; unchanged protocol/lazy handlers')
