"""Export current tracked source without private Git history or hardware evidence."""
from pathlib import Path
import argparse, hashlib, json, subprocess, zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', type=Path)
parser.add_argument('--git', default='git')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
if args.destination.exists():
    raise SystemExit('Use a new destination')
files = subprocess.check_output([args.git, '-C', str(root), 'ls-files'], text=True).splitlines()
docs = {'docs/BUILD.md', 'docs/INSTALLATION.md', 'docs/PUBLIC-RELEASE.md', 'docs/RELEASE-PACKAGES.md'}
allowed = {'.py', '.c', '.h', '.s', '.S', '.ld', '.xml', '.json', '.md', '.txt', '.cmd'}
selected = []
for rel in files:
    p = Path(rel)
    if rel.startswith(('evidence/', 'work/', 'outputs/', 'patches/experimental-sync-copy/')):
        continue
    if rel.startswith('docs/') and rel not in docs:
        continue
    if p.suffix not in allowed and p.name not in {'.gitignore', 'Makefile', 'LICENSE', 'COPYING'}:
        raise SystemExit('Unreviewed file type: ' + rel)
    selected.append(rel)
args.destination.mkdir(parents=True)
manifest = {}
for rel in selected:
    source = root / rel
    target = args.destination / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    target.write_bytes(data)
    manifest[rel] = hashlib.sha256(data).hexdigest()
(args.destination/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
archive = Path(str(args.destination) + '.zip')
if archive.exists():
    raise SystemExit('Archive already exists')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in args.destination.rglob('*'):
        if p.is_file():
            z.write(p, p.relative_to(args.destination).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for rel, digest in manifest.items():
        assert hashlib.sha256(z.read(rel)).hexdigest() == digest
print('Verified source export:', archive, 'files:', len(manifest))
