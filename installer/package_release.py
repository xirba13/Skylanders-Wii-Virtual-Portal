"""Prepare a private SD image from the user's working SD and final DOL builds."""
from pathlib import Path
import argparse,hashlib,json,shutil,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--sd',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];dst=a.output
if dst.exists() and any(dst.iterdir()):raise SystemExit('Output must be a new/empty directory')
def cp(source,target):
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
source=a.sd/'apps/skylanders-portal-installer-vwii';module_folder='Skylanders'
if not source.exists():source=a.sd/'apps/skylanders-portal-installer'
if not source.exists():source=a.sd/'apps/skylanders-e12-installer';module_folder='SkylandersHIDv5'
app=dst/'apps/skylanders-portal-installer-vwii'
for f in ['boot.dol','icon.png']:cp(source/f,app/f)
for f in ['meta.xml','ciosmaps.xml']:cp(r/'installer'/f,app/f)
group=ET.parse(app/'ciosmaps.xml').getroot().find('ciosgroup')
assert group.get('name')=='Skylanders' and group.get('basescount')=='1'
assert [(b.get('ios'),b.get('version')) for b in group.findall('base')]==[('57','6175')]
modules={c.get('module') for c in group.iter('content') if c.get('module')}
for module in modules:cp(source/module_folder/(module+'.app'),app/'Skylanders'/(module+'.app'))
portal=app/'Skylanders/SKYLANDERS.app'
assert hashlib.sha256(portal.read_bytes()).hexdigest()=='1c6899e72762c8acd6c92d194d69baba077921541fd6101c7fb72cc44e0d13f1'
for game in ['SKYZ52','SSPP52','SVXI52','SK8I52','SKNP52']:
 cp(a.build/game/(game+'.dol'),dst/(game+'.dol'))
 assert hashlib.sha256((dst/(game+'.dol')).read_bytes()).hexdigest()==json.loads((a.build/game/'build.json').read_text())['patched_sha256']
for f in ['boot.dol','icon.png','meta.xml','GXGlobal.cfg','GXGameSettings.cfg']:cp(a.sd/'apps/usbloader_gx'/f,dst/'apps/usbloader_gx'/f)
for f in (a.sd/'skylanders/e11').iterdir():
 if f.is_file() and (f.suffix in ['.bin','.sav0','.sav1'] or f.name=='library.json'):cp(f,dst/'skylanders/e11'/f.name)
cp(a.sd/'IOS57-64-v6175.wad',dst/'IOS57-64-v6175.wad')
cp(r/'docs/INSTALLATION.md',dst/'INSTALLATION.md')
manifest={str(f.relative_to(dst)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in dst.rglob('*') if f.is_file()}
(dst/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Private SD package:',dst,'files:',len(manifest))
