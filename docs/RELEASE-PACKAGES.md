# Public release assets — version 1.2

Publish the two firmware-free release ZIPs plus SHA256SUMS.txt. Keep all source and license files inside them.

- **Skylanders-Portal-1.2-vWii.zip**: complete tested vWii Homebrew Channel app in SD/. Copy SD contents to the card. The paired FIX94 Mod2.2 source archive was verified against the exact boot.dol.
- **Skylanders-Portal-1.2-Wii.zip**: complete tested Wii Homebrew Channel app in SD/, including the unchanged boot.dol from the owner-tested SD card. Copy SD contents to the card. No installer download script or PC preparation step is needed. Python 3 is still needed for the optional PC patch/library tools.

Neither ZIP includes Nintendo base IOS/WADs, games, complete game DOLs, figures or saves. USBLoaderGX is obtained separately. Game menu patches and library preparation tools are included. A console still needs Homebrew Channel; games and figures must be supplied by the user. These packages do not overwrite the user's figure library.

The vWii installer uses the console's installed base IOS; the Wii installer supports its normal Nintendo network download or a separately supplied matching offline WAD. Do not cross-install. Wii uses SkylandersWii, 57 v5918, slot252, revision21999; vWii uses Skylanders, 57 v6175, slot252, with no revision selector.

Source provenance and build instructions accompany each archive. Portal source was rebuilt with the packaged d2x source and produced the accepted binary hash. Original contributions use GPL-3.0-or-later; upstream components keep their own licenses. This packaging audit is not a blanket legal opinion.

## Reproduce

`installer/package_public.py` takes --sd (private card root), --d2x-source (exact tag source ZIP), --vwii-source (original FIX94 archive), --cios-lib (exact portal-linked source directory), --output (new directory), and optional --git (Git executable). It only reads an explicit homebrew-file allowlist from the card; it does not copy firmware, games or figure data. It validates expected module/installer/source hashes, checks map membership, and verifies ZIP entries against a manifest.

Do not upload the old private installation ZIPs or a completed personal SD image. Both public ZIPs include the homebrew installer but never the Nintendo base IOS or game data. The earlier setup helper has been removed.

## Saving clarification

The accepted runtime already saves changed figure data in the background and before replacing/removing figures. Button1 requests an immediate flush. Wait for the saved status before quitting; closing the menu is not a save command. Earlier release documentation incorrectly said that periodic autosave was absent. Only documentation and a host regression test changed in this correction; runtime modules and game patches are unchanged.

## Wii installer source-provenance limitation

The bundled Wii3.1-mod executable is verified against the owner-tested SD and official upstream release. Exact corresponding source for this binary was not verified. Its upstream licensing/source obligations remain unresolved; do not describe the source audit as complete. The old3.1 source mirror is not represented as corresponding source. The vWii binary remains paired with its original source archive.
