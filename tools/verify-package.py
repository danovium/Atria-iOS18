#!/usr/bin/env python3
"""Inspect a rootless Atria package and verify Mach-O page hashes on Linux/macOS."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile


spec = importlib.util.spec_from_file_location('verify_arm64e', Path(__file__).with_name('verify-arm64e.py'))
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def u32(data, offset, endian='<'):
    return struct.unpack_from(endian + 'I', data, offset)[0]


def verify_signature(thin, offset, size):
    blob = thin[offset:offset + size]
    if u32(blob, 0, '>') != 0xfade0cc0:
        raise ValueError('Missing embedded signature superblob')
    verified = []
    for i in range(u32(blob, 8, '>')):
        kind, start = struct.unpack_from('>II', blob, 12 + i * 8)
        if kind != 0 and not 0x1000 <= kind < 0x1005:
            continue
        cd = blob[start:]
        if u32(cd, 0, '>') != 0xfade0c02:
            raise ValueError('Invalid CodeDirectory')
        hash_offset = u32(cd, 16, '>')
        slots = u32(cd, 28, '>')
        limit = u32(cd, 32, '>')
        hash_size, hash_type, platform, page_shift = struct.unpack_from('4B', cd, 36)
        if u32(cd, 8, '>') >= 0x20300 and not limit:
            limit = struct.unpack_from('>Q', cd, 56)[0]
        hash_name = {1: 'sha1', 2: 'sha256', 3: 'sha256', 4: 'sha384'}[hash_type]
        page_size = 1 << page_shift
        if slots != (limit + page_size - 1) // page_size or limit > offset:
            raise ValueError('Invalid code-signature page bounds')
        for page in range(slots):
            block = thin[page * page_size:min((page + 1) * page_size, limit)]
            actual = hashlib.new(hash_name, block).digest()[:hash_size]
            expected = cd[hash_offset + page * hash_size:hash_offset + (page + 1) * hash_size]
            if actual != expected:
                raise ValueError(f'Code-signature page {page} hash mismatch')
        verified.append(dict(hash=hash_name, pages=slots))
    if not verified:
        raise ValueError('No CodeDirectory was verified')
    return verified


def inspect_binary(path):
    data = path.read_bytes()
    if data[:4] != b'\xca\xfe\xba\xbe':
        raise ValueError(f'{path.name} is not a universal Mach-O')
    results = {}
    for i in range(u32(data, 4, '>')):
        cpu, subtype, offset, size, align = struct.unpack_from('>IIIII', data, 8 + i * 20)
        name = {0: 'arm64', 2: 'arm64e'}.get(subtype & 0xffffff)
        if cpu != 0x100000c or name is None or offset + size > len(data):
            raise ValueError('Unexpected architecture or invalid slice bounds')
        thin = data[offset:offset + size]
        if u32(thin, 0) != 0xfeedfacf or u32(thin, 4) != cpu:
            raise ValueError('Invalid 64-bit Mach-O header')
        if u32(thin, 8) & 0xffffff != subtype & 0xffffff:
            raise ValueError('Slice subtype does not match universal header')
        libs, rpaths, signature = [], [], None
        cursor = 32
        for n in range(u32(thin, 16)):
            cmd, length = struct.unpack_from('<II', thin, cursor)
            if length < 8 or cursor + length > len(thin):
                raise ValueError('Invalid load command')
            if cmd in (0xc, 0xd, 0x80000018, 0x8000001f, 0x80000023):
                start = cursor + u32(thin, cursor + 8)
                libs.append(thin[start:cursor + length].split(b'\0')[0].decode())
            elif cmd == 0x8000001c:
                start = cursor + u32(thin, cursor + 8)
                rpaths.append(thin[start:cursor + length].split(b'\0')[0].decode())
            elif cmd == 0x1d:
                signature = struct.unpack_from('<II', thin, cursor + 8)
            cursor += length
        if not signature:
            raise ValueError(f'{name} has no embedded signature')
        results[name] = dict(libraries=libs, rpaths=rpaths,
                             signatures=verify_signature(thin, *signature),
                             cpu_subtype=hex(u32(thin, 8)))
        if name == 'arm64e':
            results[name]['authenticated_objc'] = abi.inspect_arm64e(thin)
    if set(results) != {'arm64', 'arm64e'}:
        raise ValueError('Both arm64 and arm64e slices are required')
    return dict(sha256=hashlib.sha256(data).hexdigest(), slices=results)


def main():
    package = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    control = run('dpkg-deb', '-f', str(package))
    (out / 'control.txt').write_text(control)
    (out / 'contents.txt').write_text(run('dpkg-deb', '-c', str(package)))
    if run('dpkg-deb', '-f', str(package), 'Architecture').strip() != 'iphoneos-arm64':
        raise ValueError('Expected a rootless iphoneos-arm64 package')
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        run('dpkg-deb', '-x', str(package), tmp)
        library = Path(tmp) / 'var/jb/Library'
        for label, relative in (('tweak', 'MobileSubstrate/DynamicLibraries/Atria.dylib'),
                                ('preferences', 'PreferenceBundles/AtriaPrefs.bundle/AtriaPrefs')):
            binary = library / relative
            result = inspect_binary(binary)
            results[label] = result
            for slice in result['slices'].values():
                if '/var/jb/usr/lib' not in slice['rpaths']:
                    raise ValueError('Missing rootless library rpath')
                if label == 'preferences' and '@rpath/libcolorpicker.dylib' not in slice['libraries']:
                    raise ValueError('Missing colorpicker linkage')
        count = 0
        for file in Path(tmp).rglob('*.plist'):
            plistlib.loads(file.read_bytes())
            count += 1
        results['property_lists_parsed'] = count
        filter = plistlib.loads((library / 'MobileSubstrate/DynamicLibraries/Atria.plist').read_bytes())
        if filter != {'Filter': {'Bundles': ['com.apple.springboard']}}:
            raise ValueError('Unexpected tweak injection filter')
    results['package_sha256'] = hashlib.sha256(package.read_bytes()).hexdigest()
    results['runtime_validated'] = False
    (out / 'verification.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: rootless paths, both architectures, native arm64e ObjC fixups, linkage, plists, and signature hashes.')
    print('Runtime compatibility still requires device testing.')


if __name__ == '__main__':
    main()
