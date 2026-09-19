# Skylanders Virtual Portal — Wii and Wii U vWii

A homebrew project that imitates the Skylanders **Portal of Power** in software. A custom IOS (cIOS) presents a virtual USB HIDv4 portal to Wii games, while a patched game executable adds an in-game menu for choosing figure dumps stored on an SD card. No physical portal is needed for the virtual figures.

Created with **ChatGPT 5.6 Sol** and **ChatGPT 6 Astra**, with iterative testing and feedback on real consoles. This is an unofficial fan project, not affiliated with or endorsed by Activision, Toys for Bob or Nintendo.

Keep a backup of your SD saves and a current console recovery/NAND backup appropriate to your hardware before installing custom IOS.

**DISCLAIMER**: I am not responsible for any damage to consoles, games, or other equipment that may occur while using this.

<table>
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/e72cd1ba-62ad-40d4-b403-bd187c2f0c88" width="400">
      <div style="margin-top: 10px;"><b>Spyro's Adventure</b></div>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/5c29bd4a-4e85-4cf2-820d-d44f49880e45" width="400">
      <div style="margin-top: 10px;"><b>Giants</b></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/cfed1da3-8c88-4922-b9f1-e727946c9be6" width="400">
      <div style="margin-top: 10px;"><b>Swap Force</b></div>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/5356a40b-d776-4dea-b937-e19b16ae273e" width="400">
      <div style="margin-top: 10px;"><b>Trap Team</b></div>
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2">
      <img src="https://github.com/user-attachments/assets/d1d7c363-50a5-4acb-b373-92eeff381d7c" width="400">
      <div style="margin-top: 10px;"><b>Superchargers Racing</b></div>
    </td>
  </tr>
</table>


## Features

- SD catalogue of up to **640 figures**, with **16 virtual portal slots**.
- In-game figure selection; either player's controller can open and control the menu.
- Background saving and an explicit **Save Now** command preserve figure progress on SD.
- Five fingerprint-checked game patches, shared between Wii and vWii.
- Separate, clearly labelled **Wii ONLY** and **vWii ONLY** installers.

The cIOS provides the portal protocol. The alternate DOL provides the menu. Installing the cIOS alone does **not** add the menu to the games.

## Tested hardware and cIOS settings

| Console tested               | Homebrew Channel app              | cIOS selection  | Base IOS     | Destination | Revision selector                                        |
| ---------------------------- | --------------------------------- | --------------- | ------------ | ----------- | -------------------------------------------------------- |
| European Wii U, running vWii | **Skylanders Portal - vWii ONLY** | `Skylanders`    | **57 v6175** | **252**     | This option does not appear in the tested vWii installer |
| European original Wii        | **Skylanders Portal - Wii ONLY**  | `SkylandersWii` | **57 v5918** | **252**     | **21999**                                                |

Do not cross-install the Wii and vWii packages. Wii mini and other console regions have not been tested.

Slot 252 is the tested default, not a hardcoded runtime requirement. Another suitable unused cIOS slot should work if the installer supports it and each game's **Game IOS** points to that same slot. Alternate slots are untested. Changing the slot does not require changing the DOL patch. Do not overwrite system IOSes or another cIOS you need.

## Exact supported game versions

These are the disc IDs and outer-disc revision bytes verified from the tested images, not a promise of compatibility with every European release. The original `main.dol` SHA-256 is the definitive patch requirement; the patcher rejects a mismatch.

| Game                            | Disc ID  | Disc revision | Patch                                            |
| ------------------------------- | -------- | ------------- | ------------------------------------------------ |
| Skylanders Spyro's Adventure    | `SSPP52` | 2             | [`SSPP52.patch.json`](patches/SSPP52.patch.json) |
| Skylanders Giants               | `SKYZ52` | 0             | [`SKYZ52.patch.json`](patches/SKYZ52.patch.json) |
| Skylanders Swap Force           | `SVXI52` | 0             | [`SVXI52.patch.json`](patches/SVXI52.patch.json) |
| Skylanders Trap Team            | `SK8I52` | 0             | [`SK8I52.patch.json`](patches/SK8I52.patch.json) |
| Skylanders SuperChargers Racing | `SKNP52` | 0             | [`SKNP52.patch.json`](patches/SKNP52.patch.json) |

Full input/output hashes are in each patch and in [the patch guide](patches/README.md). Disc-header and partition-header revisions can differ: the tested Spyro's Adventure image has disc revision 2 but partition boot revision 0; Swap Force has disc revision 0 but partition boot revision 1. Always use the DOL hash rather than guessing from the title or filename.

