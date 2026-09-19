"""Build only the E08 diagnostic; no cIOS build, installation or SD writes."""
from pathlib import Path
import subprocess, hashlib, struct
root=Path(__file__).resolve().parents[1]
out=root/'work/e08-build'
out.mkdir(parents=True,exist_ok=True)
sdk=Path('C:/devkitPro')
cc=sdk/'devkitPPC/bin/powerpc-eabi-gcc.exe'
arch=['-DGEKKO','-mrvl','-mcpu=750','-meabi','-mhard-float']
def run(args):subprocess.run([str(x) for x in args],check=True)
run([cc,*arch,'-O2','-Wall','-Wextra','-Werror','-I'+str(sdk/'libogc/include'),
     '-c',root/'probe/diagnostics/e08.c','-o',out/'probe.o'])
run([cc,*arch,out/'probe.o','-L'+str(sdk/'libogc/lib/wii'),'-logc','-lm','-o',out/'e08-probe.elf'])
run([sdk/'tools/bin/elf2dol.exe',out/'e08-probe.elf',out/'e08-boot.dol'])
data=(out/'e08-boot.dol').read_bytes()
assert b'E08 SINGLE CHARACTER - RAM writes' in data
for offset,size in zip(struct.unpack_from('>18I',data,0),struct.unpack_from('>18I',data,0x90)):
    assert not size or (offset>=256 and offset+size<=len(data))
print('PASS: DOL identity and sections;',len(data),'bytes; SHA256',hashlib.sha256(data).hexdigest())
