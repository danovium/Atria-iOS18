#!/usr/bin/env python3
"""Install a pinned native arm64e compiler locally; keep Theos's linker/tools."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def check_compiler(compiler):
    source = '''__attribute__((objc_root_class)) @interface Probe
- (int)value;
@end
@implementation Probe
- (int)value { return 1; }
@end
'''
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / 'probe.o'
        args = [str(compiler), '-target', 'arm64e-apple-ios15.0', '-x', 'objective-c', '-']
        subprocess.run([*args, '-c', '-o', str(obj)], input=source, text=True, check=True)
        if int.from_bytes(obj.read_bytes()[8:12], 'little') != 0x80000002:
            raise RuntimeError('Compiler does not emit the versioned arm64e ABI')
        ir = subprocess.check_output([*args, '-S', '-emit-llvm', '-o', '-'], input=source, text=True)
        # Checking the header alone is insufficient: clang 20 lacks ObjC signing.
        if 'i32 2, i64 25080, ptr getelementptr' not in ir:
            raise RuntimeError('Compiler does not authenticate Objective-C class RO pointers')
        if 'i32 2, i64 49936, ptr getelementptr' not in ir:
            raise RuntimeError('Compiler does not authenticate Objective-C method lists')
    print('PASS: native arm64e ABI, authenticated class RO pointers and method lists.')


def main():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise SystemExit('This installer targets Debian 12-compatible Linux x86_64.')
    base = Path(os.environ.get('THEOS', '/opt/theos')) / 'toolchain/linux/iphone/bin'
    if not (base / 'ld').is_file():
        raise SystemExit('Theos Linux iPhone toolchain not found; set THEOS.')
    install = ROOT / '.toolchain'
    llvm = install / 'llvm'
    manifest = (ROOT / 'tools/linux-toolchain-packages.json').read_text()
    stamp = llvm / 'installed-packages.json'
    if not stamp.exists() or stamp.read_text() != manifest:
        llvm.mkdir(parents=True, exist_ok=True)
        for entry in json.loads(manifest):
            print('Installing', entry['Package'], entry['Version'], flush=True)
            with tempfile.NamedTemporaryFile(suffix='.deb', dir=install) as archive:
                digest = hashlib.sha256()
                with urllib.request.urlopen('https://apt.llvm.org/bookworm/' + entry['Filename']) as response:
                    while block := response.read(1024 * 1024):
                        digest.update(block)
                        archive.write(block)
                archive.flush()
                if digest.hexdigest() != entry['SHA256']:
                    raise RuntimeError('Downloaded compiler package checksum mismatch')
                env = dict(os.environ, DPKG_DEB_THREADS_MAX='1', XZ_DEFAULTS='-T1')
                subprocess.run(['dpkg-deb', '-x', archive.name, str(llvm)], env=env, check=True)
        stamp.write_text(manifest)
    tools = install / 'bin'
    tools.mkdir(exist_ok=True)
    for original in base.iterdir():
        if original.name in ('clang', 'clang++', 'cc', 'c++'):
            continue
        target = tools / original.name
        if target.is_symlink():
            target.unlink()
        if not target.exists():
            target.symlink_to(original)
    wrapper = tools / 'clang'
    if wrapper.is_symlink():
        wrapper.unlink()
    wrapper.write_text('''#!/usr/bin/env bash
set -euo pipefail
TOOLS=$(cd -- "$(dirname -- "$0")" && pwd)
LLVM="$TOOLS/../llvm"
export LD_LIBRARY_PATH="$LLVM/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
real="$LLVM/usr/lib/llvm-21/bin/clang"
case "$(basename -- "$0")" in *++) real+="++" ;; esac
args=()
link=1
for arg in "$@"; do
    case "$arg" in
        -c|-E|-S|-fsyntax-only|--version|-dumpversion) link=0; args+=("$arg") ;;
        -fuse-ld=/*) args+=("--ld-path=${arg#-fuse-ld=}") ;;
        *) args+=("$arg") ;;
    esac
done
[ "$link" = 0 ] || args+=("--ld-path=$TOOLS/ld")
exec "$real" "${args[@]}"
''')
    wrapper.chmod(0o755)
    for name in ('clang++', 'cc', 'c++'):
        target = tools / name
        if target.is_symlink():
            target.unlink()
        target.symlink_to('clang')
    check_compiler(wrapper)


if __name__ == '__main__':
    main()
