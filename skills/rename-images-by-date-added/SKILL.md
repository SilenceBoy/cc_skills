---
name: rename-images-by-date-added
description: Batch-rename image files (jpg/png/heic/webp/etc.) in a folder using pattern "foldername_YYYYMMDDHHMMSSmmm.ext" based on macOS Finder "Date Added" (kMDItemDateAdded) with fallback to file creation time. Supports dry-run preview, conflict-safe suffixing (_001, _002), and undo via CSV log. Use when the user asks to rename photos/images by "date added/added time/添加时间" or wants timestamp-based naming with folder prefix.
---

# Rename Images by Date Added

## Goal

Rename image files in a target directory using the pattern: **{folder_name}_{timestamp}.{ext}**
- Timestamp format: YYYYMMDDHHMMSSmmm (年月日时分秒毫秒，精确到毫秒)
- Example: `abc_20251219151300111.jpg` for a file in folder "abc"
- Timestamp derived from **macOS Date Added** (preferred) or **file creation time** (fallback)

## Safety rules (must follow)

1. Always run a **dry-run** first and show a clear preview: `old -> new`.
2. Never rename anything if the user did not specify the target directory (ask for it).
3. Always generate a CSV log file containing `old_path,new_path,timestamp_ms,source` so the operation can be undone.
4. Detect naming collisions and resolve safely by appending `_001`, `_002`, etc.
5. Do not modify non-image files unless the user explicitly asks.

## Default behavior

- Target directory: user-provided (no default rename without explicit path).
- Extensions: common images (`jpg`, `jpeg`, `png`, `gif`, `heic`, `heif`, `webp`, `tif`, `tiff`, `bmp`).
- Time source: `auto` (try Date Added, else birth time, else mtime).
- Output format: `{folder_name}_YYYYMMDDHHMMSSmmm.{ext}` (e.g., `photos_20251219151300111.jpg`).
- Collision handling: If same timestamp exists, append `_001`, `_002`, etc.
- Mode: `--dry-run` first, then `--apply` only after user confirms.

## How to run

The implementation script is:

- `~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py`

### Dry-run example (required first step)

```bash
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --path "/ABS/PATH/TO/PHOTOS" \
  --dry-run
```

### Apply after confirmation

```bash
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --path "/ABS/PATH/TO/PHOTOS" \
  --apply
```

### Undo (using a CSV log produced by apply)

```bash
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --undo "/ABS/PATH/TO/rename-log-YYYYMMDD-HHMMSS.csv" \
  --apply
```

## What to ask the user (if missing)

* Target directory path?
* Recursive rename needed?

## Notes

- The `--keep-original` option is no longer used; files are always named with folder prefix
- The output format is always `{folder_name}_YYYYMMDDHHMMSSmmm.{ext}`
- Conflicts are resolved by appending `_001`, `_002`, etc. to the base name