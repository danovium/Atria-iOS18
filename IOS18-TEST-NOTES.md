# Atria iOS 18 test4

Experimental rootless build; device validation is still required.

## Crash addressed

The supplied `TweakSettings-2026-10-26-115616.txt` records iOS 18.5 (22F76),
iPad12,1, and a main-thread EXC_BREAKPOINT/SIGTRAP with a pointer authentication
trap while `NSBundle` loads `AtriaPrefs`. The Objective-C runtime fails in
`class_data_bits_t::safe_ro()` / `readClass()`, with registers pointing to
`ARIRootListController` and its class-data field. No preference controller
method appears above that loader failure. The logged AtriaPrefs UUID,
`4804a589-d67d-3da6-8457-f44be0b48111`, exactly matches the saved test3
package, tying the failure to that build.

Test3's experimental allemande conversion authenticated isa, superclass, and
method-list pointers but left the class RO-data pointer unsigned. Modern
arm64e Objective-C uses address-diversified DA authentication for that field
(discriminator 0x61f8). The crash location and unsigned field are consistent
with this failure; a device retest is needed to confirm the diagnosis.

Test4 removes binary ABI conversion and rebuilds both Atria and AtriaPrefs
with native arm64e metadata from upstream clang 21.1.8. Both arm64 and arm64e
slices remain included. The source-level iOS 18 startup/widget changes from
test3 are retained. No preferences reset or migration is performed.

## Sources

- Atria: `s-gdn/Atria-iOS17`, commit `1bdec9745bccb1eecd6e13b65579d2cba611de8d`.
- iOS 18.2 reference: `EthanArbuckle/iPhone17-1_18.2_22C152_Restore`,
  tree/commit `e26ed4563f78871c59d2d96856756a65d62517e5`, SpringBoardHome.framework.
- Compiler: official apt.llvm.org Debian 12 clang 21.1.8 packages, with exact
  package versions, paths and SHA256 hashes in `tools/linux-toolchain-packages.json`.
- Objective-C signing schemas cross-checked against LLVM 21.1.8
  `clang/lib/CodeGen/CGObjCMac.cpp` and Apple objc4-940.4 runtime sources.

The earlier startup and test2 patches provided the starting specification.
The original SpringBoard crash attachment was inaccessible as text; its
reported diagnosis remains based on those patch notes. This new TweakSettings
crash log was available as text and examined directly.

## Linux build

Use x86_64 Debian 12-compatible Linux with Theos and iPhoneOS16.5.sdk installed.
The local installer requires curl-equivalent HTTPS access through Python,
`dpkg-deb`, and the usual Debian runtime libraries used by official LLVM packages.
It writes only `.toolchain/` in this checkout and uses Theos's existing
linker, signing tools, and SDK. The compiler download is about 42 MB and the
extracted toolchain about 200 MB. The installer checks checksums and compiles
an Objective-C probe to require native versioned arm64e AND authenticated
class RO-data/method-list metadata; a versioned Mach-O header alone is insufficient.

```sh
python3 tools/build-low-memory.py -- python3 tools/setup-linux-toolchain.py
python3 tools/build-low-memory.py clean
python3 tools/build-low-memory.py package Atria_USE_MODULES=0 AtriaPrefs_USE_MODULES=0
python3 tools/verify-package.py packages/me.lau.atria_1.4.1-sgdnfix2+ios18test4_iphoneos-arm64.deb build-report
```

On macOS, build with a modern Xcode/Theos toolchain; the Linux installer is
not used. The ABI verifier currently checks the chained-fixup encoding emitted
by the Linux build (arm64e formats 1, 9, 12 with a single chain start per page).

The Makefiles disable Theos parallel building and pass `-mllvm -threads=1` to
both targets. The guard forces `make -j1`, pins the build to one CPU, and sets
common worker/compressor variables to one. It uses xz compression level 1,
one compressor thread, and a 128 MiB compression allocation ceiling.
Build-session RSS and total container memory are polled every 20 ms; the build
is killed at 400,000,000 and 470,000,000 bytes respectively, leaving headroom
below the requested 500,000,000-byte budget. The compiler is stopped if more
than one compiler thread is observed. LLVM virtual address space is allowed
to exceed physical RAM use. The read-only container kernel limit remains
512 MiB; this is a watchdog with sampling limits, not a new 500 MB kernel cap.

`build-report/resources.json` records actual measured build peaks. The package
verifier checks rootless paths, both slices, code-signature page hashes,
linked libraries, plists, the native arm64e ABI marker, and reachable dyld
fixups with the expected authentication for every class/metaclass isa,
superclass, class RO-data pointer, and nonempty class method-list pointer.
The old test3 package must fail this ABI check. These static checks cannot
establish device compatibility.

## Source changes retained from test3

Startup probes for ShyLabels and Zenith use POSIX `access()`; Zenith hooks
require a successful `dlopen()`. The old inline `_gridSizeClassSizes` struct
write and integer widget ABI are disabled on iOS 18. Separate object-based
hooks use `gridSizeClassSizesWithOptions:` and `SBHIconGridSizeClassSizeMap`,
with bounded widget footprints, per-layout cache keys, and original grid
baselines. Widget centering and offsets use the iOS 18 NSString grid classes
and `originForIconAtCoordinate:metrics:options:`, guarded by runtime signature
and selector checks. Dock appearance refresh calls `setBackgroundAlpha:` with
a floating-point argument on the main queue. The SpringBoard-only injection
filter, explicit framework linkage, and dual-architecture outputs remain.

## Recorded Linux validation

The clean test4 build completed without compiler/linker warnings. Both
architectures built with one compiler thread; measured peak build-session RSS
was 177,815,552 bytes and peak container memory was 283,095,040 bytes.
Package/signature/plist/linkage checks passed. The ABI verifier confirmed 38
authenticated class/metaclass RO pointers and 24 nonempty method-list pointers
across the tweak and preference bundle. It rejected test3, test3 with only its
ABI header changed, and mutations that remove authentication/address diversity
or change the key/discriminator. The test4 preferences arm64e UUID is
`9af0f3ea-b52a-39a2-afd1-e2acf8433ce1`.

## Device validation

Install test4 over test3 and first open Atria in TweakSettings. Verify that the
preference page loads before testing SpringBoard startup, layout editing,
page-specific layouts, widget resizing/offsets, and portrait/landscape changes.
This iPad/iOS 18.5 configuration may differ from the iPhone/iOS 18.2 reference.
If it still crashes, send the new crash log as `.txt` and note which action
triggered it. iOS 19/26 compatibility is not claimed.
