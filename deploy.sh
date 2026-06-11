#!/bin/bash
# ===================================
# A股自选股智能分析系统 - 一键部署脚本
# 适用环境: Ubuntu 24, 2c2g
# ===================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 项目目录
PROJECT_DIR="/opt/stock-analyzer"
DATA_DIR="/opt/stock-analyzer/data"
LOG_DIR="/opt/stock-analyzer/logs"
REPORT_DIR="/opt/stock-analyzer/reports"

# ===================================
# 步骤 1: 检查系统环境
# ===================================
check_system() {
    log_info "步骤 1/6: 检查系统环境..."
    
    # 检查是否为 root 或 sudo 用户
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo &> /dev/null; then
            SUDO=sudo
        else
            log_error "需要 sudo 权限，请以 root 用户运行或安装 sudo"
            exit 1
        fi
    else
        SUDO=""
    fi
    
    # 检查 Ubuntu 版本
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" != "ubuntu" ]]; then
            log_warn "检测到非 Ubuntu 系统，部分命令可能需要调整"
        fi
        log_info "系统: $NAME $VERSION"
    fi
    
    # 检查内存
    TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
    log_info "内存: ${TOTAL_MEM}MB"
    
    if [[ $TOTAL_MEM -lt 1500 ]]; then
        log_error "内存不足 2GB，当前 ${TOTAL_MEM}MB"
        exit 1
    fi
    
    # 检查磁盘空间（需要至少 5GB）
    AVAILABLE_DISK=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $AVAILABLE_DISK -lt 5 ]]; then
        log_error "磁盘空间不足，需要至少 5GB，当前 ${AVAILABLE_DISK}GB"
        exit 1
    fi
    log_info "可用磁盘空间: ${AVAILABLE_DISK}GB"
    
    log_info "系统检查完成 ✓"
}

# ===================================
# 步骤 2: 安装 Docker
# ===================================
install_docker() {
    log_info "步骤 2/6: 安装 Docker..."
    
    # 检查 Docker 是否已安装
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        log_info "Docker 已安装: $DOCKER_VERSION"
        
        # 检查 docker compose
        if docker compose version &> /dev/null; then
            log_info "Docker Compose 已安装"
        else
            log_warn "Docker Compose 未安装，正在安装..."
            $SUDO apt-get update
            $SUDO apt-get install -y docker-compose-plugin
        fi
        return
    fi
    
    # 安装 Docker
    log_info "正在安装 Docker..."
    
    $SUDO apt-get update
    $SUDO apt-get install -y ca-certificates curl gnupg lsb-release
    
    # 添加 Docker GPG 密钥
    $SUDO install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
    
    # 添加 Docker 仓库
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker
    $SUDO apt-get update
    $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # 启动 Docker
    $SUDO systemctl start docker
    $SUDO systemctl enable docker
    
    # 将当前用户添加到 docker 组（避免每次用 sudo）
    CURRENT_USER=$(whoami)
    $SUDO usermod -aG docker $CURRENT_USER
    
    log_info "Docker 安装完成 ✓"
    log_warn "请重新登录终端使 docker 组权限生效，或运行: newgrp docker"
}

# ===================================
# 步骤 3: 创建项目目录
# ===================================
create_dirs() {
    log_info "步骤 3/6: 创建项目目录..."
    
    # 创建主目录
    $SUDO mkdir -p $PROJECT_DIR
    $SUDO mkdir -p $DATA_DIR
    $SUDO mkdir -p $LOG_DIR
    $SUDO mkdir -p $REPORT_DIR
    
    # 设置权限
    $SUDO chown -R $(whoami):$(whoami) $PROJECT_DIR
    
    log_info "项目目录创建完成 ✓"
    log_info "主目录: $PROJECT_DIR"
}

