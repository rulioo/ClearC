# 磁盘清理大师（ClearC）— 进度存档

> 最后更新：2026-09-27
> 当前版本：`0.1.0`（见 `app/__init__.py`）
> 状态：**功能完整，可打包分发**；18/18 冒烟测试通过，`dist\ClearC.exe`（22.9 MiB）
> 已构建并验证启动。

---

## 一、这是什么

面向 Windows 的磁盘垃圾扫描与清理桌面工具，中文界面，PySide6（Qt6）实现，
PyInstaller 打包为单文件 exe。开发方：北京赛兰博科技发展有限公司。

| 项 | 值 |
| --- | --- |
| 项目根目录 | `E:\cc\clearC` |
| 入口 | `main.py` → `app/ui/main_window.py: run_gui()` |
| 可执行文件 | `dist\ClearC.exe` |
| 一键启动 | `一键启动.bat`（自动提权，优先跑 exe，回退跑源码） |
| 远程仓库 | https://github.com/rulioo/ClearC （公开，分支 `main`） |
| 图标 | `app.ico`（硬盘造型，多尺寸 16/24/32/48/64/128/256） |
| 代码规模 | 35 个 Python 文件（`app/` 32 + `tools/` 2 + `main.py`） |

## 二、目录结构

```
app/
  __init__.py          APP_NAME / COPYRIGHT / __version__ 三个常量（改名只改这里）
  core/                与界面无关的核心逻辑
    models.py            CleanItem / CleanCategory / ScanReport / DiskInfo 等数据模型
    fsutils.py           目录大小、子项枚举、fmt_size、resource_path、drive_label
    safety.py            清理前校验：黑名单 + 必须在扫描结果中
    protect.py           加锁保护，清单存 %LOCALAPPDATA%\ClearC
    recycle.py           回收站删除（SHFileOperationW）
    scan_service.py      list_drives / disk_for / read_disk / build_tasks / scan
    clean_service.py     实际清理执行，返回逐项 CleanStatus
    report.py            JSON / CSV / TXT 报告导出
  categories/          13 个扫描分类，每个一个文件，统一在 __init__ 注册
  ui/
    main_window.py       左侧导航 + 页面堆叠 + 扫描/清理全流程接线
    pages.py             OverviewPage / ScanPage / ResultPage / SettingsPage / AboutPage
    widgets.py           DonutChart（同心圆环形图）
    dialogs.py           清理确认 / 清理进度 / 清理完成
    workers.py           ScanWorker（QThread）
    theme.py             QSS 样式表（f-string，注意双大括号）
tools/
  make_icon.py         用 PIL 绘制硬盘图标并生成多尺寸 app.ico
  smoke_test.py        offscreen 冒烟测试，18 项断言
```

## 三、已实现功能

**扫描**
- 多盘选择（当前机器：C D E F G H），概览页下拉勾选，支持「全部磁盘」
- 13 个分类：用户临时文件、系统临时文件、Windows 更新缓存、回收站、缩略图缓存、
  浏览器缓存、崩溃转储与错误报告、日志文件、开发工具缓存、软件安装缓存、
  旧版 Windows、休眠文件、大文件分析（>500MB）
- 分类分两种作用域：`system` 只跑系统盘，`drive` 按盘符实例化（回收站、大文件）
- 8 线程并行扫描，实时进度回调，可取消
- 扫描页：同心圆环图 —— **外环蓝色 = 扫描盘容量使用率，内环绿色 = 扫描进度**，底部图例
- 扫描完成提示含盘信息，如 `C: 1系统 · 发现 13 个分类 · 共 12.8 GB 垃圾`

**结果**
- 可展开树：分类 → 明细，明细可单独勾选，父节点三态联动
- 清理以**明细勾选**为准，未勾选的一律不动
- 行悬停 = 浅蓝 `#EAF1FE`；选中 = 深蓝 `#2F6FED` + 白字；整行选中
- 右键菜单三项：打开所在文件夹 / 加锁保护 / 直接删除（进回收站）

