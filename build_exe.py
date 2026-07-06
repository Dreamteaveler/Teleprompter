#!/usr/bin/env python3
# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 修改后按 GPL-3.0-or-later 分发。
#
"""提词器打包脚本 — 使用 PyInstaller 生成单个 exe

用法:
    python build_exe.py          # 构建 release 版本
    python build_exe.py --clean  # 清理后重新构建
    python build_exe.py --check  # 只检查依赖，不构建
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC_FILE = ROOT / "Teleprompter.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
EXE_NAME = "提词器1.10单文件版.exe"
PORTABLE_NAME = "提词器1.10便携版"
COLLECT_DIR = DIST_DIR / PORTABLE_NAME


def run(cmd: list[str], **kwargs):
    """运行命令，实时输出，失败时抛异常"""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"命令失败 (code={result.returncode}): {' '.join(cmd)}")


def clean():
    """清理旧构建产物"""
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            print(f"清理 {d}")
            shutil.rmtree(d)
    for p in ROOT.glob("*.spec"):
        if p.name != SPEC_FILE.name:
            print(f"清理 {p}")
            p.unlink()


def check_deps():
    """检查依赖是否已安装"""
    print("检查依赖...")
    deps = ["pyinstaller"] + [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    missing = []
    for dep in deps:
        pkg = dep.split(">=")[0].split("==")[0].strip()
        try:
            __import__(pkg.replace("-", "_"))
            print(f"  [OK] {pkg}")
        except ImportError:
            # pyinstaller 作为命令行工具不总能通过 __import__ 找到
            try:
                subprocess.run(
                    [sys.executable, "-c", f"import {pkg.replace('-','_')}"],
                    capture_output=True,
                )
                print(f"  [OK] {pkg}")
            except Exception:
                missing.append(dep)
                print(f"  [MISS] {dep}")

    if missing:
        print(f"\n缺少以下依赖: {missing}")
        print(f"请运行: pip install {' '.join(missing)}")
        sys.exit(1)

    print("所有依赖已满足。\n")


def build():
    """运行 PyInstaller"""
    print("=" * 60)
    print("  提词器 打包构建")
    print(f"  Spec: {SPEC_FILE}")
    print("=" * 60)

    install_pyinstaller()
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ])

    # 清理便携版 EXE 的中间产物（已在子文件夹中）
    leftover = DIST_DIR / "提词器.exe"
    if leftover.exists():
        leftover.unlink()

    exe_path = DIST_DIR / EXE_NAME
    collect_path = COLLECT_DIR
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print(f"  构建成功!")
        print(f"  单文件版: {exe_path}  ({size_mb:.1f} MB)")
        if collect_path.exists():
            print(f"  便携版:   {collect_path}\\")
        print("=" * 60)
    else:
        print(f"\n构建产物未找到: {exe_path}")
        sys.exit(1)


def install_pyinstaller():
    """确保 PyInstaller 已安装"""
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller 未安装，正在安装...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def main():
    args = sys.argv[1:]

    if "--check" in args:
        check_deps()
        return

    if "--clean" in args:
        clean()

    check_deps()
    build()


if __name__ == "__main__":
    main()
