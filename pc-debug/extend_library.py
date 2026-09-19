"""Append dumps without changing existing indices, source files or save journals."""
from pathlib import Path,PureWindowsPath
import argparse,hashlib,json,struct,unicodedata,shutil
from prepare_e11_library import fnv

def extend(source,existing,dest):
    if dest.exists():raise ValueError('Use a new destination directory')
    entries=json.loads((existing/'library.json').read_text())
    cat=(existing/'catalog.bin').read_bytes();magic,count,digest=struct.unpack_from('>III',cat)
    stride={0x45313143:64,0x45313443:32,0x45313543:24}.get(magic,0)
    if magic not in (0x45313143,0x45313443,0x45313543) or len(cat)!=16416 or count!=len(entries) or count>({64:256,32:512,24:640}[stride]) or fnv(cat[32:32+count*stride])!=digest:
        raise ValueError('Existing catalogue failed validation')
    paths=set();data=[]
    for i,e in enumerate(entries):
        b=(existing/f'fig{i:03d}.bin').read_bytes();h=hashlib.sha256(b).hexdigest()
        if e['index']!=i or len(b)!=1024 or h!=e['sha256'] or fnv(b)!=e['fnv']:raise ValueError('Existing figure mismatch')
        offset=32+i*stride+(4 if stride==64 else 0)
        if struct.unpack_from('>I',cat,offset)[0]!=fnv(b):raise ValueError('Catalogue source hash mismatch')
        paths.add(PureWindowsPath(e['source']).as_posix().casefold());data.append(b)
    old_count=len(entries)
    for p in sorted(source.rglob('*.dump'),key=lambda p:str(p.relative_to(source)).casefold()):
        rel=p.relative_to(source);b=p.read_bytes()
        if len(b)!=1024:raise ValueError('Not a 1024-byte figure: '+str(rel))
        key=rel.as_posix().casefold()
        if key in paths:
            old=next(e for e in entries if PureWindowsPath(e['source']).as_posix().casefold()==key)
            if hashlib.sha256(b).hexdigest()!=old['sha256']:raise ValueError('Existing source changed: '+str(rel))
            continue
        group={'1.':'SSA','2.':'GIANTS','3.':'SWAP','4.':'TRAP','5.':'SC'}.get(rel.parts[0][:2],'FIGURE')
        label=group+' '+p.stem
        if group=='SWAP':
            for part,short in [(' Bottom','BOT'),(' Top','TOP')]:
                if p.stem.endswith(part):label='SWAP '+short+' '+p.stem[:-len(part)]
        label=unicodedata.normalize('NFKD',label).encode('ascii','ignore').decode().upper()
        entries.append(dict(index=len(entries),name=label,source=str(rel),sha256=hashlib.sha256(b).hexdigest(),fnv=fnv(b),figure_id=int.from_bytes(b[16:18],'little'),variant=int.from_bytes(b[28:30],'little')))
        paths.add(key);data.append(b)
    if len(entries)>640:raise ValueError('More than640 figures; nothing written')
    labels=[e['name'][:19] for e in entries]
    # Stable suffixes make every abbreviated label distinguishable.
    for i,e in enumerate(entries):e['display_name']=labels[i] if labels.count(labels[i])==1 else labels[i][:15]+f' {i:03d}'
    if len({e['display_name'] for e in entries})!=len(entries):raise ValueError('Display label collision')
    cat=bytearray(16416)
    for i,e in enumerate(entries):
        o=32+i*24;struct.pack_into('>I',cat,o,e['fnv']);label=e['display_name'].encode();cat[o+4:o+4+len(label)]=label
    struct.pack_into('>III',cat,0,0x45313543,len(entries),fnv(cat[32:32+len(entries)*24]))
    dest.mkdir(parents=True)
    for i,b in enumerate(data):(dest/f'fig{i:03d}.bin').write_bytes(b)
    for p in existing.iterdir():
        if p.suffix in ('.sav0','.sav1'):shutil.copyfile(p,dest/p.name)
    (dest/'catalog.bin').write_bytes(cat);(dest/'library.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
    print(f'Preserved{old_count} figure indices; added{len(entries)-old_count}; total{len(entries)}')
    return entries

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('existing',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();extend(a.source,a.existing,a.destination)