# ===================================
# 步骤 4: 配置环境变量
# ===================================
setup_env() {
    log_info "步骤 4/6: 配置环境变量..."
    
    ENV_FILE="$PROJECT_DIR/.env"
    
    if [[ -f $ENV_FILE ]]; then
        log_warn ".env 文件已存在，跳过创建"
        log_info "如需重新配置，请删除 $ENV_FILE 后重新运行"
        return
    fi
    
    # 创建 .env 文件
    cat > $ENV_FILE << 'EOF'
# ===================================
# A股自选股智能分析系统 - 配置文件
# ===================================

# 【必填】自选股列表（股票代码，用逗号分隔）
STOCK_LIST=600519,000858,300750,002594

# 【必填】AI 模型配置
# 推荐使用 AIHubMix（一个 Key 通吃 GPT/Claude/Gemini 等）
# 获取地址: https://aihubmix.com/?aff=CfMq
AIHUBMIX_KEY=your_aihubmix_key_here

# 【推荐配置】通知渠道
# 企业微信机器人 Webhook
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key_here

# 【可选】Tushare Pro Token（提高数据准确性）
# 注册地址: https://tushare.pro
# TUSHARE_TOKEN=your_tushare_token_here

# 【可选】定时任务配置
SCHEDULE_ENABLED=true
SCHEDULE_TIME=18:00
RUN_IMMEDIATELY=true
MARKET_REVIEW_ENABLED=true

# 【可选】选股功能
STOCK_SELECTOR_ENABLED=false
STOCK_SELECTOR_STRATEGY=aggressive
STOCK_SELECTOR_TOP_N=10

# Web 服务配置
WEBUI_ENABLED=true
WEBUI_HOST=0.0.0.0
WEBUI_PORT=8000

# 系统配置
REPORT_TYPE=full
REPORT_LANGUAGE=zh
LOG_LEVEL=INFO
MAX_WORKERS=3
EOF
    
    $SUDO chown $(whoami):$(whoami) $ENV_FILE
    
    log_info ".env 配置文件已创建: $ENV_FILE"
    log_warn "请编辑 $ENV_FILE 填入你的配置！"
}

# ===================================
# 步骤 5: 部署应用
# ===================================
deploy_app() {
    log_info "步骤 5/6: 部署应用..."
    
    # 复制项目文件（如果需要）
    if [[ ! -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        log_info "正在复制项目文件..."
        
        # 这里需要用户提供项目代码
        # 可以通过以下方式：
        # 1. 从 GitHub 克隆: git clone https://github.com/chenYanRen/daily_stock_analysis.git $PROJECT_DIR
        # 2. 或手动上传
        
        log_error "请先将项目代码放到 $PROJECT_DIR 目录"
        log_info "方法1 - 从 GitHub 克隆:"
        echo "  git clone https://github.com/chenYanRen/daily_stock_analysis.git $PROJECT_DIR"
        echo "  cd $PROJECT_DIR"
        echo "  然后重新运行此脚本"
        log_info "方法2 - 手动上传项目文件到 $PROJECT_DIR"
        exit 1
    fi
    
    cd $PROJECT_DIR
    
    # 构建 Docker 镜像
    log_info "正在构建 Docker 镜像（首次可能需要几分钟）..."
    $SUDO docker compose -f docker/docker-compose.yml build
    
    # 启动服务（定时模式 + Web界面）
    log_info "正在启动服务..."
    $SUDO docker compose -f docker/docker-compose.yml up -d
    
    log_info "应用部署完成 ✓"
}

# ===================================
# 步骤 6: 验证部署
# ===================================
verify_deploy() {
    log_info "步骤 6/6: 验证部署..."
    
    sleep 3
    
    # 检查容器状态
    echo ""
    log_info "Docker 容器状态:"
    $SUDO docker ps --filter "name=stock-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    
    # 检查服务是否正常运行
    if curl -s http://localhost:8000/health &> /dev/null; then
        log_info "✅ Web 服务运行正常: http://localhost:8000"
    else
        log_warn "Web 服务可能尚未就绪，请等待几秒后访问: http://localhost:8000"
    fi
    
    echo ""
    log_info "=========================================="
    log_info "🎉 部署完成！"
    log_info "=========================================="
    echo ""
    log_info "📍 访问地址:"
    echo "   - Web 界面: http://你的服务器IP:8000"
    echo "   - API 文档: http://你的服务器IP:8000/docs"
    echo ""
    log_info "📁 重要路径:"
    echo "   - 项目目录: $PROJECT_DIR"
    echo "   - 日志目录: $LOG_DIR"
    echo "   - 报告目录: $REPORT_DIR"
    echo "   - 配置文件: $PROJECT_DIR/.env"
    echo ""
    log_info "🔧 常用命令:"
    echo "   - 查看日志: cd $PROJECT_DIR && docker compose -f docker/docker-compose.yml logs -f"
    echo "   - 重启服务: cd $PROJECT_DIR && docker compose -f docker/docker-compose.yml restart"
    echo "   - 停止服务: cd $PROJECT_DIR && docker compose -f docker/docker-compose.yml down"
    echo "   - 更新代码: cd $PROJECT_DIR && git pull && docker compose -f docker/docker-compose.yml up -d --build"
    echo ""
    log_warn "⚠️ 记得修改 $PROJECT_DIR/.env 配置文件，填入你的 AI Key 和通知渠道！"
}

# ===================================
# 主流程
# ===================================
main() {
    echo "=========================================="
    echo "  A股自选股智能分析系统 - 一键部署"
    echo "  适用: Ubuntu 24, 2c2g+"
    echo "=========================================="
    echo ""
    
    check_system
    install_docker
    create_dirs
    setup_env
    deploy_app
    verify_deploy
}

# 运行
main "$@"
