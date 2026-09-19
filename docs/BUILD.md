# Build notes

Required locally:

- devkitPro/devkitARM;
- d2x cIOS library sources;
- Fakemote's cIOS library;
- `stripios` compatible with d2x modules.

The current Makefile keeps paths matching the original research workspace and will need configurable dependency paths before the repository is portable.

Build products are deliberately ignored by Git. IOS57 content, WAD files and figure dumps must be supplied locally by the owner and must never be committed.