## Installation

Public release ZIPs and their platform-specific setup steps are described in [release packages](docs/RELEASE-PACKAGES.md). Both ZIPs include their tested installer executable; no PC installer download or setup script is needed. Neither includes Nintendo firmware or game/figure data.

### What you supply

- A homebrew-enabled original Wii or Wii U vWii, an SD card and USBLoaderGX.
- Your own matching game image and extracted, unmodified `main.dol`.
- Your own compatible **1024-byte figure dumps**; none are supplied here.

### What the release supplies

Both platform ZIPs supply the compiled portal module, required d2x modules, custom installer configuration, five game patches, figure-library tools, source and licenses. You do **not** need to build or find the portal/d2x modules separately.

- **vWii ZIP:** includes the tested installer; copy the contents of `SD/` to the card.
- **Wii ZIP:** includes the installer executable tested on the original Wii; copy the contents of `SD/` to the card.
- **Nintendo base IOS:** not bundled. The vWii installer uses IOS57 v6175 already on your console. The Wii installer obtains IOS57 v5918 through its normal network installation, or you supply a verified matching offline WAD if needed.

The source-only repository ZIP is for development; use a platform release ZIP for installation. Nintendo firmware, games and figure data are not supplied by this project.

### 1. Prepare the figure library and game patch

For a new library, place your `.dump` files beneath a source directory and run:

```text
python pc-debug/prepare_library.py path/to/your-dumps path/to/new-library
```

Copy the resulting directory contents to `sd:/skylanders/e11/`. Optional top-level folders beginning `1.`, `2.`, `3.`, `4.` and `5.` produce SSA, Giants, Swap, Trap and SuperChargers labels. Menu labels are shortened to 19 characters; full source names remain in `library.json`.

For an existing library, preserve its indices and journals:

```text
python pc-debug/extend_library.py path/to/your-dumps path/to/current-e11 path/to/new-staging-folder
```

Back up the current library first; use the validated staging output. Do not regenerate an existing catalogue from scratch or overwrite newer saves with old backups.

Apply the matching patch, for example:

```text
python pc-debug/apply_dol_patch.py patches/SKYZ52.patch.json path/to/original/main.dol SKYZ52.dol
```

Place the resulting `<gameID>.dol` at the SD root. See [all five commands](patches/README.md). Patching needs Python 3; rebuilding the menu needs devkitPPC.

### 2A. Install on Wii U vWii

1. Enter **vWii** and open Homebrew Channel.
2. Launch **Skylanders Portal - vWii ONLY**, in `apps/skylanders-portal-installer-vwii`.
3. Select **Skylanders**, base **57 v6175**, destination **252**. There is **no cIOS revision selection option** in this tested installer.
4. If using offline installation, the matching base is `IOS57-64-v6175.wad`. Wait for successful completion before exiting.

The vWii map and metadata are in `installer/ciosmaps.xml` and `installer/meta.xml`. See [vWii installation details](docs/INSTALLATION.md).

### 2B. Install on original Wii

1. Open Homebrew Channel and launch **Skylanders Portal - Wii ONLY**, in `apps/skylanders-portal-installer-wii`.
2. Select **SkylandersWii**, base **57 v5918**, destination **252**, cIOS revision **21999**.
3. If using offline installation, the matching base is `IOS57-64-v5918.wad`. Wait for successful completion before exiting.

The Wii map and metadata are in `installer/wii/`. See [Wii installation and packaging](installer/wii/README.md). Do not use the vWii base WAD or installer on an original Wii.

### 3. Configure USBLoaderGX and play

For each supported game set **Game IOS: 252**, **Alternate DOL: from SD/USB**, DOL path **`sd:/`**, **Ocarina: off**, **Hooktype: none**, **debugger: off**. If you deliberately chose another cIOS slot, use that slot as Game IOS. Game images stay on your game drive.

Start the game, open the menu, load a compatible figure, close the menu and check recognition. Save some progress, wait for success, then restart to confirm persistence.

## Menu controls and saving

