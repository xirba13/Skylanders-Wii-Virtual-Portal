"""E06b build/scope gate; run after build_windows.py and test_control_runtime.py."""
from pathlib import Path
import subprocess
import struct
from skylanders_lab import elf_segments

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'plugin/source/main.c').read_text()
baseline = subprocess.check_output(['C:/Program Files/Git/cmd/git.exe', 'show',
    '6cc8a35:plugin/source/main.c'], cwd=ROOT, text=True)
def without_control(text):
    start = text.index('control_transfer_handler(ipcmessage *message)')
    end = text.index('\nstatic s32 ', start)
    return text[:start] + text[end:]
assert without_control(source) == without_control(baseline), 'unexpected plugin scope change'
probe = (ROOT/'probe/source/main.c').read_text()
assert probe.index('IOS_IoctlAsync(fd, 1') < probe.index('IOS_Ioctl(fd, 0, NULL')
assert 'control_vectors[1].len = 2;' in probe
assert 'control_vectors[1].len = 4;' in probe
assert 'if (async_ret >= 0 && !change_done) goto pending_request;' in probe
assert probe.count('if (interrupt_ret >= 0 && !interrupt_done) goto pending_request;') == 4
assert 'while (1) VIDEO_WaitVSync();' in probe
out = ROOT/'work/e06b-build'
dol = (out/'boot.dol').read_bytes()
assert b'E06b-short-control-v32' in dol
assert len(dol) >= 256
# Every DOL section fits the file; BSS is excluded from file-size checks.
for offset, size in zip(struct.unpack_from('>18I', dol, 0), struct.unpack_from('>18I', dol, 0x90)):
    assert not size or (offset >= 256 and offset + size <= len(dol))
blob = (out/'SKYLANDERS.app').read_bytes()
segments = elf_segments(blob)
for seg in segments:
    assert seg.offset + seg.filesz <= len(blob)
    assert seg.filesz <= seg.memsz
    if seg.flags & 1:
        assert 0x13970000 <= seg.vaddr and seg.vaddr + seg.memsz <= 0x13979000
    else:
        assert 0x13979000 <= seg.vaddr and seg.vaddr + seg.memsz <= 0x13987000
print('PASS: control-only plugin scope; short/no-GETVERSION probe; pending-buffer guards; DOL and ELF bounds')
