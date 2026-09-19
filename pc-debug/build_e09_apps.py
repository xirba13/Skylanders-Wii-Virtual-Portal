from pathlib import Path
import subprocess,hashlib
r=Path(__file__).resolve().parents[1];out=r/'work/e09-build';out.mkdir(parents=True,exist_ok=True)
sdk=Path('C:/devkitPro');cc=sdk/'devkitPPC/bin/powerpc-eabi-gcc.exe'
arch=['-DGEKKO','-mrvl','-mcpu=750','-meabi','-mhard-float']
for name in ['e09','e09_selector']:
    elf=out/(name+'.elf');dol=out/(name+'.dol')
    subprocess.run([str(x) for x in [cc,*arch,'-O2','-Wall','-Wextra','-Werror','-I'+str(sdk/'libogc/include'),r/('probe/diagnostics/'+name+'.c'),'-L'+str(sdk/'libogc/lib/wii'),'-lfat','-lwiiuse','-lbte','-logc','-lm','-o',elf]],check=True)
    subprocess.run([str(sdk/'tools/bin/elf2dol.exe'),str(elf),str(dol)],check=True)
    b=dol.read_bytes();print(name,len(b),hashlib.sha256(b).hexdigest())
