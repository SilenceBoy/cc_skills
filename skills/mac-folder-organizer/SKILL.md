---
name: mac-folder-organizer
description: Organize files in a specified macOS folder into a "分类结果" directory with subfolders 表格/代码/视频/图片/文档/压缩包/安装包/演示文稿/其他 based on file extensions. Unclassified files are moved to "其他" folder by default. Default non-recursive. Always run a dry-run preview first, then apply only after user confirmation. Create missing folders, avoid overwriting by suffixing, write a CSV log, and support undo. Use when the user asks to 整理/归档/分类整理 a folder like Downloads/Desktop.
---

# mac-folder-organizer（Mac 文件夹分类整理）

## 目标

在用户指定的目标文件夹内，按文件后缀名进行分类整理：
- 输出根目录：`目标文件夹/分类结果/`
- 分类子目录（固定）：表格、代码、视频、图片、文档、压缩包、安装包、演示文稿、其他
- 未能识别分类的文件将自动移动到"其他"文件夹

## 必须遵守的安全规则（硬性）

1. 必须先 dry-run：先输出“将要移动”的预览清单（old -> new），并给出分类统计；用户确认后才能 apply。
2. 默认不递归扫描；只有用户明确说“递归”或同意递归，才允许递归。
3. 扫描时必须排除 `分类结果/` 目录及其子目录（递归时尤其重要，避免重复整理）。
4. 不允许覆盖同名文件：若目标已存在同名文件，必须自动加后缀 `_001/_002...`。
5. 不删除文件；只做“移动”整理（move）。
6. apply 执行时必须写 CSV 日志（old_path,new_path,status,error），并告诉用户如何 undo。

## 交互式确认点

在执行 apply 前，必须确认三件事：
- 目标路径是否正确？
- 是否递归扫描？（默认否）
- 预览无误后是否开始 apply？

## 实现方式

使用随 Skill 提供的脚本执行（由 Claude Code 通过 Bash 运行）：

mac-folder-organizer/scripts/organize_folder.py

## 使用示例

### 1) 默认：不递归 dry-run（必须先做）

```bash
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/ABS/PATH/TO/TARGET" \
  --dry-run
```

### 2) 确认后执行 apply
```bash
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/ABS/PATH/TO/TARGET" \
  --apply
```

### 3) 若用户确认递归（可选）
```bash
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/ABS/PATH/TO/TARGET" \
  --recursive \
  --dry-run
```

### 4) 撤销（用 apply 产生的日志）
```bash
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --undo "/ABS/PATH/TO/分类结果/_logs/sort-log-YYYYMMDD-HHMMSS.csv" \
  --apply
```
