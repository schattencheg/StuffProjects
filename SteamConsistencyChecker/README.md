# SteamConsistencyChecker

Steam library manifest parser for Windows.

## Description

This project contains utilities for parsing Steam library files and validating game installations. It reads Steam's `libraryfolders.vdf` configuration and checks for consistency between manifest files (`.acf`) and installed game folders.

Scans Steam libraries and reports:
- **Manifest entries** - Lists all detected game manifests with their status:
  - `[OK]` - Game folder exists
  - `[MISSING]` - Manifest exists but game folder is missing
- **Orphaned folders** - Game folders without corresponding manifest files
