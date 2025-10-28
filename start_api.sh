#!/bin/bash

# 麻将分析 API 服务启动脚本

echo "===================================="
echo "麻将分析 API 服务启动"
echo "===================================="

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到 python 命令"
    exit 1
fi

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "激活虚拟环境..."
    source .venv/bin/activate
else
    echo "警告: 未找到虚拟环境 .venv"
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 文件"
    echo "请创建 .env 文件并配置必要的环境变量"
fi

# 检查依赖
echo "检查依赖包..."
python -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: Flask 未安装"
    echo "请运行: pip install -r requirements.txt"
    exit 1
fi

# 创建缓存目录
mkdir -p cache

# 启动服务
echo ""
echo "启动 API 服务..."
echo "访问地址: http://localhost:5000"
echo "健康检查: http://localhost:5000/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo "===================================="
echo ""

python start_api.py