| Control                             | Action                                                                             |
| ----------------------------------- | ---------------------------------------------------------------------------------- |
| **Plus + Minus**, either Wii Remote | Open/close the menu; the other player can claim control with their own combination |
| D-pad Up / Down                     | Browse figures                                                                     |
| D-pad Left / Right                  | Change page                                                                        |
| A                                   | Load highlighted figure into the chosen slot                                       |
| B                                   | Close menu                                                                         |
| Nunchuk C / Z                       | Change portal slot                                                                 |
| Minus alone, then release           | Remove figure                                                                      |
| **1 — Save**                        | **Save figure data to SD now**                                                     |
| 2                                   | Rescan library                                                                     |

**1 — Save Now** requests an immediate flush of pending figure changes. Before finishing a session, use it and wait for the saved status. Closing the menu does not itself request a save, and powering off can interrupt pending writes. Autosave timing is not a guarantee that the latest change is already on the card. This concerns figure data; the game's own campaign/save-slot data is handled separately by the game.

Figure data is saved automatically in the background, but it may not work properly. Remember to save manually before changing to another one.

Progress is stored in alternating `.sav0` / `.sav1` journals with integrity checks; original `figNNN.bin` dumps remain unchanged. Back up the entire `skylanders/e11` folder together. Use separate slots for Swap Force TOP/BOT halves, or figures and vehicles needed together. Each game still decides which figures it supports.

## Limitations and troubleshooting

- A menu requires the exact matching game patch and Alternate DOL settings, even if the virtual portal itself already works.
- A patched game must run under the virtual portal cIOS, not the game's stock IOS.
- Swap Force, Trap Team and SuperChargers Racing hold the background image while the menu is open; **gameplay is not paused**.
- Portal-speaker audio is not played.
- If a figure is rejected, check game compatibility, catalogue integrity and the selected slot.
- PC checks verify protocol behavior, patch bytes and storage invariants; real-console tests remain necessary for new builds.

## Patching another region or revision

It is possible, but not automatic. Renaming an existing patch or changing its input hash is insufficient. Extract the new original `main.dol`, record the disc ID/revision and hash, then reverse-engineer its controller sampling, VI/GX display-copy functions, memory layout and safe hook sites. Later games may load engine code dynamically and perform scratch-buffer copies that must not be painted.

Add a reviewed profile to `overlay/profiles.json`, including expected instructions, controller state, renderer addresses and any scratch-copy guard. Extend the builder if the engine needs a new strategy. Build with:

```text
python pc-debug/build_e11_overlay.py path/to/new/main.dol output-folder --multi-slot --sync-copy
```

The builder only accepts known fingerprints. Validate the generated patch, memory boundaries and input/output hashes, then test opening/closing, both controllers, figure loading, saving/restart and gameplay on hardware. Share the small patch and source profile, **not the game's DOL or image**.

## Building and repository layout

[Build notes](docs/BUILD.md) explain the current Windows/devkitPro dependency layout; the original developer paths still need configuration on a new machine. `installer/package_release.py` prepares a **private** vWii SD package from an existing setup; `installer/package_wii.py` prepares a **private** verified Wii package. Both may copy firmware and must not be used as public release archives.

- `plugin/`: current ARM HIDv4 portal and SD storage implementation.
- `overlay/`: in-game PPC menu and exact-game profiles.
- `patches/`: portable game patches; root patches are the accepted release.
- `installer/`: platform maps, metadata and private packaging tools.
- `pc-debug/`: builders, patcher and host validation tools.
- `probe/` and `portal-core/`: historical diagnostics, not required installation apps. The private development checkout also retains text evidence and old logs; these are omitted from the public source export.

## License, credits, publication and future work

Original project contributions are licensed under **GPL-3.0-or-later**; see [LICENSE](LICENSE) and [upstream notices](THIRD-PARTY-NOTICES.md). Third-party materials retain their own licenses.

Thanks to the d2x cIOS, FAKEMOTE/embedded-game-controller, devkitPro/libogc, USBLoaderGX, Dolphin and re_nsyshid projects and their contributors. They supplied the homebrew foundations, tools and/or protocol references used during development. AI assistance does not replace upstream credit or license obligations. See [third-party and publication notes](docs/PUBLIC-RELEASE.md).

Do not publish Nintendo IOS/WADs, keys/tickets, NAND dumps, game images, complete original or patched DOLs, figure dumps, save journals, private SD ZIPs or personal probe photos. Patches contain small replacement byte sequences and our overlay rather than whole games; this is not a blanket legal clearance for distributing every byte. Upstream code remains subject to its own licenses.

Possible future work: patches for more regions/revisions, configurable autosave timing and clearer save-status feedback, broader hardware testing and more portable build/package tooling. These are ideas, not promised features. The working runtime is frozen for now.
