#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Prompt Processor - 启动检查
简化版本 - 只检查关键依赖
"""

import sys
import subprocess
import importlib

def install_package(package_name):
    """安装指定的包"""
    try:
        print(f"🔧 正在安装 {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--quiet"])
        print(f"✅ {package_name} 安装成功")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {package_name} 安装失败")
        return False

def check_and_install_dependency(lib_name, package_name=None):
    """检查并安装依赖"""
    if package_name is None:
        package_name = lib_name
    
    try:
        importlib.import_module(lib_name)
        return True
    except ImportError:
        print(f"⚠️ 缺少依赖: {lib_name}")
        return install_package(package_name)

def startup_check():
    """启动检查：验证并安装关键依赖"""
    print("🔍 Advanced Prompt Processor 依赖检查...")
    
    # 核心依赖映射 (import_name: pip_package_name)
    critical_deps = {
        'pandas': 'pandas>=1.3.0',
        'requests': 'requests>=2.25.0', 
        'numpy': 'numpy>=1.19.0',
        'urllib3': 'urllib3>=1.26.0',
        'openpyxl': 'openpyxl>=3.0.0'
    }
    
    all_success = True
    
    for lib_name, package_name in critical_deps.items():
        if not check_and_install_dependency(lib_name, package_name):
            all_success = False
    
    if all_success:
        print("✅ 所有核心依赖已就绪")
        return True
    else:
        print("❌ 部分依赖安装失败，请手动安装")
        return False

if __name__ == "__main__":
    startup_check()