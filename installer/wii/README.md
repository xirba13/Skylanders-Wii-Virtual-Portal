# Original Wii installer

This is the separate original-Wii version of Skylanders Portal1.2. It is not for Wii U vWii or Wii mini. PC verification passes and the owner confirmed operation on a European original Wii, slot 252, on 14 September 2026. The existing vWii release remains unchanged.

## Prepare and install

1. Use an original Wii with Homebrew Channel already installed. Before testing experimental cIOS, have a current NAND backup and the recovery setup appropriate to that Wii.
2. Copy the contents of this package's `SD` folder to your card. It adds `apps/skylanders-portal-installer-wii` and the verified `IOS57-64-v5918.wad`. Do not substitute the older local WAD that failed verification, and do not use the vWii v6175 WAD.
3. The card also needs the existing `skylanders/e11` library, USBLoaderGX and the five matching root game DOLs. The card previously copied to D: already has those shared files. Game images stay on the existing game drive.
4. In Homebrew Channel, open **Skylanders Portal - Wii ONLY**. Do not select the separate vWii installer.
5. Select **SkylandersWii**, base **57**, version **5918**, destination **252**. Confirm252 is available for this test; leave system IOSes and existing cIOS slots249–251 unchanged. Select cIOS revision **21999**. Wait for the installer to report success before leaving.
6. In USBLoaderGX set the test game's **Game IOS252**, **Alternate DOL from SD/USB**, path **sd:/**, **Ocarina off**, **Hooktype none**, **debugger off**. A different supported free destination slot requires the matching Game IOS setting; the DOL itself does not change.

## Verification after installation

Start with Giants or Spyro's Adventure, since their menu behavior is already well established on vWii. Confirm portal detection, open with **Plus+Minus**, select a compatible figure, close the menu and confirm gameplay. Then save a small amount of progress, wait for saved status, restart and confirm it remains. Check the second controller and then the other games.

Report the installer result and any game/menu error. The Wii setup is owner-confirmed; a separate per-game Wii test matrix was not recorded. The menu controls,16 slots,640-entry capacity and save format match the vWii release. Swap/Trap/SuperChargers menus hold the background while open; they do not pause gameplay. Portal-speaker audio is not played.

## Why the portal binary is shared

Verified Wii IOS57v5918 and vWii IOS57v6175 contain byte-identical HID modules, including all hook targets. The six required official Wii d2x-v11-beta3 modules also match the corresponding vWii package files. The portal can therefore use the same binary. The base IOS, kernel patch offsets/content IDs and installer are platform-specific: the two installation packages are not interchangeable.

`ciosmaps.xml` selects only Wii57v5918 and adds the portal as the seventh module. `expected.json` records verified content/module hashes. No firmware, tickets, keys or WADs are committed. The private package includes the clean, signature-verified base obtained from Nintendo's update service.

Sources: [official d2x release](https://github.com/wiidev/d2x-cios/releases/tag/d2x-v11-beta3), [Wii/vWii installation distinction](https://wii.hacks.guide/cios.html).

## Reproduce the private package

Build the shared module with `python pc-debug/build_windows.py --multi-slot --out work/wii-release-build`. Obtain the official Wii d2x-v11-beta3 installer and verified decrypted contents of Wii IOS57v5918. Run `pc-debug/verify_wii_package.py` against those files. Then run `installer/package_wii.py --base-dir <verified-base-directory> --official <Wii-installer-directory> --portal <SKYLANDERS.app> --output <new-SD-folder>`. The packager validates every input and refuses nonempty destinations.