**清理与安全**
- 默认删除到回收站（可恢复），永久删除需显式确认
- 黑名单硬拦截：`C:\Windows`（白名单子目录除外）、`Program Files`、`pagefile.sys` 等
- 双保险：待清理路径必须出现在本次扫描结果中，否则拒绝
- 可加锁保护文件：加锁项在结果页**不可勾选**、不参与父节点全选、清理一律拒绝
- 每次扫描可自动导出 JSON 备份到 `reports/`

**界面**
- 左侧导航四项：概览 / 扫描 / 设置 / 关于
- 概览页：磁盘容量环形图（蓝 `#2F6FED`）、盘符选择、上次扫描摘要、管理员状态
- 设置页：删除方式、是否二次确认、扫描线程数、自动导出备份；底部版权信息
- 关于页：图标、软件名、版本号、简介、版权信息

## 四、构建与运行

```bash
# 跑测试（18 项断言，不碰真实用户数据）
QT_QPA_PLATFORM=offscreen python tools/smoke_test.py

# 重新生成图标（改配色时）
python tools/make_icon.py

# 打包 exe —— 必须先杀掉正在运行的进程，否则 dist 被占用删不掉
taskkill //F //IM ClearC.exe
python -m PyInstaller --noconfirm ClearC.spec

# 查看打包结果里都有什么、谁占大头（裁剪体积时用）
python tools/bundle_report.py
```

**打包配置全部在 `ClearC.spec` 里**，不要再在命令行堆 `--onefile --windowed` 之类的
参数——会和 spec 冲突或被忽略。spec 已经进版本管理（`.gitignore` 里 `!ClearC.spec`）。

### 体积裁剪（47.4 MiB → 22.9 MiB，-51.8%）

程序只用 `QtCore / QtGui / QtWidgets`，但 PySide6 的 hook 会把整套 Qt 收进来。
`ClearC.spec` 分两层裁：

1. `EXCLUDES` —— 不参与分析的 Python 模块（QML/Quick、Pdf、Network、OpenGL、
   虚拟键盘、Sql、Test、`ssl`/`_ssl`、tkinter、PIL、numpy…），从源头断依赖；
2. `_keep()` —— 模块排除后 hook 仍会按目录收集 DLL / 插件 / 翻译，在 Analysis
   之后按文件名再筛一遍。

剔掉的大件（压缩后）：`opengl32sw.dll` 7.31 MiB、QML/Quick 栈约 5.2 MiB、
`Qt6Pdf` 2.35 MiB、OpenSSL 4.55 MiB（含 Python 与 Qt 各一份）、
96 个翻译文件 1.85 MiB、`Qt6Network` + 网络/TLS 插件约 1.3 MiB、多余平台插件与
图片格式插件约 1.6 MiB。

**保留清单（改 `DROP_NAMES` 时务必别误删）**：`qwindows.dll`（平台插件，没了程序
起不来）、`qico.dll`（读 `app.ico`，窗口图标与关于页要用）、`qoffscreen.dll`
（留着便于对打包结果做无窗口自检）、`Qt6Core|Gui|Widgets.dll`、`qmodernwindowsstyle.dll`。

**没用 UPX**：本机没装，且 UPX 压过的 exe 是杀毒软件误报的经典特征，清理工具本来
就容易触发 SmartScreen，不划算。spec 里显式 `upx=False` 并注明原因，免得以后有人
装了 UPX 导致构建结果悄悄变化。

**验证方法**：`MainWindowHandle` 在本环境恒为 0（会话不在交互式窗口站），不能据此
判断失败。改为**检查 GUI 进程实际加载的 DLL**——`qwindows.dll` 载入即证明平台插件
成功、窗口已建立（缺失时 Qt 会立即 `qFatal` 崩溃）。

给用户用：双击 `一键启动.bat` 即可（自动弹 UAC 提权）。

## 四之二、推送到 GitHub

