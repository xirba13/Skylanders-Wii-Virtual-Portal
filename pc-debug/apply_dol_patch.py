"""Apply a fingerprint-checked menu patch without a compiler or game distribution."""
import argparse
import hashlib
import json
from pathlib import Path

def apply_patch(original, patch):
    if patch.get('format') != 'skylanders-dol-patch-v1':
        raise ValueError('Unsupported patch format')
    if len(original) != patch['input_size'] or hashlib.sha256(original).hexdigest() != patch['input_sha256']:
        raise ValueError('Wrong original DOL: game/revision mismatch or already patched')
    size = patch['output_size']
    if not len(original) <= size <= len(original) + 0x2000:
        raise ValueError('Invalid output size')
    result = bytearray(original) + bytes(size - len(original))
    end = 0
    for write in patch['writes']:
        offset, data = write['offset'], bytes.fromhex(write['hex'])
        if offset < end or offset + len(data) > size or not data:
            raise ValueError('Invalid or overlapping patch range')
        result[offset:offset + len(data)] = data
        end = offset + len(data)
    if hashlib.sha256(result).hexdigest() != patch['output_sha256']:
        raise ValueError('Patched output hash mismatch')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', type=Path)
    parser.add_argument('original_dol', type=Path)
    parser.add_argument('output_dol', type=Path)
    args = parser.parse_args()
    try:
        result = apply_patch(args.original_dol.read_bytes(), json.loads(args.patch.read_text()))
        # Exclusive creation also protects the original and existing output files.
        with args.output_dol.open('xb') as output:
            output.write(result)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print('Created ' + str(args.output_dol))

if __name__ == '__main__':
    main()
