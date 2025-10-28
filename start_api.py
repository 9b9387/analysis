#!/usr/bin/env python3
"""
API服务启动脚本
"""
from api_service.app import run_server

if __name__ == '__main__':
    print("=" * 60)
    print("麻将分析 REST API 服务")
    print("=" * 60)
    print("\n正在启动服务...")
    print("\n访问 http://localhost:5000 查看API信息")
    print("访问 http://localhost:5000/health 进行健康检查")
    print("\n按 Ctrl+C 停止服务\n")
    print("=" * 60)
    
    run_server()
