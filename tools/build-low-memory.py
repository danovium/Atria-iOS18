#!/usr/bin/env python3
"""Run a Linux build on one CPU; abort below the 500 MB container ceiling."""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

# Leave room for Python, shell, and the bot under the requested 500 MB total.
RSS_LIMIT = 400_000_000
CGROUP_LIMIT = 470_000_000
THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'LZMA_THREADS')


def usage():
    raise SystemExit('Usage: python3 tools/build-low-memory.py [package ...] '
                     'or -- COMMAND [ARG ...]')


def main():
    args = sys.argv[1:] or ['package']
    if args[0] == '--':
        command = args[1:]
        if not command:
            usage()
    else:
        if any(a.startswith(('-j', '--jobs', '-l', '--load-average')) for a in args):
            usage()
        command = ['make', '-j1', 'FINALPACKAGE=1', *args]
    if not hasattr(os, 'sched_setaffinity'):
        raise SystemExit('This resource guard requires Linux CPU affinity and /proc.')
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    env = os.environ.copy()
    env.update({key: '1' for key in THREAD_ENV})
    env.update(MAKEFLAGS='-j1', MFLAGS='-j1', THEOS_USE_PARALLEL_BUILDING='0',
               COPYFILE_DISABLE='1', ZERO_AR_DATE='1', XZ_DEFAULTS='-T1',
               XZ_OPT='-T1 --memlimit-compress=128MiB', ZSTD_NBTHREADS='1',
               DPKG_DEB_THREADS_MAX='1')
    # A virtual-address limit is not a physical RAM limit; LLVM maps shared
    # libraries and reserves address space. Limit allocations and monitor RAM.
    resource.setrlimit(resource.RLIMIT_DATA, (400_000_000, 400_000_000))
    resource.setrlimit(resource.RLIMIT_AS, (1_500_000_000, 1_500_000_000))
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    proc = subprocess.Popen(command, env=env, start_new_session=True)
    peak_rss = peak_cgroup = peak_threads = peak_compiler_threads = 0
    reason = None
    try:
        while proc.poll() is None:
            rss = threads = 0
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    stat = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                    if int(stat[3]) != proc.pid:  # process session ID
                        continue
                    status = (entry / 'status').read_text().splitlines()
                    process_threads = 0
                    for line in status:
                        if line.startswith('VmRSS:'):
                            rss += int(line.split()[1]) * 1024
                        elif line.startswith('Threads:'):
                            process_threads = int(line.split()[1])
                            threads += process_threads
                    if (entry / 'comm').read_text().strip().startswith('clang'):
                        peak_compiler_threads = max(peak_compiler_threads, process_threads)
                except (OSError, ValueError, IndexError, ProcessLookupError):
                    continue
            cgroup_file = Path('/sys/fs/cgroup/memory.current')
            cgroup = int(cgroup_file.read_text()) if cgroup_file.exists() else 0
            peak_rss, peak_cgroup = max(peak_rss, rss), max(peak_cgroup, cgroup)
            peak_threads = max(peak_threads, threads)
            if peak_compiler_threads > 1:
                reason = 'Compiler created more than one thread; stopping the build.'
                break
            if rss >= RSS_LIMIT or cgroup >= CGROUP_LIMIT:
                reason = 'Memory guard stopped the build before the 500 MB ceiling.'
                break
            time.sleep(.02)
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise
    if reason:
        os.killpg(proc.pid, signal.SIGKILL)
    rc = proc.wait()
    report = dict(command=command, cpu=cpu, make_jobs=1,
                  rss_abort_bytes=RSS_LIMIT, cgroup_abort_bytes=CGROUP_LIMIT,
                  peak_build_group_rss_bytes=peak_rss,
                  peak_container_memory_bytes=peak_cgroup,
                  peak_group_threads=peak_threads, peak_compiler_threads=peak_compiler_threads,
                  exit_code=rc,
                  note='20 ms polling guard; kernel cgroup is read-only at 512 MiB.')
    out = Path('build-report')
    out.mkdir(exist_ok=True)
    (out / 'resources.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Build resources: RSS {peak_rss / 1e6:.1f} MB; '
          f'container {peak_cgroup / 1e6:.1f} MB; CPU {cpu}; make -j1.', flush=True)
    if reason:
        raise SystemExit(reason)
    return rc


if __name__ == '__main__':
    sys.exit(main())
