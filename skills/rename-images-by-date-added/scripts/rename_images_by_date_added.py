#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rename image files by macOS "Date Added" (kMDItemDateAdded) with fallback to birthtime/mtime.
- Default is dry-run (preview only)
- Use --apply to actually rename
- Writes a CSV log for undo
- Supports --undo to revert using a previous log

Designed primarily for macOS. On other OSes, mdls is not available and the script will fall back.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple, List

DEFAULT_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp",
    ".tif", ".tiff", ".bmp"
}

@dataclass(frozen=True)
class PlanItem:
    old_path: Path
    new_path: Path
    timestamp_ms: int
    source: str

def _normalize_exts(exts: Optional[List[str]]) -> set[str]:
    if not exts:
        return set(DEFAULT_EXTS)
    out: set[str] = set()
    for e in exts:
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        out.add(e)
    return out if out else set(DEFAULT_EXTS)

def _iter_files(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from (p for p in root.rglob("*") if p.is_file())
    else:
        yield from (p for p in root.iterdir() if p.is_file())

def _parse_mdls_date(s: str) -> Optional[float]:
    """
    mdls -raw outputs examples like:
      2025-12-16 02:23:45 +0000
      2025-12-16 02:23:45.123 +0000
      (null)

    Return epoch seconds (float) if parseable.
    """
    s = s.strip()
    if not s or s == "(null)":
        return None

    # Normalize timezone like +08:00 -> +0800 if needed
    m = re.match(r"^(.*)\s([+-]\d{2}):(\d{2})$", s)
    if m:
        s = f"{m.group(1)} {m.group(2)}{m.group(3)}"

    for fmt in ("%Y-%m-%d %H:%M:%S.%f %z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.timestamp()
        except ValueError:
            pass

    return None

def _get_date_added_mdls(path: Path) -> Optional[float]:
    """
    Use macOS mdls to read kMDItemDateAdded.
    Returns epoch seconds float or None.
    """
    try:
        proc = subprocess.run(
            ["mdls", "-name", "kMDItemDateAdded", "-raw", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if proc.returncode != 0:
        return None

    return _parse_mdls_date(proc.stdout)

def _get_birthtime(path: Path) -> Optional[float]:
    st = path.stat()
    # macOS typically provides st_birthtime
    bt = getattr(st, "st_birthtime", None)
    if bt is None:
        return None
    # st_birthtime is seconds (float)
    return float(bt)

def _get_mtime(path: Path) -> float:
    return float(path.stat().st_mtime)

def _timestamp_ms_for_file(path: Path, source: str) -> Tuple[int, str]:
    """
    source:
      - auto: try date-added, else birthtime, else mtime
      - date-added: mdls only; fallback to birthtime/mtime if missing
      - birthtime: birthtime only; fallback to mtime if missing
      - mtime: mtime only
    """
    source = source.lower()

    if source not in {"auto", "date-added", "birthtime", "mtime"}:
        raise ValueError(f"Unsupported source: {source}")

    if source in {"auto", "date-added"}:
        da = _get_date_added_mdls(path)
        if da is not None:
            return int(round(da * 1000)), "date-added"

        if source == "date-added":
            # explicit request, but still avoid failing hard
            bt = _get_birthtime(path)
            if bt is not None:
                return int(round(bt * 1000)), "birthtime"
            return int(round(_get_mtime(path) * 1000)), "mtime"

    if source in {"auto", "birthtime"}:
        bt = _get_birthtime(path)
        if bt is not None:
            return int(round(bt * 1000)), "birthtime"
        return int(round(_get_mtime(path) * 1000)), "mtime"

    # mtime
    return int(round(_get_mtime(path) * 1000)), "mtime"

def _format_name(ts_ms: int, fmt: str, prefix: str = "") -> str:
    """
    Format timestamp with optional prefix.
    prefix is typically the folder name.
    """
    fmt = fmt.lower()
    dt = datetime.fromtimestamp(ts_ms / 1000.0)
    # Always use datetime format: YYYYMMDDHHMMSSmmm (精确到毫秒)
    time_str = dt.strftime("%Y%m%d%H%M%S") + f"{ts_ms % 1000:03d}"

    if prefix:
        return f"{prefix}_{time_str}"
    return time_str

def _unique_target_name(
    target_dir: Path,
    base: str,
    ext: str,
    used: set[str]
) -> str:
    """
    Ensure uniqueness within the batch and on filesystem by suffixing _001, _002...
    """
    candidate = f"{base}{ext}"
    if candidate not in used and not (target_dir / candidate).exists():
        used.add(candidate)
        return candidate

    i = 1
    while True:
        candidate = f"{base}_{i:03d}{ext}"
        if candidate not in used and not (target_dir / candidate).exists():
            used.add(candidate)
            return candidate
        i += 1

def build_plan(
    root: Path,
    recursive: bool,
    exts: set[str],
    fmt: str,
    keep_original: bool,
    time_source: str,
) -> List[PlanItem]:
    files: List[Path] = []
    for p in _iter_files(root, recursive):
        if p.name.startswith("."):
            continue
        if p.suffix.lower() in exts:
            files.append(p)

    items: List[Tuple[Path, int, str]] = []
    for p in files:
        ts_ms, src = _timestamp_ms_for_file(p, time_source)
        items.append((p, ts_ms, src))

    # Sort for stability
    items.sort(key=lambda x: (x[1], x[0].name.lower()))

    used_names: set[str] = set()
    plan: List[PlanItem] = []
    for old_path, ts_ms, src in items:
        target_dir = old_path.parent
        ext = old_path.suffix  # preserve original case

        # Use folder name as prefix
        folder_name = target_dir.name
        base = _format_name(ts_ms, fmt, prefix=folder_name)

        # keep_original is now ignored as we always use folder prefix

        new_name = _unique_target_name(target_dir, base, ext, used_names)
        new_path = target_dir / new_name

        if new_path == old_path:
            # already matches
            continue

        plan.append(PlanItem(old_path=old_path, new_path=new_path, timestamp_ms=ts_ms, source=src))

    return plan

def write_csv_log(log_path: Path, plan: List[PlanItem]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["old_path", "new_path", "timestamp_ms", "source"])
        for it in plan:
            w.writerow([str(it.old_path), str(it.new_path), it.timestamp_ms, it.source])

def apply_plan(plan: List[PlanItem], log_path: Path) -> None:
    # Write log AFTER each successful rename to avoid recording actions that didn't happen.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["old_path", "new_path", "timestamp_ms", "source"])
        for it in plan:
            if it.new_path.exists():
                raise FileExistsError(f"Target already exists: {it.new_path}")
            it.old_path.rename(it.new_path)
            w.writerow([str(it.old_path), str(it.new_path), it.timestamp_ms, it.source])
            f.flush()

def undo_from_log(log_path: Path, apply: bool) -> int:
    if not log_path.exists():
        raise FileNotFoundError(f"Log not found: {log_path}")

    rows: List[Tuple[Path, Path]] = []
    with log_path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            old_p = Path(row["old_path"])
            new_p = Path(row["new_path"])
            rows.append((old_p, new_p))

    # reverse to safely undo in case of cascades
    rows.reverse()

    changed = 0
    for old_p, new_p in rows:
        if not new_p.exists():
            print(f"[SKIP] new missing: {new_p}")
            continue
        if old_p.exists():
            print(f"[SKIP] old already exists: {old_p}")
            continue

        print(f"[UNDO] {new_p} -> {old_p}")
        if apply:
            new_p.rename(old_p)
        changed += 1

    return changed

def default_log_name(root: Path, prefix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return root / f"{prefix}-{stamp}.csv"

def main() -> int:
    ap = argparse.ArgumentParser(description="Rename images by macOS Date Added (ms) with dry-run/apply/undo.")
    ap.add_argument("--path", type=str, help="Target directory path for rename.")
    ap.add_argument("--recursive", action="store_true", help="Process files recursively.")
    ap.add_argument("--ext", action="append", help="Extensions to include (e.g. --ext jpg --ext png). Default: common images.")
    ap.add_argument("--format", dest="fmt", default="epoch-ms", choices=["epoch-ms", "datetime-ms"], help="Filename format.")
    ap.add_argument("--keep-original", action="store_true", help="Append original stem after timestamp (e.g. 123__IMG_0001.jpg).")
    ap.add_argument("--time-source", default="auto", choices=["auto", "date-added", "birthtime", "mtime"], help="Timestamp source preference.")
    ap.add_argument("--dry-run", action="store_true", help="Preview only (default if neither --dry-run nor --apply is provided).")
    ap.add_argument("--apply", action="store_true", help="Actually rename files.")
    ap.add_argument("--log", type=str, help="CSV log path. Default: in target directory.")
    ap.add_argument("--undo", type=str, help="Undo using a previous CSV log. Use with --apply to actually undo.")
    args = ap.parse_args()

    # Undo mode
    if args.undo:
        log_path = Path(args.undo).expanduser()
        do_apply = bool(args.apply)
        changed = undo_from_log(log_path, apply=do_apply)
        print(f"Undo done. Items affected: {changed}. apply={do_apply}")
        return 0

    if not args.path:
        print("ERROR: --path is required for rename mode.", file=sys.stderr)
        return 2

    root = Path(args.path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: path is not a directory: {root}", file=sys.stderr)
        return 2

    exts = _normalize_exts(args.ext)

    # Default mode: dry-run unless user explicitly sets --apply
    do_apply = bool(args.apply)
    do_dry = bool(args.dry_run) or not do_apply

    plan = build_plan(
        root=root,
        recursive=bool(args.recursive),
        exts=exts,
        fmt=args.fmt,
        keep_original=bool(args.keep_original),
        time_source=args.time_source,
    )

    if not plan:
        print("No matching image files found (or all already match target naming).")
        return 0

    # Log path
    if args.log:
        log_path = Path(args.log).expanduser()
    else:
        log_path = default_log_name(root, prefix="rename-log")

    # Preview
    print(f"Target directory: {root}")
    print(f"Files to rename: {len(plan)}")
    print(f"Format: {args.fmt}; keep_original={args.keep_original}; time_source={args.time_source}; recursive={args.recursive}")
    print(f"Log path: {log_path}")
    print("\nPreview:")
    for it in plan[:50]:
        print(f"  {it.old_path.name} -> {it.new_path.name}  [ts_ms={it.timestamp_ms} src={it.source}]")
    if len(plan) > 50:
        print(f"  ... ({len(plan) - 50} more)")

    if do_dry and not do_apply:
        # Write a plan log for review
        write_csv_log(log_path, plan)
        print("\nDry-run complete. Plan written to CSV log above. Re-run with --apply to execute.")
        return 0

    # Apply
    print("\nApplying rename...")
    apply_plan(plan, log_path)
    print(f"Done. Renamed {len(plan)} files. Log saved to: {log_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())