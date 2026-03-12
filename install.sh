#!/bin/bash

# 手机控制技能包安装脚本
# 支持 macOS、Ubuntu/Debian、CentOS/RHEL

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# 打印信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" &> /dev/null
}

# 安装 macOS 依赖
install_macos() {
    info "检测到 macOS 系统"

    if ! command_exists brew; then
        error "未检测到 Homebrew，请先安装: https://brew.sh"
        exit 1
    fi

    info "安装系统依赖..."
    brew install android-platform-tools scrcpy tesseract ffmpeg || warn "部分包可能已安装"

    # 安装 Tesseract 中文语言包
    if ! brew list tesseract-lang &>/dev/null; then
        info "安装 Tesseract 语言包..."
        brew install tesseract-lang || warn "语言包安装失败，可手动下载"
    fi
}

# 安装 Debian/Ubuntu 依赖
install_debian() {
    info "检测到 Debian/Ubuntu 系统"

    info "更新软件包列表..."
    sudo apt-get update

    info "安装系统依赖..."
    sudo apt-get install -y \
        android-tools-adb \
        android-tools-fastboot \
        scrcpy \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        tesseract-ocr-eng \
        ffmpeg \
        libsm6 \
        libxext6
}

# 安装 CentOS/RHEL 依赖
install_rhel() {
    info "检测到 CentOS/RHEL 系统"

    info "安装 EPEL 仓库..."
    sudo yum install -y epel-release || sudo dnf install -y epel-release

    info "安装系统依赖..."
    sudo yum install -y \
        android-tools \
        tesseract \
        tesseract-langpack-chi_sim \
        ffmpeg || warn "部分包可能需要手动安装"

    # Scrcpy 可能需要手动编译安装
    warn "Scrcpy 可能需要手动编译安装，参考: https://github.com/Genymobile/scrcpy/blob/master/BUILD.md"
}

# 安装 Python 依赖
install_python_deps() {
    info "安装 Python 依赖..."

    # 检查 Python 版本
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    required_version="3.10"

    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        warn "Python 版本 $python_version 可能不完全兼容，建议升级到 3.10+"
    fi

    # 安装依赖
    pip3 install -r requirements.txt || pip install -r requirements.txt
}

# 验证安装
verify_installation() {
    info "验证安装..."

    local all_ok=true

    # 检查系统命令
    for cmd in adb scrcpy tesseract ffmpeg; do
        if command_exists $cmd; then
            info "✓ $cmd 已安装"
        else
            warn "✗ $cmd 未找到"
            all_ok=false
        fi
    done

    # 检查 Python 包
    python3 -c "import fastapi, uvicorn, ppadb, cv2, pytesseract, PIL, numpy" 2>/dev/null && \
        info "✓ Python 依赖已安装" || { warn "✗ Python 依赖未完全安装"; all_ok=false; }

    if $all_ok; then
        echo ""
        info "${GREEN}所有依赖安装成功！${NC}"
        info "启动服务: uvicorn main:app --reload"
    else
        echo ""
        warn "部分依赖未安装，请查看上述日志"
        exit 1
    fi
}

# 主函数
main() {
    echo "========================================"
    echo "  手机控制技能包安装脚本"
    echo "========================================"
    echo ""

    # 检测操作系统
    OS=$(detect_os)
    info "检测到操作系统: $OS"

    # 根据系统安装依赖
    case $OS in
        macos)
            install_macos
            ;;
        debian)
            install_debian
            ;;
        rhel)
            install_rhel
            ;;
        *)
            error "不支持的操作系统: $OSTYPE"
            exit 1
            ;;
    esac

    # 安装 Python 依赖
    install_python_deps

    # 验证安装
    echo ""
    verify_installation
}

# 执行主函数
main "$@"
