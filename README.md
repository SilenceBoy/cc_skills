# Claude Code Skills Collection

这是一个 [Claude Code](https://claude.com/claude-code) 的自定义 Skills 集合,包含实用的 macOS 文件管理工具。

## 📦 包含的 Skills

### 1. mac-folder-organizer (文件夹分类整理)

自动按文件类型整理文件夹,将文件分类到对应的子目录中。

**功能特点:**
- 自动分类文件到固定的子目录:表格、代码、视频、图片、文档、压缩包、安装包、演示文稿、其他
- 输出到 `分类结果/` 目录,不影响原始文件夹结构
- 支持递归扫描(需用户确认)
- 干运行预览,确认后执行
- 自动处理同名文件冲突(添加 `_001`、`_002` 后缀)
- CSV 日志记录,支持撤销操作

**使用场景:**
- 整理杂乱的下载文件夹
- 归档桌面文件
- 批量分类项目文件

**使用方法:**

在 Claude Code 中直接使用自然语言命令:
```
整理我的下载文件夹
分类整理 /Users/xxx/Downloads
归档桌面文件
```

或者直接调用脚本:
```bash
# 1. 先预览
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/path/to/folder" \
  --dry-run

# 2. 确认后执行
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/path/to/folder" \
  --apply

# 3. 递归模式(可选)
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --path "/path/to/folder" \
  --recursive \
  --dry-run

# 4. 撤销操作
python3 ~/.claude/skills/mac-folder-organizer/scripts/organize_folder.py \
  --undo "/path/to/分类结果/_logs/sort-log-YYYYMMDD-HHMMSS.csv" \
  --apply
```

---

### 2. rename-images-by-date-added (按添加日期重命名图片)

批量重命名图片文件,使用 `{文件夹名}_{时间戳}.{扩展名}` 格式,基于 macOS Finder 的"添加日期"。

**功能特点:**
- 基于 macOS 的"添加日期"(kMDItemDateAdded)重命名
- 时间戳精确到毫秒: `YYYYMMDDHHMMSSmmm`
- 输出格式: `foldername_20251219151300111.jpg`
- 支持常见图片格式: jpg, png, heic, webp, gif, tif, bmp 等
- 自动处理时间戳冲突(添加 `_001`、`_002` 后缀)
- 干运行预览,确认后执行
- CSV 日志记录,支持撤销操作

**使用场景:**
- 整理相册照片,按添加时间排序
- 批量重命名下载的图片
- 统一图片命名格式

**使用方法:**

在 Claude Code 中直接使用自然语言命令:
```
按添加时间重命名这个文件夹的图片
重命名 /Users/xxx/Photos 里的照片
```

或者直接调用脚本:
```bash
# 1. 先预览
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --path "/path/to/photos" \
  --dry-run

# 2. 确认后执行
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --path "/path/to/photos" \
  --apply

# 3. 撤销操作
python3 ~/.claude/skills/rename-images-by-date-added/scripts/rename_images_by_date_added.py \
  --undo "/path/to/rename-log-YYYYMMDD-HHMMSS.csv" \
  --apply
```

---

## 🚀 安装方法

### 方法 1: 克隆整个仓库

```bash
# 克隆到 Claude Code skills 目录
cd ~/.claude/skills
git clone https://github.com/SilenceBoy/cc_skills.git

# 或者克隆到自定义目录后创建符号链接
git clone https://github.com/SilenceBoy/cc_skills.git ~/my-skills
ln -s ~/my-skills/skills/* ~/.claude/skills/
```

### 方法 2: 单独下载某个 Skill

```bash
cd ~/.claude/skills

# 下载 mac-folder-organizer
curl -L https://github.com/SilenceBoy/cc_skills/archive/main.tar.gz | tar xz --strip=2 "cc_skills-main/skills/mac-folder-organizer"

# 或下载 rename-images-by-date-added
curl -L https://github.com/SilenceBoy/cc_skills/archive/main.tar.gz | tar xz --strip=2 "cc_skills-main/skills/rename-images-by-date-added"
```

### 验证安装

重启 Claude Code 后,可以通过以下方式验证:

```bash
# 检查 skills 是否已加载
ls ~/.claude/skills/

# 应该能看到:
# mac-folder-organizer/
# rename-images-by-date-added/
```

---

## 📋 使用前提

- **操作系统**: macOS (这些 skills 依赖 macOS 特有的元数据)
- **Python**: Python 3.6+
- **Claude Code**: 已安装并配置 Claude Code CLI

---

## ⚠️ 安全提示

1. **先预览,后执行**: 所有 skills 都遵循"先 dry-run 预览,用户确认后才执行"的原则
2. **不会删除文件**: 只进行移动或重命名操作,不会删除任何文件
3. **冲突安全**: 自动处理同名文件冲突,避免覆盖
4. **可撤销**: 所有操作都会生成 CSV 日志,支持完整撤销
5. **日志位置**:
   - mac-folder-organizer: `分类结果/_logs/`
   - rename-images-by-date-added: 目标文件夹根目录

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

如果你开发了新的实用 Skill,欢迎贡献到这个仓库。

---

## 📄 许可证

MIT License

---

## 🔗 相关链接

- [Claude Code 官方文档](https://docs.anthropic.com/claude/docs)
- [如何创建自定义 Skills](https://docs.anthropic.com/claude/docs/claude-code-skills)

---

## 📝 更新日志

### 2025-12-19
- 初始版本发布
- 添加 mac-folder-organizer skill
- 添加 rename-images-by-date-added skill
