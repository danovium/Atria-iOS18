# Atria iOS 18 experimental port
Based on the s-gdn iOS 17 fork, with the supplied startup fixes and new iOS 18 widget interfaces.

made by AI. no support will be provided

Tested on iOS 18.5 with Dopamine 3.0.11

# Bugs
- yeah
- what did u even expect its just ai slop


# Installation (it's weird)
- Install TweakSettings and Atria
- Before respring, disable Tweak Injection
- Open TweakSettings and turn off everything except Main Toggle and Layout Modifications
- Re-enable Tweak Injection and re-enable the disabled Settings

# Credits
 - https://github.com/s-gdn/Atria-iOS17 (base)
 - https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore (springboard binary)
 - pengubow (made verity bot linked to gpt)
 - chatgpt (making a slop port even sloppier)
   
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
