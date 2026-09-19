"""Create a new current-format library from private 1024-byte .dump files."""
from pathlib import Path
import argparse, json, struct, tempfile
from extend_library import extend
from prepare_e11_library import fnv

def prepare(source, destination):
    if not any(source.rglob('*.dump')):
        raise ValueError('No .dump files found')
    with tempfile.TemporaryDirectory() as tmp:
        seed = Path(tmp)
        catalogue = bytearray(16416)
        struct.pack_into('>III', catalogue, 0, 0x45313543, 0, fnv(b''))
        (seed/'catalog.bin').write_bytes(catalogue)
        (seed/'library.json').write_text('[]')
        return extend(source, seed, destination)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
