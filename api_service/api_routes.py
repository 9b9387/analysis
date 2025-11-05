"""
API路由 - Flask路由处理
"""
import os
import logging
from flask import Blueprint, request, jsonify

from .task_manager import TaskManager, TaskStatus
from .task_processor import TaskProcessor
from .cos_downloader import COSDownloader


# 创建Blueprint
api_bp = Blueprint('api', __name__)

# 全局管理器（将在app.py中初始化）
task_manager: TaskManager = None
task_processor: TaskProcessor = None


def init_managers(tm: TaskManager, tp: TaskProcessor):
    """初始化管理器"""
    global task_manager, task_processor
    task_manager = tm
    task_processor = tp


@api_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'message': 'Mahjong Analysis API is running'
    })


@api_bp.route('/analysis', methods=['POST'])
def create_analysis():
    """
    创建分析任务
    
    请求体:
    {
        "cos_path": "egg/uuid/2025-10-15",
        "prompt": "分析提示词",
        "name": "任务名称",  // 可选，任务标识名称
        "force_reanalyze": false  // 可选，是否强制重新分析已有JSON的图片，默认false
    }
    
    返回:
    {
        "task_id": "uuid",
        "status": "pending",
        "message": "任务已创建"
    }
    """
    try:
        # 解析请求
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '请求体不能为空'}), 400
        
        cos_path = data.get('cos_path')
        prompt = data.get('prompt')
        name = data.get('name', '')
        force_reanalyze = data.get('force_reanalyze', False)
        
        # 验证参数
        if not cos_path:
            return jsonify({'error': 'cos_path参数不能为空'}), 400
        
        if not prompt:
            return jsonify({'error': 'prompt参数不能为空'}), 400
        
        # 创建任务
        task_id = task_manager.create_task(cos_path, prompt, force_reanalyze, name)
        
        # 启动任务处理
        task_processor.start_task(task_id)
        
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'message': '任务已创建',
            'name': name,
            'force_reanalyze': force_reanalyze
        }), 201
    
    except Exception as e:
        logging.error(f"创建任务失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/<task_id>', methods=['GET'])
def get_analysis_status(task_id: str):
    """
    查询任务状态
    
    返回:
    {
        "task_id": "uuid",
        "status": "completed",
        "progress": 100,
        "message": "分析完成",
        "created_at": "2025-10-27T10:00:00",
        "updated_at": "2025-10-27T10:05:00",
        "result_file": "/path/to/result.txt",
        "cache_used": true
    }
    """
    try:
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        
        task_dict = task.to_dict()
        
        return jsonify(task_dict)
    
    except Exception as e:
        logging.error(f"查询任务失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务
    
    查询参数:
        status: 过滤任务状态 (pending, downloading, analyzing, merging, completed, failed)
        page: 页码，从1开始 (默认: 1)
        page_size: 每页数量 (默认: 20)
        limit: 限制返回数量 (已废弃，建议使用page和page_size)
    
    返回:
    {
        "tasks": [
            {
                "task_id": "uuid",
                "status": "completed",
                "progress": 100,
                ...
            }
        ],
        "total": 100,
        "page": 1,
        "page_size": 20,
        "total_pages": 5
    }
    """
    try:
        # 获取查询参数
        status_filter = request.args.get('status')
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=20, type=int)
        limit = request.args.get('limit', type=int)  # 向后兼容
        
        # 验证分页参数
        if page < 1:
            return jsonify({'error': '页码必须大于0'}), 400
        if page_size < 1:
            return jsonify({'error': '每页数量必须大于0'}), 400
        if page_size > 100:
            return jsonify({'error': '每页数量不能超过100'}), 400
        
        # 获取所有任务
        tasks = list(task_manager.tasks.values())
        
        # 过滤状态
        if status_filter:
            try:
                status_enum = TaskStatus(status_filter)
                tasks = [t for t in tasks if t.status == status_enum]
            except ValueError:
                return jsonify({'error': f'无效的状态: {status_filter}'}), 400
        
        # 按创建时间倒序排序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # 计算总数
        total = len(tasks)
        
        # 计算分页
        if limit and limit > 0:
            # 向后兼容limit参数
            tasks = tasks[:limit]
            total_pages = 1
            page = 1
            page_size = limit
        else:
            # 使用分页
            total_pages = (total + page_size - 1) // page_size  # 向上取整
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            tasks = tasks[start_index:end_index]
        
        # 转换为字典
        task_list = [t.to_dict() for t in tasks]
        
        return jsonify({
            'tasks': task_list,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        })
    
    except Exception as e:
        logging.error(f"列出任务失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/search/<name>', methods=['GET'])
def search_tasks_by_name(name: str):
    """
    根据任务名称搜索任务
    
    参数:
        name: 任务名称（路径参数）
    
    查询参数:
        status: 过滤任务状态 (pending, downloading, analyzing, merging, completed, failed)
        limit: 限制返回数量
    
    返回:
    {
        "name": "任务名称",
        "tasks": [
            {
                "task_id": "uuid",
                "name": "任务名称",
                "status": "completed",
                "progress": 100,
                ...
            }
        ],
        "total": 5
    }
    """
    try:
        # 获取查询参数
        status_filter = request.args.get('status')
        limit = request.args.get('limit', type=int)
        
        # 获取所有任务并过滤名称
        tasks = [t for t in task_manager.tasks.values() if t.name == name]
        
        # 过滤状态
        if status_filter:
            try:
                status_enum = TaskStatus(status_filter)
                tasks = [t for t in tasks if t.status == status_enum]
            except ValueError:
                return jsonify({'error': f'无效的状态: {status_filter}'}), 400
        
        # 按创建时间倒序排序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # 限制数量
        if limit and limit > 0:
            tasks = tasks[:limit]
        
        # 转换为字典
        task_list = [t.to_dict() for t in tasks]
        
        return jsonify({
            'name': name,
            'tasks': task_list,
            'total': len(task_list)
        })
    
    except Exception as e:
        logging.error(f"搜索任务失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/<task_id>/result', methods=['GET'])
def get_analysis_result(task_id: str):
    """
    获取任务最终结果（以JSON格式返回txt文件内容）
    
    返回:
    {
        "task_id": "uuid",
        "status": "completed",
        "result_file": "/path/to/result.txt",
        "content": "文件内容...",
        "size": 12345,
        "created_at": "2025-10-27T10:00:00"
    }
    """
    try:
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        
        if task.status != TaskStatus.COMPLETED:
            return jsonify({'error': '任务尚未完成'}), 400
        
        if not task.result_file or not os.path.exists(task.result_file):
            return jsonify({'error': '结果文件不存在'}), 404
        
        # 读取文件内容
        with open(task.result_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 获取文件名并添加_merged后缀
        filename = os.path.basename(task.result_file)
        name, ext = os.path.splitext(filename)
        merged_filename = f"{name}_merged{ext}"
        merged_file_path = os.path.join(os.path.dirname(task.result_file), merged_filename)
        
        # 读取merged文件内容作为analysis_data
        analysis_data = ""
        if os.path.exists(merged_file_path):
            with open(merged_file_path, 'r', encoding='utf-8') as f:
                analysis_data = f.read()
        # 获取文件大小
        file_size = os.path.getsize(task.result_file)
        
        return jsonify({
            'task_id': task_id,
            'status': task.status.value,
            'result_file': task.result_file,
            'content': content,
            'analysis_data': analysis_data,
            'size': file_size,
            'created_at': task.created_at,
            'updated_at': task.updated_at
        })
    
    except Exception as e:
        logging.error(f"获取任务结果失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/cos/list', methods=['GET'])
def list_cos_directory():
    """
    列出COS指定路径下的文件和文件夹
    
    查询参数:
        path: COS路径 (例如: egg/uuid/2025-10-15)
    
    返回:
    {
        "path": "egg/uuid/2025-10-15",
        "files": [
            {
                "name": "file1.png",
                "key": "egg/uuid/2025-10-15/file1.png",
                "size": 12345,
                "size_human": "12.1KB",
                "last_modified": "2025-10-27T10:00:00",
                "type": "file"
            }
        ],
        "directories": [
            {
                "name": "subdir",
                "key": "egg/uuid/2025-10-15/subdir/",
                "type": "directory"
            }
        ],
        "total_files": 10,
        "total_directories": 2
    }
    """
    try:
        # 获取路径参数
        cos_path = request.args.get('path', '')
        
        # 创建COS下载器
        downloader = COSDownloader()
        
        # 列出目录内容
        result = downloader.list_directory(cos_path)
        
        return jsonify(result)
    
    except Exception as e:
        logging.error(f"列出COS目录失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
