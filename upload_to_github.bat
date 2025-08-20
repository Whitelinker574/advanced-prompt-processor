@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo 🚀 一键上传项目到GitHub
echo ================================

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装，请先安装Python
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python已安装

REM 检查GitHub CLI是否安装
gh --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ GitHub CLI未安装
    echo 请安装GitHub CLI: winget install GitHub.cli
    echo 或访问: https://cli.github.com/
    echo.
    echo 按任意键退出...
    pause >nul
    exit /b 1
)

echo ✅ GitHub CLI已安装

REM 检查GitHub CLI登录状态
gh auth status >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ 未登录GitHub CLI
    echo 🔐 正在启动登录...
    echo.
    gh auth login
    echo.
    echo 登录完成后请重新运行此脚本
    echo.
    echo 按任意键退出...
    pause >nul
    exit /b 1
)

echo ✅ GitHub CLI已登录

REM 配置代理（如果需要）
echo 🌐 检查网络连接...
set /p use_proxy="是否需要使用代理? (Y/n): "
if /i "%use_proxy%"=="" set use_proxy=Y
if /i "%use_proxy%"=="Y" (
    echo.
    echo 📋 常用代理配置:
    echo 1. http://127.0.0.1:7890  (Clash默认)
    echo 2. http://127.0.0.1:10809 (V2rayN默认)
    echo 3. http://127.0.0.1:1080  (其他代理)
    echo 4. 自定义代理
    echo.
    set /p proxy_choice="请选择代理类型 (1-4): "
    
    if "%proxy_choice%"=="1" (
        set proxy_url=http://127.0.0.1:7890
    ) else if "%proxy_choice%"=="2" (
        set proxy_url=http://127.0.0.1:10809
    ) else if "%proxy_choice%"=="3" (
        set proxy_url=http://127.0.0.1:1080
    ) else if "%proxy_choice%"=="4" (
        set /p proxy_url="请输入代理地址 (如: http://127.0.0.1:7890): "
    ) else (
        set proxy_url=http://127.0.0.1:7890
    )
    
    echo 🔧 设置代理: !proxy_url!
    git config --global http.proxy !proxy_url!
    git config --global https.proxy !proxy_url!
    echo ✅ 代理设置完成
) else (
    echo 🔧 清除代理设置...
    git config --global --unset http.proxy 2>nul
    git config --global --unset https.proxy 2>nul
    echo ✅ 不使用代理
)

echo.

REM 配置Git用户信息
echo 🔧 检查Git配置...
git config --global user.name >nul 2>&1
if errorlevel 1 (
    echo 设置Git用户信息...
    git config --global user.name "Whitelinker574"
    git config --global user.email "Whitelinker574@users.noreply.github.com"
    echo ✅ Git配置完成
) else (
    echo ✅ Git已配置
)

REM 获取仓库信息
set /p repo_name="请输入仓库名称 (默认: advanced-prompt-processor): "
if "%repo_name%"=="" set repo_name=advanced-prompt-processor

set /p description="请输入仓库描述 (可选): "
if "%description%"=="" set description=Advanced Prompt Processor for ComfyUI - 高级提示词处理器

echo.
echo 📊 项目信息:
echo   仓库名称: %repo_name%
echo   仓库描述: %description%
echo.

set /p confirm="确认上传? (Y/n): "
if /i "%confirm%"=="n" (
    echo ❌ 用户取消操作
    pause
    exit /b 1
)

echo.
echo 🔄 开始上传流程...

REM 初始化Git仓库
if not exist ".git" (
    echo 🔄 初始化Git仓库...
    git init
    if errorlevel 1 (
        echo ❌ Git仓库初始化失败
        pause
        exit /b 1
    )
    echo ✅ Git仓库初始化成功
) else (
    echo ✅ Git仓库已存在
)

REM 添加文件
echo 🔄 添加文件到Git...
git add .
if errorlevel 1 (
    echo ❌ 添加文件失败
    pause
    exit /b 1
)

REM 提交文件
echo 🔄 提交文件...
git commit -m "Initial commit: Advanced Prompt Processor for ComfyUI"
if errorlevel 1 (
    echo ❌ 文件提交失败
    pause
    exit /b 1
)
echo ✅ 文件提交成功

REM 创建GitHub仓库
echo 🔄 创建GitHub仓库...
gh repo create %repo_name% --public --description "%description%"
if errorlevel 1 (
    echo ⚠️  仓库可能已存在，继续推送...
)

REM 添加远程仓库
git remote add origin https://github.com/Whitelinker574/%repo_name%.git 2>nul
git remote set-url origin https://github.com/Whitelinker574/%repo_name%.git

REM 推送到GitHub
echo 🔄 推送代码到GitHub...
git branch -M main

REM 推送重试机制
set retry_count=0
:retry_push
set /a retry_count+=1
echo 尝试第 !retry_count! 次推送...

git push -u origin main
if not errorlevel 1 (
    echo ✅ 推送成功！
    goto push_success
)

if !retry_count! lss 3 (
    echo ⚠️  推送失败，10秒后重试...
    timeout /t 10 /nobreak >nul
    goto retry_push
) else (
    echo.
    echo ❌ 推送失败，已重试 3 次
    echo.
    echo 🔧 可能的解决方案:
    echo 1. 检查网络连接
    echo 2. 检查代理设置
    echo 3. 手动执行: git push -u origin main
    echo.
    set /p manual_retry="是否手动重试推送? (Y/n): "
    if /i "!manual_retry!"=="" set manual_retry=Y
    if /i "!manual_retry!"=="Y" (
        echo 🔄 手动重试推送...
        git push -u origin main
        if not errorlevel 1 (
            echo ✅ 推送成功！
            goto push_success
        )
    )
    echo ❌ 推送失败
    pause
    exit /b 1
)

:push_success

echo.
echo ================================
echo 🎉 项目成功上传到GitHub!
echo 🔗 仓库地址: https://github.com/Whitelinker574/%repo_name%
echo ================================
echo.
echo 按任意键退出...
pause >nul
