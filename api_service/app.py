"""
Flask应用主入口
"""
import logging
from flask import Flask, jsonify
from flask_cors import CORS

from . import config
from .task_manager import TaskManager
from .task_processor import TaskProcessor
from .api_routes import api_bp, init_managers


def create_app():
    """创建Flask应用"""
    # 创建Flask应用
    app = Flask(__name__)
    
    # 启用CORS - 允许所有来源
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建管理器
    task_manager = TaskManager(
        storage_file=config.TASK_STORAGE_FILE,
        cache_root=config.CACHE_ROOT_DIR
    )
    task_processor = TaskProcessor(task_manager)
    
    # 初始化路由管理器
    init_managers(task_manager, task_processor)
    
    # 注册蓝图
    app.register_blueprint(api_bp)
    
    # 添加错误处理器
    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden', 'message': str(e)}), 403
    
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not Found', 'message': str(e)}), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500
    
    # 添加根路径
    @app.route('/')
    def index():
        return {
            'name': 'Mahjong Analysis API',
            'version': '1.0.0',
            'endpoints': {
                'health': 'GET /health',
                'create_analysis': 'POST /analysis',
                'get_analysis_status': 'GET /analysis/<task_id>',
                'download_result': 'GET /analysis/<task_id>/download',
                'list_tasks': 'GET /tasks',
                'list_cos_directory': 'GET /cos/list?path=<cos_path>'
            }
        }
    
    return app


def run_server():
    """运行服务器"""
    app = create_app()
    
    # 打印配置信息
    print("\n" + "=" * 60)
    print("服务器配置:")
    print(f"  主机: {config.FLASK_HOST}")
    print(f"  端口: {config.FLASK_PORT}")
    print(f"  调试模式: {config.FLASK_DEBUG}")
    print(f"  缓存目录: {config.CACHE_ROOT_DIR}")
    print(f"  任务存储: {config.TASK_STORAGE_FILE}")
    print("=" * 60 + "\n")
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    run_server()
