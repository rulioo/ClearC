# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 exe，已裁剪未使用的 Qt 组件。

打包方式（配置以本文件为准，不要再在命令行堆参数）：

    python -m PyInstaller ClearC.spec

本程序只用到 QtCore / QtGui / QtWidgets，但 PySide6 的 hook 会把整套 Qt 都收进来。
下面把这些没用到的组件排除，实测可把 exe 从 47.4 MiB 降到约 24 MiB。

排除分两层，缺一不可：
  1. EXCLUDES —— 让 PyInstaller 不去分析这些 Python 模块，从源头断掉依赖；
  2. _keep() —— 模块排除后，hook 仍可能按目录收集 DLL / 插件 / 翻译，
     在 Analysis 之后按文件名把它们从打包结果里剔掉。
"""
from __future__ import annotations

# ---------- 第一层：不参与分析的 Python 模块 ----------
EXCLUDES = [
    # 未使用的 Qt 模块
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvgWidgets",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtWebChannel",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSpatialAudio",
    "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech",
    "PySide6.QtXml",
    "PySide6.QtConcurrent",
    "PySide6.QtDBus",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    # 标准库里用不到的大家伙
    "tkinter",
    "unittest",
    "doctest",
    "pydoc",
    "pdb",
    "difflib",
    "lib2to3",
    "distutils",
    "setuptools",
    "pip",
    # 本程序不做网络通信，_ssl 只是被间接牵连进来的（省下约 4.5 MiB）
    "ssl",
    "_ssl",
    # 只被 tools/ 用到，不随程序分发
    "PIL",
    "numpy",
    "playwright",
]

# ---------- 第二层：从打包结果里剔除的文件（按小写文件名匹配）----------
# 保留清单（务必别误删）：qwindows.dll / qoffscreen.dll / qico.dll /
# qmodernwindowsstyle.dll / Qt6Core|Gui|Widgets.dll / pyside6.abi3.dll
DROP_NAMES = {
    # 软件 OpenGL 回退（Mesa llvmpipe）——纯 Widgets 程序用不到，单项最大
    "opengl32sw.dll",
    # QML / Quick 运行时
    "qt6qml.dll",
    "qt6quick.dll",
    "qt6qmlmodels.dll",
    "qt6qmlmeta.dll",
    "qt6qmlworkerscript.dll",
    # 其它未使用的 Qt 模块
    "qt6pdf.dll",
    "qt6network.dll",
    "qt6opengl.dll",
    "qt6virtualkeyboard.dll",
    "qtnetwork.pyd",
    # 平台插件：只需要 qwindows，qoffscreen 留着便于无窗口自检
    "qdirect2d.dll",
    "qminimal.dll",
    # 图片格式插件：程序只显示 .ico（qico.dll 保留），不加载用户图片
    "qgif.dll",
    "qicns.dll",
    "qjpeg.dll",
    "qpdf.dll",
    "qsvg.dll",
    "qtga.dll",
    "qtiff.dll",
    "qwbmp.dll",
    "qwebp.dll",
    "qsvgicon.dll",
    # 触屏 / 虚拟键盘 / 网络状态 / TLS 后端
    "qtuiotouchplugin.dll",
    "qtvirtualkeyboardplugin.dll",
    "qnetworklistmanager.dll",
    "qcertonlybackend.dll",
    "qopensslbackend.dll",
    "qschannelbackend.dll",
    # OpenSSL：TLS 后端都删了，没有任何东西会加载它。
    # 实测运行中的进程只载入 Qt6Core/Gui/Widgets，确认是死重。
    "libcrypto-3.dll",
    "libcrypto-3-x64.dll",
    "libssl-3.dll",
    "libssl-3-x64.dll",
}

# 只保留简体中文和英文的 Qt 翻译，其余 90 多个 .qm 全部丢弃
KEEP_TRANSLATIONS = {"qt_zh_cn.qm", "qtbase_zh_cn.qm", "qt_en.qm", "qtbase_en.qm"}


def _keep(name: str) -> bool:
    """判断某个打包条目是否保留。name 形如 'PySide6\\\\translations\\\\qt_ar.qm'。"""
    low = name.lower().replace("/", "\\")
    base = low.rsplit("\\", 1)[-1]
    if "\\translations\\" in low:
        return base in KEEP_TRANSLATIONS
    return base not in DROP_NAMES


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("app.ico", ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

# 模块排除之后，hook 仍可能按目录把 DLL / 插件 / 翻译收进来，这里再筛一遍
a.binaries = [e for e in a.binaries if _keep(e[0])]
a.datas = [e for e in a.datas if _keep(e[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ClearC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # 不用 UPX：本机没装，且 UPX 压缩过的 exe 极易被杀毒软件误报，
    # 对一个清理工具来说得不偿失。
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["app.ico"],
)
