"""Build with native devkitPro tools without requiring the MSYS process runtime.

Writes candidates under work/e06b-build; does not replace installer/SD files.
"""
from pathlib import Path
import argparse
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SDK = Path('C:/devkitPro')
parser = argparse.ArgumentParser()
parser.add_argument('--out', default='work/e06b-build')
parser.add_argument('--sdk', type=Path, default=SDK)
parser.add_argument('--cios-lib', type=Path, default=ROOT.parent / 'work/fakemote/embedded-game-controller/cios-lib')
parser.add_argument('--d2x-lib', type=Path, default=ROOT.parent / 'work/skylanders-research/d2x-cios-full/source/cios-lib')
parser.add_argument('--stripios', type=Path, default=ROOT.parent / 'work/stripios-current-static.exe')
parser.add_argument('--module-only', action='store_true', help='Skip the historical diagnostic probe')
parser.add_argument('--figure', type=Path, help='Private 1024-byte figure copied into RAM; no persistence')
parser.add_argument('--storage',action='store_true',help='Load selected figure and save asynchronously to SD')
parser.add_argument('--menu',action='store_true',help='E11 SD library and in-game mailbox (implies storage)')
parser.add_argument('--multi-slot',action='store_true',help='E12: 16 figures and journal persistence')
args=parser.parse_args()
if args.multi_slot: args.menu=True
if args.menu: args.storage=True
if args.storage and args.figure: parser.error('Choose --storage or --figure')
OUT = ROOT / args.out
OUT.mkdir(parents=True, exist_ok=True)
SDK = args.sdk.resolve()
CIOS = args.cios_lib.resolve()
D2X = args.d2x_lib.resolve()
ARM = SDK / 'devkitARM/bin/arm-none-eabi-gcc.exe'
PPC = SDK / 'devkitPPC/bin/powerpc-eabi-gcc.exe'

def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)

arch = ['-mcpu=arm926ej-s', '-mthumb', '-mthumb-interwork', '-mbig-endian']
flags = arch + ['-std=gnu11', '-I'+str(CIOS), '-I'+str(D2X), '-ffreestanding',
                '-fno-builtin', '-ffunction-sections', '-fomit-frame-pointer',
                '-Os', '-Wall', '-Wstrict-prototypes']
figure_flags=['-DE09_STORAGE'] if args.storage else []
if args.menu: figure_flags.append('-DE11_MENU')
if args.multi_slot: figure_flags.append('-DE12_MENU')
if args.figure:
    data=args.figure.read_bytes()
    if len(data)!=1024: raise SystemExit('Figure must be exactly 1024 bytes')
    generated=OUT/'private_figure.h'
    generated.write_text('#define V4_FIGURE_PRESENT 1\n#define V4_FIGURE_DATA e08_figure\n'
        +'static unsigned char e08_figure[1024] = {'+','.join(str(x) for x in data)+'};\n')
    figure_flags=['-include',str(generated)]
    print('Figure SHA256',hashlib.sha256(data).hexdigest())
objects = []
for src in [ROOT/'plugin/source/main.c', ROOT/'plugin/source/start.s',
            CIOS/'syscalls.s', CIOS/'ios.c', CIOS/'swi_mload.c', CIOS/'tools.s',
            CIOS/'str_utils.c', D2X/'isfs.c']:
    obj = OUT / (src.stem+'.o')
    extra = ['-D_LANGUAGE_ASSEMBLY', '-x', 'assembler-with-cpp'] if src.suffix=='.s' else []
    run([ARM, *flags, *extra, *(figure_flags if src.name=='main.c' else []), '-c', src, '-o', obj])
    objects.append(obj)
elf = OUT / 'SKYLANDERS.elf'
run([ARM, *arch, '-nostartfiles', '-nostdlib', '-Wl,-T,'+str(ROOT/'plugin/source/link.ld'),
     '-Wl,--gc-sections', '-Wl,-static', *objects, '-lgcc', '-o', elf])
run([args.stripios.resolve(), elf, OUT/'SKYLANDERS.app'])
if args.module_only:
    data = (OUT/'SKYLANDERS.app').read_bytes()
    print('SKYLANDERS.app', len(data), hashlib.sha256(data).hexdigest())
    raise SystemExit(0)
ppcflags = ['-DGEKKO', '-mrvl', '-mcpu=750', '-meabi', '-mhard-float']
run([PPC, *ppcflags, '-O2', '-Wall', '-I'+str(SDK/'libogc/include'),
     '-c', ROOT/'probe/source/main.c', '-o', OUT/'probe.o'])
run([PPC, *ppcflags, OUT/'probe.o', '-L'+str(SDK/'libogc/lib/wii'),
     '-lfat', '-lwiiuse', '-lbte', '-logc', '-lm', '-o', OUT/'probe.elf'])
run([SDK/'tools/bin/elf2dol.exe', OUT/'probe.elf', OUT/'boot.dol'])
for name in ['SKYLANDERS.app','SKYLANDERS.elf','boot.dol','probe.elf']:
    data=(OUT/name).read_bytes()
    print(name, len(data), hashlib.sha256(data).hexdigest())
