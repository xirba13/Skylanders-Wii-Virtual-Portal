"""Check a Wii-only installer against verified decrypted base contents and modules.
No firmware or keys are stored in the repository; this performs no installation.
"""
from pathlib import Path
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from skylanders_lab import elf_segments,address_to_offset,byte_list
ROOT=Path(__file__).resolve().parents[1]
def verify(base_dir,official,portal):
 expected=json.loads((ROOT/'installer/wii/expected.json').read_text())
 h=lambda b:hashlib.sha256(b).hexdigest()
 contents={rec['cid']:(base_dir/f"{rec['cid']:08x}.app").read_bytes() for rec in expected['contents']}
 for rec in expected['contents']:
  assert len(contents[rec['cid']])==rec['size'] and h(contents[rec['cid']])==rec['sha256']
 root=ET.parse(ROOT/'installer/wii/ciosmaps.xml').getroot();groups=root.findall('ciosgroup')
 assert root.get('ciosgroupscount')=='1' and len(groups)==1
 g=groups[0];assert g.get('name')=='SkylandersWii' and g.get('basescount')=='1'
 bases=g.findall('base');assert len(bases)==1;b=bases[0]
 assert b.get('ios')=='57' and b.get('version')=='5918'
 cs=b.findall('content');assert len(cs)==int(b.get('contentscount'))==26
 ids=[int(c.get('id'),0) for c in cs];assert len(set(ids))==len(ids)
 modules={int(c.get('id'),0):c for c in cs if c.get('module')}
 assert len(modules)==int(b.get('modulescount'))==7
 assert modules[0x23].get('module')=='SKYLANDERS'
 assert {int(c.get('id'),0) for c in cs if not c.get('module')}==set(contents)
 checks=0
 for c in cs:
  if c.get('module'):continue
  data=contents[int(c.get('id'),0)];ranges=[]
  assert len(c.findall('patch'))==int(c.get('patchscount','0'))
  for p in c.findall('patch'):
   o=int(p.get('offset'),0);n=int(p.get('size'),0);old=byte_list(p.get('originalbytes'));new=byte_list(p.get('newbytes'))
   assert n==len(old)==len(new) and data[o:o+n]==old
   assert all(o+n<=a or z<=o for a,z in ranges);ranges.append((o,o+n));checks+=1
 hid=contents[13];assert h(hid)==expected['hid_sha256'];segs=elf_segments(hid)
 for addr,word in {0x13658330:0xebffff74,0x1365834c:0xebffff61,0x13658180:0xeb000217,0x13658fb4:0xe1a0c00d}.items():
  assert struct.unpack_from('>I',hid,address_to_offset(segs,addr,4))[0]==word
 assert h(portal.read_bytes())==expected['portal_sha256']
 assert h((official/'boot.dol').read_bytes())==expected['installer_sha256']
 blobs=list(contents.values())
 for name,digest in expected['modules'].items():
  data=(official/'d2x-v11-beta3'/name).read_bytes();assert h(data)==digest;blobs.append(data)
 regions=[]
 for data in blobs:
  if data[:4]==b'\x7fELF':regions.extend(elf_segments(data))
 for own in elf_segments(portal.read_bytes()):
  for other in regions:
   assert own.vaddr+own.memsz<=other.vaddr or other.vaddr+other.memsz<=own.vaddr,'Portal overlaps existing module'
 return {'platform':'Wii','base':57,'version':5918,'base_contents':len(contents),'map_preimages':checks,'modules':7,'hid_identical_to_vwii':True,'portal_hash':expected['portal_sha256'],'hardware_tested':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('base_dir',type=Path);p.add_argument('official_installer',type=Path);p.add_argument('portal',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
 report=verify(a.base_dir,a.official_installer,a.portal)
 if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
