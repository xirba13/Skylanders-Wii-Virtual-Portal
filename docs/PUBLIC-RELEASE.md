# Public repository preparation

## Keep private

Never upload an SD-card ZIP or the private installer ZIP: these include Nintendo base IOS firmware. Keep IOS/WADs, tickets, keys, NAND dumps, games, full game DOLs (patched or not), figure dumps and saves private. The repository ignores common forms and private work/output directories; ignores are not a security boundary.

Tracked-file/history extension audit found no WAD, ISO, RVZ, APP, DOL or BIN files, but did find 36 personal probe PNGs in history. They were removed from the current tree. Removing a file in a commit does not remove earlier copies. Publish the separately prepared source-only snapshot as a new repository rather than pushing the private development history. That snapshot omits historical evidence, experimental patches, local paths in old logs and .git. No remote publication has been performed.

## Licenses and third-party materials

The owner has authorized GPL-3.0-or-later for original contributions. See ../LICENSE and ../THIRD-PARTY-NOTICES.md. Do not describe the entire tree as MIT, public domain or free of copyright. An AI-assisted origin does not clear upstream obligations. Third-party licenses and corresponding-source requirements remain applicable.

- [d2x cIOS](https://github.com/wiidev/d2x-cios): upstream root LICENSE declares GPL v3; individual cIOS library files carry GPL v2-or-later notices. Preserve the relevant notices and provide corresponding source when distributing covered binaries.
- [FAKEMOTE](https://github.com/xerpi/fakemote) and its embedded-game-controller cIOS library: the locally used cIOS library files carry GPL v2-or-later notices. Check the precise component/revision, not only the repository badge.
- [Dolphin](https://github.com/dolphin-emu/dolphin): protocol reference; its COPYING describes multiple compatible licenses. Any copied implementation must keep its actual license/attribution. Merely citing a project is not a substitute for compliance.
- re_nsyshid: another protocol reference used during development; verify provenance/license before redistributing any code from it.
- devkitPro/libogc, d2x installer and USBLoaderGX: separate upstream projects. Obtain them from their upstream sources and retain their license/source requirements if bundling. They are not included as binary downloads in the source-only snapshot. The separate public release packages include verified homebrew components with source/notices; see RELEASE-PACKAGES.md.

The portable JSON patches include generated overlay bytes and small replacement instructions/header values. They are not whole game executables, but a patch format by itself does not guarantee that every included byte is unencumbered. Installer XML includes patch preimages/offsets rather than full firmware. This audit is a packaging/provenance check, not a legal opinion or guarantee of publication rights.

Skylanders and Portal of Power names identify compatibility; do not include official logos, game art or marketing assets as project branding. Do not imply endorsement by Activision, Nintendo or OpenAI.

## Release checklist

- Use the source-only export for the repository and the dedicated public release ZIPs for release assets, never a private SD package or the old .git history.
- Preserve the GPL-3.0-or-later project license and upstream notices; review exact third-party sources before distributing compiled dependencies.
- Include only root accepted game patches, source, tooling and current docs.
- Supply no firmware, figure/game data or personal photos.
- Keep the precise game hashes and hardware scope; other regions and slots remain untested.
