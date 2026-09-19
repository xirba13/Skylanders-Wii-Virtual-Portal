"""Prepare an E11 library in a NEW directory, preserving all original dumps."""
from pathlib import Path
import argparse,hashlib,json,re,struct,unicodedata

def fnv(data):
 h=2166136261
 for b in data:h=((h^b)*16777619)&0xffffffff
 return h

def prepare(source,dest):
 files=sorted(source.rglob('*.dump'),key=lambda p:(p.stem.casefold()!='dark spyro',str(p.relative_to(source)).casefold()))
 if not 0<len(files)<=256:raise ValueError('Library must contain 1-256 dumps')
 entries=[];contents=[]
 for i,p in enumerate(files):
  data=p.read_bytes()
  if len(data)!=1024:raise ValueError(f'{p.name}: expected exactly 1024 bytes')
  rel=p.relative_to(source);game='SSA' if rel.parts[0].startswith('1.') else 'GIANTS'
  category=re.sub(r'^\d+\)\s*','',rel.parts[1]) if len(rel.parts)>2 else ''
  label=f'{game} {p.stem}'
  if 'Series 2' in category:label+=' S2'
  if 'LightCore' in category and 'lightcore' not in p.stem.lower():label+=' LIGHTCORE'
  label=unicodedata.normalize('NFKD',label).encode('ascii','ignore').decode().upper()
  # Full original path is retained in library.json for truncated variant names.
  label=label[:47]
  entries.append(dict(index=i,name=label,source=str(rel),sha256=hashlib.sha256(data).hexdigest(),fnv=fnv(data),figure_id=int.from_bytes(data[16:18],'little'),variant=int.from_bytes(data[28:30],'little')))
  contents.append(data)
 names={}
 for e in entries:names[e['name']]=names.get(e['name'],0)+1
 for e in entries:
  if names[e['name']]>1:e['name']=e['name'][:42]+f' {e["index"]:03d}'
 cat=bytearray(32+256*64)
 for e in entries:
  o=32+e['index']*64;struct.pack_into('>II',cat,o,e['index'],e['fnv']);name=e['name'].encode();cat[o+8:o+8+len(name)]=name
 struct.pack_into('>III',cat,0,0x45313143,len(entries),fnv(cat[32:32+len(entries)*64]))
 dest.mkdir(parents=True,exist_ok=False)
 for e,data in zip(entries,contents):(dest/f'fig{e["index"]:03d}.bin').write_bytes(data)
 (dest/'catalog.bin').write_bytes(cat);(dest/'library.json').write_text(json.dumps(entries,indent=2))
 for e in entries:assert hashlib.sha256((dest/f'fig{e["index"]:03d}.bin').read_bytes()).hexdigest()==e['sha256']
 print(f'Prepared and verified {len(entries)} figures; default: {entries[0]["name"]}')
 return entries
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();prepare(a.source,a.destination)
