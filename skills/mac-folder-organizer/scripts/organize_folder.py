#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Organize a macOS folder into a "分类结果" directory with categories:
表格、代码、视频、图片、文档、压缩包、安装包、演示文稿

Key behaviors:
- Default: non-recursive scan
- Dry-run by default; requires --apply to move
- Excludes the result directory itself from scanning (important for recursive)
- Conflict-safe: if destination exists, suffix _001/_002...
- Produces a CSV log on apply for undo
- Supports undo via --undo <log.csv> --apply
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

CAT_TABLE = "表格"
CAT_CODE = "代码"
CAT_VIDEO = "视频"
CAT_IMAGE = "图片"
CAT_DOC = "文档"
CAT_ARCHIVE = "压缩包"
CAT_INSTALLER = "安装包"
CAT_PRESENT = "演示文稿"
CAT_OTHER = "其他"

CATEGORIES = [
    CAT_TABLE, CAT_CODE, CAT_VIDEO, CAT_IMAGE,
    CAT_DOC, CAT_ARCHIVE, CAT_INSTALLER, CAT_PRESENT
]

COMPOUND_EXTS = [
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst",
    ".tgz", ".tbz2", ".txz"
]

EXT_MAP: Dict[str, Set[str]] = {
    CAT_TABLE: {".xls", ".xlsx", ".csv", ".tsv", ".ods", ".numbers"},
    CAT_CODE: {
        ".py", ".ipynb", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".kts",
        ".go", ".rs", ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp",
        ".m", ".mm", ".swift", ".cs",
        ".sh", ".bash", ".zsh", ".fish",
        ".sql",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".xml", ".gradle", ".pom", ".sln", ".csproj",
    },
    CAT_VIDEO: {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".wmv", ".flv", ".webm"},
    CAT_IMAGE: {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp", ".svg"},
    CAT_DOC: {".pdf", ".doc", ".docx", ".txt", ".rtf", ".md", ".pages", ".epub", ".mobi"},
    CAT_ARCHIVE: {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", *COMPOUND_EXTS},
    CAT_INSTALLER: {".dmg", ".pkg", ".mpkg", ".exe", ".msi", ".deb", ".rpm", ".apk"},
    CAT_PRESENT: {".ppt", ".pptx", ".key", ".odp"},
}

# 默认不动目录；可用 --include-packages 把 iWork 包（.pages/.numbers/.key）当作可移动对象
DEFAULT_PACKAGE_DIR_EXTS = {".pages", ".numbers", ".key"}

@dataclass(frozen=True)
class PlanItem:
    old_path: Path
    new_path: Path
    category: str

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")

def match_compound_ext(name_lower: str) -> Optional[str]:
    for ext in sorted(COMPOUND_EXTS, key=len, reverse=True):
        if name_lower.endswith(ext):
            return ext
    return None

def split_base_ext(name: str) -> Tuple[str, str]:
    nl = name.lower()
    cext = match_compound_ext(nl)
    if cext:
        return name[: -len(cext)], name[-len(cext):]
    p = Path(name)
    ext = p.suffix
    if ext:
        return name[: -len(ext)], ext
    return name, ""

def ext_token(path: Path) -> str:
    _, ext = split_base_ext(path.name)
    return ext.lower()

def classify(path: Path) -> Optional[str]:
    name_lower = path.name.lower()
    if name_lower in {"dockerfile", "makefile"}:
        return CAT_CODE
    if name_lower.startswith("dockerfile"):
        return CAT_CODE

    e = ext_token(path)
    if not e:
        return None
    for cat, exts in EXT_MAP.items():
        if e in exts:
            return cat
    return None

def iter_candidates(
    root: Path,
    recursive: bool,
    result_dir: Path,
    include_packages: bool,
    include_app: bool,
) -> Iterable[Path]:
    result_dir = result_dir.resolve()

    def eligible(p: Path) -> bool:
        try:
            rp = p.resolve()
        except Exception:
            rp = p.absolute()

        # 排除 分类结果 及其子树
        if rp == result_dir or result_dir in rp.parents:
            return False

        if is_hidden(p):
            return False

        if p.is_file():
            return True

        # 可选：把 iWork 包目录当作可移动对象
        if include_packages and p.is_dir():
            e = ext_token(p)
            if e in DEFAULT_PACKAGE_DIR_EXTS:
                return True
            if include_app and e == ".app":
                return True

        return False

    if not recursive:
        for p in root.iterdir():
            if eligible(p):
                yield p
        return

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)

        # prune hidden dirs and result_dir
        pruned = []
        for d in list(dirnames):
            dd = dp / d
            if is_hidden(dd):
                pruned.append(d)
                continue
            try:
                rdd = dd.resolve()
            except Exception:
                rdd = dd.absolute()
            if rdd == result_dir or result_dir in rdd.parents:
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        for fn in filenames:
            p = dp / fn
            if eligible(p):
                yield p

        if include_packages or include_app:
            for d in dirnames:
                p = dp / d
                if eligible(p):
                    yield p

def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    base, ext = split_base_ext(dest.name)
    i = 1
    while True:
        candidate = dest.with_name(f"{base}_{i:03d}{ext}")
        if not candidate.exists():
            return candidate
        i += 1

def build_plan(
    root: Path,
    result_dir_name: str,
    recursive: bool,
    flatten: bool,
    include_packages: bool,
    include_app: bool,
    unclassified: str,
) -> Tuple[List[PlanItem], List[Path], Dict[str, int], List[Path], Path]:
    result_dir = (root / result_dir_name).resolve()

    counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
    plan: List[PlanItem] = []
    unclassified_list: List[Path] = []

    candidates = list(iter_candidates(
        root=root,
        recursive=recursive,
        result_dir=result_dir,
        include_packages=include_packages,
        include_app=include_app,
    ))
    candidates.sort(key=lambda p: p.as_posix().lower())

    for p in candidates:
        cat = classify(p)
        if not cat:
            unclassified_list.append(p)
            continue

        dest_dir = result_dir / cat
        if flatten:
            dest = dest_dir / p.name
        else:
            rel_parent = p.parent.relative_to(root)
            dest = dest_dir / rel_parent / p.name

        dest = unique_destination(dest)
        plan.append(PlanItem(old_path=p, new_path=dest, category=cat))
        counts[cat] += 1

    dirs_to_create: Set[Path] = {result_dir, result_dir / "_logs"}
    for it in plan:
        dirs_to_create.add(it.new_path.parent)

    dirs_sorted = sorted(dirs_to_create, key=lambda p: p.as_posix().lower())

    # 可选：未分类移动到 其他
    if unclassified == "move" and unclassified_list:
        uc_dir = result_dir / CAT_OTHER
        dirs_sorted.append(uc_dir)
        for p in unclassified_list:
            dest = unique_destination(uc_dir / p.name)
            plan.append(PlanItem(old_path=p, new_path=dest, category=CAT_OTHER))

    plan.sort(key=lambda it: (it.category, it.old_path.name.lower()))
    return plan, dirs_sorted, counts, unclassified_list, result_dir

def write_log_header(w: csv.writer) -> None:
    w.writerow(["category", "old_path", "new_path", "status", "error"])

def apply_plan(plan: List[PlanItem], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        write_log_header(w)
        f.flush()

        for it in plan:
            try:
                it.new_path.parent.mkdir(parents=True, exist_ok=True)
                if it.new_path.exists():
                    it = PlanItem(it.old_path, unique_destination(it.new_path), it.category)

                shutil.move(str(it.old_path), str(it.new_path))
                w.writerow([it.category, str(it.old_path), str(it.new_path), "moved", ""])
            except Exception as e:
                w.writerow([it.category, str(it.old_path), str(it.new_path), "failed", repr(e)])
            finally:
                f.flush()

def undo_from_log(log_path: Path, apply: bool) -> int:
    if not log_path.exists():
        raise FileNotFoundError(f"Log not found: {log_path}")

    rows: List[Tuple[str, Path, Path]] = []
    with log_path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("status") != "moved":
                continue
            rows.append((row.get("category", ""), Path(row["old_path"]), Path(row["new_path"])))

    rows.reverse()
    changed = 0
    for cat, old_p, new_p in rows:
        if not new_p.exists():
            print(f"[SKIP] missing new: {new_p}")
            continue
        if old_p.exists():
            print(f"[SKIP] old exists: {old_p}")
            continue

        print(f"[UNDO] {new_p} -> {old_p} (cat={cat})")
        if apply:
            old_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(new_p), str(old_p))
        changed += 1
    return changed

def main() -> int:
    ap = argparse.ArgumentParser(description="Organize a macOS folder into 分类结果 by file extensions.")
    ap.add_argument("--path", type=str, help="Target folder path to organize.")
    ap.add_argument("--recursive", action="store_true", help="Scan recursively (default: non-recursive).")
    ap.add_argument("--result-dir-name", default="分类结果", help='Result folder name (default: "分类结果").')
    ap.add_argument("--keep-structure", action="store_true", help="Keep relative structure under each category (default: flatten).")
    ap.add_argument("--include-packages", action="store_true", help="Also move iWork package directories (.pages/.numbers/.key).")
    ap.add_argument("--include-app", action="store_true", help="Also move .app bundles (directories). Use with caution.")
    ap.add_argument("--unclassified", choices=["report", "move"], default="move",
                    help='What to do with unclassified items: move to 其他 (default) or report only.')
    ap.add_argument("--dry-run", action="store_true", help="Preview only (default if --apply is not provided).")
    ap.add_argument("--apply", action="store_true", help="Actually move files.")
    ap.add_argument("--undo", type=str, help="Undo using a CSV log file. Use with --apply to actually undo.")
    ap.add_argument("--max-preview", type=int, default=80, help="Max preview lines to print.")
    args = ap.parse_args()

    if args.undo:
        log_path = Path(args.undo).expanduser().resolve()
        do_apply = bool(args.apply)
        changed = undo_from_log(log_path, apply=do_apply)
        print(f"Undo complete. affected={changed}. apply={do_apply}")
        return 0

    if not args.path:
        print("ERROR: --path is required.", file=sys.stderr)
        return 2

    root = Path(args.path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: path is not a directory: {root}", file=sys.stderr)
        return 2

    recursive = bool(args.recursive)
    flatten = not bool(args.keep_structure)

    plan, dirs_to_create, counts, unclassified_list, result_dir = build_plan(
        root=root,
        result_dir_name=args.result_dir_name,
        recursive=recursive,
        flatten=flatten,
        include_packages=bool(args.include_packages),
        include_app=bool(args.include_app),
        unclassified=args.unclassified,
    )

    total_matched = sum(counts.values())
    print(f"Target: {root}")
    print(f"Result dir: {result_dir}")
    print(f"Mode: {'recursive' if recursive else 'non-recursive'}; {'flatten' if flatten else 'keep-structure'}")
    print(f"Include packages: {bool(args.include_packages)}; include .app: {bool(args.include_app)}")
    print(f"Unclassified policy: {args.unclassified}")

    print("\nCounts by category:")
    for cat in CATEGORIES:
        print(f"  {cat}: {counts.get(cat, 0)}")
    print(f"  (matched total): {total_matched}")
    print(f"Unclassified items: {len(unclassified_list)}")

    print("\nDirectories that would be created on apply:")
    for d in dirs_to_create[:30]:
        print(f"  {d}")
    if len(dirs_to_create) > 30:
        print(f"  ... ({len(dirs_to_create) - 30} more)")

    print("\nPreview (old -> new):")
    for it in plan[: args.max_preview]:
        print(f"  [{it.category}] {it.old_path} -> {it.new_path}")
    if len(plan) > args.max_preview:
        print(f"  ... ({len(plan) - args.max_preview} more)")

    if unclassified_list and args.unclassified == "report":
        print("\nUnclassified (not moved):")
        for p in unclassified_list[: min(30, len(unclassified_list))]:
            print(f"  {p}")
        if len(unclassified_list) > 30:
            print(f"  ... ({len(unclassified_list) - 30} more)")

    do_apply = bool(args.apply)
    do_dry = bool(args.dry_run) or not do_apply

    if do_dry and not do_apply:
        print("\nDry-run complete. Re-run with --apply to perform the moves.")
        return 0

    log_path = (result_dir / "_logs" / f"sort-log-{now_stamp()}.csv").resolve()
    print(f"\nApplying moves... Log: {log_path}")
    apply_plan(plan, log_path=log_path)
    print("Done.")
    print(f"Log saved to: {log_path}")
    print("To undo: rerun with --undo <log.csv> --apply")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())