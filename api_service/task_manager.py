"""
任务管理器 - 管理分析任务的状态和缓存
"""
import os
import json
import uuid
import threading
from enum import Enum
from typing import Dict, Optional
from datetime import datetime


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    DOWNLOADING = "downloading"   # 下载中
    ANALYZING = "analyzing"       # 分析中
    MERGING = "merging"          # 合并分析中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败


class Task:
    """任务对象"""
    
    def __init__(self, task_id: str, cos_path: str, prompt: str):
        self.task_id = task_id
        self.cos_path = cos_path
        self.prompt = prompt
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.progress = 0
        self.message = ""
        self.error = None
        self.result_file = None
        self.cache_used = False
        
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'cos_path': self.cos_path,
            'prompt': self.prompt,
            'status': self.status.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'progress': self.progress,
            'message': self.message,
            'error': self.error,
            'result_file': self.result_file,
            'cache_used': self.cache_used
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """从字典创建任务对象"""
        task = cls(data['task_id'], data['cos_path'], data['prompt'])
        task.status = TaskStatus(data['status'])
        task.created_at = data['created_at']
        task.updated_at = data['updated_at']
        task.progress = data['progress']
        task.message = data['message']
        task.error = data.get('error')
        task.result_file = data.get('result_file')
        task.cache_used = data.get('cache_used', False)
        return task


class TaskManager:
    """任务管理器 - 线程安全的任务状态管理"""
    
    def __init__(self, storage_file: str = './tasks.json', cache_root: str = './cache'):
        self.storage_file = storage_file
        self.cache_root = cache_root
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
        
        # 创建缓存根目录
        os.makedirs(self.cache_root, exist_ok=True)
        
        # 加载已有任务
        self._load_tasks()
    
    def create_task(self, cos_path: str, prompt: str) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task = Task(task_id, cos_path, prompt)
        
        with self.lock:
            self.tasks[task_id] = task
            self._save_tasks()
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, status: TaskStatus = None, 
                   progress: int = None, message: str = None, 
                   error: str = None, result_file: str = None,
                   cache_used: bool = None):
        """更新任务状态"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            
            if status:
                task.status = status
            if progress is not None:
                task.progress = progress
            if message is not None:
                task.message = message
            if error is not None:
                task.error = error
            if result_file is not None:
                task.result_file = result_file
            if cache_used is not None:
                task.cache_used = cache_used
            
            task.updated_at = datetime.now().isoformat()
            self._save_tasks()
    
    def get_cache_dir(self, cos_path: str) -> str:
        """获取缓存目录路径"""
        # 从COS路径提取目录名
        path_parts = cos_path.strip('/').split('/')
        cache_name = '_'.join(path_parts)
        cache_dir = os.path.join(self.cache_root, cache_name)
        return cache_dir
    
    def check_cache_exists(self, cos_path: str) -> bool:
        """检查缓存是否存在"""
        cache_dir = self.get_cache_dir(cos_path)
        
        # 检查目录是否存在且包含PNG文件
        if not os.path.exists(cache_dir):
            return False
        
        # 检查是否有PNG文件
        png_files = [f for f in os.listdir(cache_dir) if f.endswith('.png')]
        return len(png_files) > 0
    
    def get_cached_png_files(self, cos_path: str) -> list:
        """获取缓存的PNG文件列表"""
        cache_dir = self.get_cache_dir(cos_path)
        if not os.path.exists(cache_dir):
            return []
        
        png_files = []
        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.png'):
                    png_files.append(os.path.join(root, file))
        
        return sorted(png_files)
    
    def _load_tasks(self):
        """从文件加载任务"""
        if not os.path.exists(self.storage_file):
            return
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for task_data in data.get('tasks', []):
                    task = Task.from_dict(task_data)
                    self.tasks[task.task_id] = task
        except Exception as e:
            print(f"加载任务失败: {e}")
    
    def _save_tasks(self):
        """保存任务到文件"""
        try:
            data = {
                'tasks': [task.to_dict() for task in self.tasks.values()]
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存任务失败: {e}")
