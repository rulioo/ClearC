# 磁盘清理大师（ClearC）

扫描并清理系统与各磁盘垃圾数据、回收磁盘空间的 Windows 桌面工具。

## 功能

- **多盘扫描**：在概览页选择「全部磁盘」或指定盘符（C、D、E…）。系统垃圾（临时文件、更新缓存、缩略图等）仅针对 C 盘；**回收站与大文件分析**可作用于任意盘符。
- **扫描**：13 类垃圾数据（临时文件、更新缓存、回收站、缩略图、浏览器缓存、崩溃转储、旧日志、开发缓存、安装缓存、Windows.old、休眠文件、大文件分析），8 线程并行，实时进度。
- **报告**：分类 List 列表，可展开查看明细；**父节点与明细记录都可单独勾选**，父节点自动三态（全选/部分/全不选），支持导出 JSON / CSV / 文本。
- **清理**：以**展开明细中勾选的记录**为准执行清理；默认删除进**回收站**（可恢复），内置系统黑名单与二次校验；可选永久删除。
- **安全**：系统关键目录黑名单、路径合法性二次校验、占用文件跳过、清理前审计备份。

## 使用

### 运行源码
```bash
pip install -r requirements.txt

# GUI
python main.py

# CLI（扫描引擎验证）
python -m app list          # 列出所有垃圾分类（含作用域）
python -m app drives        # 列出可扫描的盘符及容量
python -m app scan -o report.json          # 扫全部盘（默认）
python -m app scan --drives C,D            # 只扫 C、D 盘
```

### 打包 exe
```bash
pip install pyinstaller
python tools/make_icon.py
python -m PyInstaller --noconfirm ClearC.spec
# 产物：dist/ClearC.exe
```

打包配置全部写在 `ClearC.spec` 里，**不要再在命令行堆参数**（会被 spec 覆盖或冲突）。
spec 中裁掉了未使用的 Qt 组件（QML/Quick、Pdf、Network、OpenGL、虚拟键盘、
90 多个翻译文件、OpenSSL 等），exe 由 47.4 MiB 降到 22.9 MiB（-51.8%）。
裁剪逻辑与保留清单见 spec 内注释——**改 `DROP_NAMES` 时务必确认没删掉
`qwindows.dll` / `qico.dll` / `Qt6Core|Gui|Widgets.dll`**，否则程序起不来或图标丢失。

## 目录结构
```
app/
  core/       # 模型、文件系统工具、安全规则、扫描/清理服务、报告导出
  categories/ # 分类扫描器（插件式）
  ui/         # PySide6 界面（主窗口、页面、对话框、后台线程）
tools/        # 图标生成、冒烟测试
main.py       # GUI 入口（打包目标）
```

## 说明
- 建议以**管理员身份**运行以完整扫描（含回收站）。
- 扫描到 Windows.old / 休眠文件等高风险项默认不勾选。
- 非 C 盘只扫描回收站与大文件分析（系统垃圾分类只针对 C 盘）；大文件分析仅列出、不会自动删除。
