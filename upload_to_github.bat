@echo off
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
git push -u origin main
if errorlevel 1 (
    echo ❌ 推送失败
    pause
    exit /b 1
)

echo.
echo ================================
echo 🎉 项目成功上传到GitHub!
echo 🔗 仓库地址: https://github.com/Whitelinker574/%repo_name%
echo ================================
echo.
echo 按任意键退出...
pause >nul
