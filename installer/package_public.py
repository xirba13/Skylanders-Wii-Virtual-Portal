'''Build firmware-free public release archives from verified homebrew inputs.
Both archives include the unchanged, hash-verified tested installer executable.
'''
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PORTAL = '1c6899e72762c8acd6c92d194d69baba077921541fd6101c7fb72cc44e0d13f1'
VWII_BOOT = '9658fa27391585581156bd64ce055c6daff2623c34dfd6ff36be54dbb481a65b'
ICON = '25edf68c27aac00d6579af03a637a375b135d4e8d8ada8f686274b860691f255'
VWII_SOURCE = '4212f0caa25328e824b85eadc28eb6665d78f2ddd4d02f8ad6a8c25d3cde23cd'

def sha(data): return hashlib.sha256(data).hexdigest()
def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
def write(dst, text):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding='utf-8', newline='')
def unzip_source(z, dst, prefix=''):
    for name in z.namelist():
        if name.endswith('/') or not name.startswith(prefix): continue
        rel = Path(name[len(prefix):])
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe archive path')
        target = dst/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(name))

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sd', type=Path, required=True)
parser.add_argument('--d2x-source', type=Path, required=True)
parser.add_argument('--vwii-source', type=Path, required=True)
parser.add_argument('--cios-lib', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--git', default='git')
a = parser.parse_args()
if a.output.exists(): raise SystemExit('Use a new output directory')
expected = json.loads((ROOT/'installer/wii/expected.json').read_text())
assert sha(a.vwii_source.read_bytes()) == VWII_SOURCE, 'Wrong vWii source archive'
with zipfile.ZipFile(a.vwii_source) as z:
    assert sha(z.read('hbc/d2x-cios-installer/boot.dol')) == VWII_BOOT
assert sha(a.d2x_source.read_bytes()) == '5c7cb5edf70f7f70a5896b37b160857d59bfff0835e6a3f1c73a5936c23733e0', 'Wrong d2x source archive'
with zipfile.ZipFile(a.d2x_source) as z:
    assert z.namelist()[0].startswith('d2x-cios-d2x-v11-beta3/'), 'Wrong d2x source tag'
# This allowlist never scans or copies the user's game/library/WAD files.
project = subprocess.check_output([a.git, '-C', str(ROOT), 'ls-files'], text=True).splitlines()
project = [p for p in project if not p.startswith(('work/', 'outputs/', 'evidence/', 'patches/experimental-sync-copy/'))
           and (not p.startswith('docs/') or p in {'docs/BUILD.md','docs/INSTALLATION.md','docs/PUBLIC-RELEASE.md','docs/RELEASE-PACKAGES.md'})]
for rel in project:
    assert Path(rel).suffix.lower() not in {'.wad','.dol','.app','.bin','.iso','.rvz','.sav0','.sav1','.png'}, rel
assets = []
for platform in ['Wii', 'vWii']:
    key = platform.lower()
    folder = 'skylanders-portal-installer-'+key
    package = a.output/('Skylanders-Portal-1.2-'+platform)
    source_app = a.sd/'apps'/folder
    app = package/'SD/apps'/folder
    group = 'SkylandersWii' if key == 'wii' else 'Skylanders'
    config = ROOT/'installer/wii' if key == 'wii' else ROOT/'installer'
    for name in ['meta.xml','ciosmaps.xml']: copy(config/name, app/name)
    assert sha((source_app/'icon.png').read_bytes()) == ICON
    copy(source_app/'icon.png', app/'icon.png')
    for name, digest in {**expected['modules'], 'SKYLANDERS.app': PORTAL}.items():
        data = (source_app/group/name).read_bytes()
        assert sha(data) == digest, name
        copy(source_app/group/name, app/group/name)
    xml = ET.parse(app/'ciosmaps.xml').getroot()
    g = xml.find('ciosgroup')
    assert g.get('name') == group
    assert {c.get('module')+'.app' for c in g.iter('content') if c.get('module')} == set(expected['modules']) | {'SKYLANDERS.app'}
    if key == 'vwii':
        assert sha((source_app/'boot.dol').read_bytes()) == VWII_BOOT
        copy(source_app/'boot.dol', app/'boot.dol')
        with zipfile.ZipFile(a.vwii_source) as z:
            unzip_source(z, package/'source/upstream/installer-vwii', 'sources/')
            write(package/'source/upstream/installer-vwii/LICENSE.txt', z.read('license.txt').decode())
    else:
        assert sha((source_app/'boot.dol').read_bytes()) == expected['installer_sha256']
        copy(source_app/'boot.dol', app/'boot.dol')
    for rel in project: copy(ROOT/rel, package/'source/project'/rel)
    with zipfile.ZipFile(a.d2x_source) as z:
        unzip_source(z, package/'source/upstream/d2x', 'd2x-cios-d2x-v11-beta3/')
    for p in a.cios_lib.iterdir():
        if p.is_file() and (p.suffix in {'.c','.h','.s','.txt'} or p.name=='CMakeLists.txt'):
            copy(p, package/'source/upstream/cios-lib'/p.name)
    for name in ['apply_dol_patch.py','prepare_library.py','prepare_e11_library.py','extend_library.py']:
        copy(ROOT/'pc-debug'/name, package/'PC-tools'/name)
    for p in (ROOT/'patches').glob('*.json'): copy(p, package/'patches'/p.name)
    copy(ROOT/'LICENSE', package/'LICENSES/Project-GPL-3.0.txt')
    copy(ROOT/'THIRD-PARTY-NOTICES.md', package/'LICENSES/THIRD-PARTY-NOTICES.md')
    with zipfile.ZipFile(a.vwii_source) as z:
        write(package/'LICENSES/Installer-GPL-2.0.txt', z.read('license.txt').decode())
    write(package/'LICENSES/README.md', 'Original project contributions: GPL-3.0-or-later. Upstream d2x, installer and cIOS-library notices retain their original terms. Full source and component notices are under source/. Do not remove source/ or LICENSES/ when redistributing this release. Both tested installer binaries are included. See SOURCE-PROVENANCE.md for the unresolved exact-source provenance of Wii 3.1-mod; do not mistake this package for a completed license-compliance audit.\n')
    base = '5918' if key == 'wii' else '6175'
    first = f'1. This package contains the tested {platform} installer. No PC installer download or setup script is needed.\n'
    firmware = ('The Wii installer can obtain base IOS57 v5918 from Nintendo using its normal network installation. If network installation fails, supply your own verified `IOS57-64-v5918.wad` at the SD root. Neither firmware nor a WAD downloader is included.\n'
                if key == 'wii' else 'The FIX94 vWii installer uses the base IOS installed on your own vWii NAND. Keep IOS57 v6175 present and unmodified. No Nintendo firmware is bundled; do not substitute Wii firmware.\n')
    revision = 'Select cIOS revision **21999**.' if key == 'wii' else 'The tested installer has **no revision selector**.'
    write(package/'START-HERE.md', f'''# Skylanders Portal 1.2 — {platform} ONLY

For {'an original Wii, not Wii U vWii or Wii mini' if key == 'wii' else 'Wii U vWii, not an original Wii'}.

{first}2. Copy the **contents of SD/** to the root of your SD card. Only the project app is added. Do not copy the enclosing SD folder itself. Keep existing figure libraries and saves.
3. Your console must already have Homebrew Channel and an appropriate recovery/NAND backup. Open **Skylanders Portal - {platform} ONLY**.
4. Select **{group} → base 57 v{base} → slot 252** (ensure the slot is available). {revision} Wait for successful installation. Leave system IOSes and other cIOS slots unchanged.

{firmware}
## Game menus and figures

Install USBLoaderGX separately from https://github.com/wiidev/usbloadergx/releases . It is not bundled. The following steps require Python 3, your own games and your own 1024-byte `.dump` figure files.

For a new figure library:

```text
python PC-tools/prepare_library.py path/to/your-dumps path/to/new-library
```

Copy the resulting files to `sd:/skylanders/e11/`. For an existing library use `PC-tools/extend_library.py` instead, preserving indices and saves. Never replace a working catalogue with a newly generated one without preserving its source IDs.

Extract the original main.dol from your own game and apply its matching patch, for example:

```text
python PC-tools/apply_dol_patch.py patches/SKYZ52.patch.json path/to/main.dol SKYZ52.dol
```

Copy `<gameID>.dol` to the SD root. Supported outer-disc versions: SSA **SSPP52 rev2**, Giants **SKYZ52 rev0**, Swap Force **SVXI52 rev0**, Trap Team **SK8I52 rev0**, SuperChargers Racing **SKNP52 rev0**. The patcher checks exact original DOL hashes. Each game needs its own patch. No complete game executable is supplied.

In USBLoaderGX set **Game IOS 252**, **Alternate DOL from SD/USB**, path **sd:/**, **Ocarina off**, **Hooktype none**, **debugger off**. The menu comes from the game patch, not the cIOS alone.

Open with **Plus+Minus** on either player's Wii Remote. D-pad browses; A loads; B closes; Nunchuk C/Z selects one of 16 slots; Minus alone then release removes; **1 saves to SD**; 2 rescans. Wait for saved status before quitting. Background saving is already implemented, and pending changes are saved before figure replacement/removal. Save Now requests an immediate flush; wait for completion before powering off. Original dumps remain unchanged; save journals are separate. Use compatible figures and separate slots for Swap halves or vehicles.

Both console versions were owner-tested on European hardware in slot252. Other slots should work with matching Game IOS settings, but are untested. Later-game menus hold the background, not gameplay; portal speaker audio is not played.

## Release contents and licensing

The runtime matches the accepted 1.2 build. See `source/project/README.md` for the full guide and credits to ChatGPT 5.6 Sol and ChatGPT 6 Astra. See `SOURCE-PROVENANCE.md` and LICENSES/. No Nintendo base IOS/WAD, game image, complete game DOL, figure dump or save journal is bundled. `RELEASE-MANIFEST.json` records the distributed file hashes.

This is an unofficial homebrew project. Do not cross-install the two platform packages.
''')
    write(package/'SOURCE-PROVENANCE.md', f'''# Sources and reproducibility

- Portal binary SHA256: `{PORTAL}`. Built from the project source included in source/project. Original contributions: GPL-3.0-or-later.
- d2x modules: unmodified d2x-v11-beta3 components, source tag commit `33ad1eeeb8f562df99e7d7ca428fdd36e0e31be7`, included in source/upstream/d2x. Upstream: https://github.com/wiidev/d2x-cios/releases/tag/d2x-v11-beta3 . Source ZIP SHA256 `{sha(a.d2x_source.read_bytes())}`. Its build scripts and per-component notices are retained.
- Portal-linked cIOS library: exact local source files used by the tested build, included in source/upstream/cios-lib; from FAKEMOTE's embedded-game-controller dependency, https://github.com/embedded-game-controller/embedded-game-controller . Individual files retain authors and GPL-2.0-or-later notices. The linked d2x isfs.c matches the above tag after line-ending normalization.
- vWii installer: FIX94 Mod2.2 original archive https://www.mediafire.com/file/6bmthtyas3q17cr/ , SHA256 `{VWII_SOURCE}`. The archive pairs source and binary; boot.dol exactly matches `{VWII_BOOT}`. Its source (including original embedded homebrew module data and public certificate resource) is included in the vWii package. Source notices and GPLv2 license retained. Only external map/meta labels are customized; installer executable is unchanged.
- Wii installer: official d2x-v11-beta3 asset, boot.dol SHA256 `f46f7ff56cb1b152e79a91e41dab0e553eb9d9df3a05a93ee60a44d3c6374131`. Source for this exact 3.1-mod binary could not be verified. It is included unchanged from the owner-tested SD installer, as requested. The old 3.1 source mirror is not presented as corresponding source. Exact corresponding-source availability and associated distribution obligations remain unresolved; the presence of GPL notices is not a claim that this audit is complete.

## Rebuild the portal

Use devkitPro/devkitARM and a native C++ compiler. Compile `source/upstream/d2x/stripios_src/main.cpp` into a local stripios executable (for example `g++ main.cpp -o stripios`). Then, from this package root on Windows:

```text
python source/project/pc-debug/build_windows.py --multi-slot --module-only --sdk C:/devkitPro --cios-lib source/upstream/cios-lib --d2x-lib source/upstream/d2x/source/cios-lib --stripios path/to/stripios.exe --out C:/absolute/path/to/new-build
```

The accepted ARM compiler was devkitARM as recorded in BUILD-TOOLS.txt. Different compiler versions may produce different bytes. The source-only rebuild does not require Nintendo firmware or figure data. The d2x module source uses its upstream build scripts/toolchain; the vWii installer uses its supplied Makefile and historical devkitPPC/libogc environment. Installer/legacy-module bit-for-bit rebuilds were not performed here. Do not mistake a runtime portal rebuild for an installer rebuild.

Upstream homebrew resource files under the installer source are retained as part of its published source distribution. The source package does not contain your console's private keys or a dumped IOS. Keep source and notices alongside binaries when redistributing.
''')
    tools = subprocess.check_output(['C:/devkitPro/devkitARM/bin/arm-none-eabi-gcc.exe','--version'], text=True)
    write(package/'BUILD-TOOLS.txt', tools)
    manifest = {p.relative_to(package).as_posix(): sha(p.read_bytes()) for p in package.rglob('*') if p.is_file()}
    assert not any(Path(p).suffix.lower() in {'.wad','.iso','.wbfs','.rvz','.dump','.sav0','.sav1'} for p in manifest)
    dols = [p for p in manifest if p.lower().endswith('.dol')]
    assert dols == ['SD/apps/'+folder+'/boot.dol']
    write(package/'RELEASE-MANIFEST.json', json.dumps({'platform':platform,'version':'1.2','wii_setup_required':False,'files':manifest}, indent=2)+'\n')
    archive = Path(str(package)+'.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in package.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(package).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for rel,h in manifest.items(): assert sha(z.read(rel)) == h
    assets.append({'file':archive.name,'sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size})
write(a.output/'SHA256SUMS.txt',''.join(x['sha256']+'  '+x['file']+'\n' for x in assets))
print(json.dumps(assets,indent=2))
