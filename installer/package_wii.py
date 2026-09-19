"""Package the verified original-Wii candidate; never modifies either SD card."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pc-debug'))
from verify_wii_package import verify
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--base-dir',type=Path,required=True);p.add_argument('--official',type=Path,required=True)
p.add_argument('--portal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
report=verify(a.base_dir,a.official,a.portal)
expected=json.loads((ROOT/'installer/wii/expected.json').read_text())
wad=a.base_dir/'IOS57-64-v5918.wad'
assert hashlib.sha256(wad.read_bytes()).hexdigest()==expected['base_wad_sha256']
if a.output.exists() and any(a.output.iterdir()):raise SystemExit('Output must be new or empty')
app=a.output/'apps/skylanders-portal-installer-wii'
def cp(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
for name in ['boot.dol','icon.png']:cp(a.official/name,app/name)
for name in ['meta.xml','ciosmaps.xml']:cp(ROOT/'installer/wii'/name,app/name)
for name in expected['modules']:cp(a.official/'d2x-v11-beta3'/name,app/'SkylandersWii'/name)
cp(a.portal,app/'SkylandersWii/SKYLANDERS.app');cp(wad,a.output/wad.name)
cp(ROOT/'installer/wii/README.md',a.output/'SKYLANDERS-WII-INSTALLATION.md')
manifest={f.relative_to(a.output).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in a.output.rglob('*') if f.is_file()}
(a.output/'WII-PACKAGE-MANIFEST.json').write_text(json.dumps({'verification':report,'files':manifest},indent=2)+'\n')
print('Wii-only package prepared:',a.output,'verified files:',len(manifest))
