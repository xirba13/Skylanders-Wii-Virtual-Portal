# In-game figure menu patches

These small patches contain the overlay and replacement bytes, not complete game executables. Apply to an extracted, original `main.dol` from the exact revision below. No compiler is needed to apply them; Python3 is sufficient. The input and output SHA256 are checked. Other regions/revisions and already patched files are rejected.

| Game | Patch | Original DOL SHA256 |
|---|---|---|
| Swap Force SVXI52 revision0 | SVXI52.patch.json | cebe439454e070e010e29581e7ba9b8bda558fbba8857013e9f31f77f8b69030 |
| Trap Team SK8I52 revision0 | SK8I52.patch.json | 9508395ff73af492937f1cf4830a60f06e5e92ee06e8393b62bcfe1c15956355 |
| SuperChargers Racing SKNP52 revision0 | SKNP52.patch.json | 862c9de4102cd2e69820673fa17d3378c7319d219249e8543273b888c95c54e5 |
| Giants SKYZ52 revision0 | SKYZ52.patch.json | 8a538ccfa2d5e98778114345c4ce503dc1c983b53befc1b53cda59c5812a6821 |
| Spyro's Adventure SSPP52 revision2 | SSPP52.patch.json | 6f4be21bd83c7072e566f1e813392b755fd27371026b8dae5c49d56c2d20c09f |

From the repository root:

```text
python pc-debug/apply_dol_patch.py patches/SKNP52.patch.json path/to/super/main.dol SKNP52.dol
python pc-debug/apply_dol_patch.py patches/SVXI52.patch.json path/to/swap/main.dol SVXI52.dol
python pc-debug/apply_dol_patch.py patches/SK8I52.patch.json path/to/trap/main.dol SK8I52.dol
python pc-debug/apply_dol_patch.py patches/SSPP52.patch.json path/to/ssa/main.dol SSPP52.dol
python pc-debug/apply_dol_patch.py patches/SKYZ52.patch.json path/to/giants/main.dol SKYZ52.dol
```

Put the resulting `<gameID>.dol` at the SD root. For each game in USBLoaderGX: Game IOS252, Alternate DOL from SD/USB (stored value2), DOL path `sd:/`, Ocarina off, Hooktype none and debugger off. The version1.2 HIDv4 cIOS and SD catalogue must already be installed. An IOS alone does not inject this menu.

Open with Plus+Minus on either player's Wii Remote. The opener controls the menu; the other player can claim it with their own Plus+Minus. D-pad browses; A loads, B closes; C/Z switches menu slots; Minus removes on release,1 saves,2 rescans. All five games use the same figure library and save journals. SSA cannot use Giants-only figures; select an SSA-compatible figure.

The patches use the accepted GPU-synchronized renderer and Plus+Minus/player2 controls. The user reports Giants and Spyro's Adventure work and flicker mostly disappeared. Swap Force and Trap Team are now user-confirmed working. SuperChargers Racing is also user-confirmed working on vWii. Both newer games hook GXCopyDisp entry and poll menu input there, independently of VI framebuffer changes. Swap Force also requires entry coverage because its game engine loads dynamically. All five menus accept up to640 catalogue entries. Reinstall the updated cIOS for the compact catalogue. Portal-speaker audio is accepted but not played. Load Swap Force TOP and BOT files in separate slots. See [complete installation](../docs/INSTALLATION.md).

To rebuild from source with devkitPPC at C:/devkitPro:

```text
python pc-debug/build_e11_overlay.py path/to/main.dol output-folder --multi-slot --sync-copy
```

The builder selects the exact fingerprint in `overlay/profiles.json` and emits the DOL, overlay and portable patch. Full DOLs stay out of git. `experimental-sync-copy/` contains historical E13B patches retained for recovery; the root patches are the final release.

The newer-game menus hold the background image while open and resume normal XFB copies on close. They do not pause gameplay. This avoids injecting the engine's blocking completion routine from its copy hook. The held-frame repair and Swap scratch-buffer fix are user-confirmed working. Older-game rendering is unchanged.

Swap Force additionally filters GXCopyDisp by the actual BP4D destination pitch: its zero-pitch clear-to-junk-buffer call must execute normally and must never receive menu pixels. The 2026-09-13 scratch-buffer repair is user-confirmed working. Trap Team held-frame rendering is user-confirmed working.

Version1.2 catalogue supports640 entries in the same memory budget, with19-character unique menu labels. Full source names remain in library.json. The E15C catalogue requires reinstalling version1.2 into IOS252. SuperChargers uses the held-background renderer and scratch-copy guard.

The original-Wii portal is also owner-confirmed on a European Wii, slot 252. See the root README for the exact tested scope and separate platform installers. Disc revisions here refer to the outer disc header; DOL hashes are authoritative.
