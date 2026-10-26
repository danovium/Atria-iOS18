# Atria iOS 18 experimental port
Based on the s-gdn iOS 17 fork, with the supplied startup fixes and new iOS 18 widget interfaces.

The test4 iOS 18 build uses native arm64e compilation and addresses the test3 preference-loader authentication failure. It is experimental and has not been tested on a device. See `IOS18-TEST-NOTES.md` for changes, Linux resource limits, build instructions, and validation limits. iOS 26 is unsupported.

Open this in browser to add my repo: https://s-gdn.github.io/repo.html

## Building

This fork includes a GitHub Actions workflow for building Atria
using Theos on a macOS runner.

To build your own copy:

1. Fork this repository.
2. Open the Actions tab and enable workflows.
3. Run the build workflow.
4. Download the generated `.deb` from the workflow artifacts.

The resulting package is intended for rootless / roothide jailbreaks.
Compatibility has only been confirmed on iOS 17.1.1 - 17.3.1