```bash
git add -A && git commit -m "..." && git push
```

仓库地址 `https://github.com/rulioo/ClearC`，公开仓库，主分支 `main`。
认证走 Git Credential Manager（`credential.helper=manager`），凭据已缓存，无需每次登录。

**注意：这是公开仓库，提交前务必确认没混进本机数据。** `.gitignore` 已排除：

- `reports/` 以及根目录的 `clearC_report_*.json`、`report.json`
  —— 这些是**本机真实扫描报告**，含 `C:\Users\...` 下的实际文件路径、回收站条目、
  磁盘容量，属于个人使用痕迹，不能公开
- `build/`、`dist/`、`*.spec`、`desktop.ini`、`app_old.ico`

`.gitattributes` 锁定了 `*.bat` 为 `eol=crlf`，保证 GBK 编码的一键启动脚本在任何
平台 clone 下来都能直接双击运行（GBK 多字节字符的后续字节不会落在 0x0A/0x0D，
换行转换不会破坏编码）。

## 五、踩过的坑（改代码前先看这里）

1. **`一键启动.bat` 必须保持 GBK 编码 + CRLF 换行。**
   本机控制台代码页是 936，cmd 按 GBK 解析批处理文件；存成 UTF-8 会把中文
   当命令执行（报 `'xx' 不是内部或外部命令`）。另外 cmd 要求 CRLF，纯 LF
   会导致行在中途被截断。
   重新编码：`[System.IO.File]::WriteAllText($p, $s, [System.Text.Encoding]::GetEncoding(936))`

2. **打包后资源要从 `sys._MEIPASS` 读。** 统一走 `fsutils.resource_path()`，
   源码运行时它回退到项目根目录。

3. **`theme.py` 的 QSS 是 f-string**，所有 CSS 大括号要写成双大括号 `{{ }}`，
   否则 `.format` 报错或匹配不上。

4. **`QTreeWidgetItem` 默认就带 `ItemIsUserCheckable`**，要取消勾选能力必须
   `flags & ~Qt.ItemFlag.ItemIsUserCheckable`，不能靠"不加这个 flag"。

5. **测试脚本打印中文 / emoji 要 `PYTHONIOENCODING=utf-8`**，否则 GBK 控制台
   抛 `UnicodeEncodeError`。

6. **本环境 Read 工具无法显示 offscreen 渲染的 PNG。** 验证界面效果改用像素采样：
   `QT_QPA_PLATFORM=offscreen` + `widget.grab().save(png)` + PIL 取色，
   或 PowerShell `System.Drawing.Bitmap.GetPixel` 验 exe 图标。

## 六、待办 / 可选项

- [ ] 版本号仍是 `0.1.0`，正式发布前可提到 `1.0.0`（改 `app/__init__.py` 一行）
- [ ] exe 文件名仍是 `ClearC.exe`，如需中文名要同步改打包命令和 `一键启动.bat`
- [ ] **许可证未定**：仓库是公开的，但没放 LICENSE 文件，法律上默认「保留所有权利」。
      若打算开源需补 LICENSE；若保持闭源商用，建议在 README 里写明授权条款
- [ ] 代码签名：目前 exe 未签名，分发时 Windows SmartScreen 会提示未知发布者
- [x] ~~打包体积优化~~ 已完成：用 `ClearC.spec` 裁掉未使用的 Qt 组件，体积见上一节
- [ ] 还可再压：`Qt6Svg.dll`（0.25 MiB）理论上用不到，但 Windows 11 样式的
      `qmodernwindowsstyle` 是否依赖它没实测过，砍之前要先确认样式不坏
- [ ] `req.txt` 名字与 `requirements.txt` 太像，容易误认成依赖清单，其实是最初的需求
      描述。建议改名（如 `需求说明.md`），待确认
- [ ] 一条遗留提问：早前一轮修订里用户提到过 `3）…` 但话没说完，始终未澄清，
      如仍需要请补充说明
