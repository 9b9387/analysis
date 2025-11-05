"""
任务处理器 - 执行完整的分析任务流程
"""
import logging
import threading
from typing import Callable

from .task_manager import TaskManager, TaskStatus
from .cos_downloader import COSDownloader
from .gemini_analyzer import GeminiAnalyzer


class TaskProcessor:
    """任务处理器 - 编排完整的分析流程"""
    
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.logger = logging.getLogger(__name__)
    
    def process_task(self, task_id: str):
        """
        处理单个任务（在后台线程中执行）
        
        Args:
            task_id: 任务ID
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            self.logger.error(f"任务不存在: {task_id}")
            return
        
        try:
            cos_path = task.cos_path
            prompt = task.prompt
            cache_dir = self.task_manager.get_cache_dir(cos_path)
            
            # 步骤1: 检查缓存或下载PNG和JSON文件
            if self.task_manager.check_cache_exists(cos_path):
                self.logger.info(f"使用缓存: {cache_dir}")
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.DOWNLOADING,
                    progress=10,
                    message="使用本地缓存",
                    cache_used=True
                )
                png_files = self.task_manager.get_cached_png_files(cos_path)
            else:
                self.logger.info(f"开始下载文件: {cos_path}")
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.DOWNLOADING,
                    progress=10,
                    message="开始下载PNG和JSON文件"
                )
                
                # 下载PNG和JSON文件
                downloader = COSDownloader()
                
                def download_progress(current, total, msg):
                    progress = 10 + int(30 * current / total)
                    self.task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"下载进度: {current}/{total} - {msg}"
                    )
                
                downloaded_files = downloader.download_files(
                    cos_path,
                    cache_dir,
                    extensions=['.png', '.json'],
                    progress_callback=download_progress
                )
                
                png_files = downloaded_files.get('png', [])
                
                if not png_files:
                    raise ValueError(f"未找到PNG文件: {cos_path}")
                
                json_count = len(downloaded_files.get('json', []))
                self.logger.info(f"下载完成，共 {len(png_files)} 个PNG文件，{json_count} 个JSON文件")
            
            # 新增：限制最大分析图片数量为30，超过则直接标记任务失败并返回
            if png_files and len(png_files) > 30:
                self.logger.warning(f"任务 {task_id} 图片数量超限: {len(png_files)} > 30")
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    progress=0,
                    message=f"图片数量超过限制: {len(png_files)} > 30",
                    error="图片数量超过限制(30)"
                )
                return
            
            # 步骤2: 分析每个PNG文件
            self.logger.info(f"开始分析PNG文件")
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.ANALYZING,
                progress=40,
                message="开始分析PNG文件"
            )
            
            analyzer = GeminiAnalyzer()
            normalized_cos_path = cos_path.strip('/') if cos_path else ''
            # cos_result_prefix = f"{normalized_cos_path}/analysis" if normalized_cos_path else "analysis"
            cos_result_prefix = normalized_cos_path
            
            def analyze_progress(current, total, msg):
                progress = 40 + int(40 * current / total)
                self.task_manager.update_task(
                    task_id,
                    progress=progress,
                    message=f"分析进度: {current}/{total} - {msg}"
                )
            
            from gemini.anlysis_rule import prompt_score_rule
                
            json_files = analyzer.batch_analyze_images(
                png_files,
                prompt_score_rule,
                cache_dir,
                progress_callback=analyze_progress,
                cos_result_prefix=cos_result_prefix,
                force_reanalyze=task.force_reanalyze
            )
            
            if not json_files:
                raise ValueError("没有生成有效的JSON文件")
            
            self.logger.info(f"分析完成，共 {len(json_files)} 个JSON文件")
            
            # 步骤3: 合并JSON并进行二次分析
            self.logger.info(f"开始合并分析")
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.MERGING,
                progress=80,
                message="开始合并分析"
            )
            
            # 使用固定的分析提示词
            # from gemini.anlysis_rule import prompt_score_rule
            
            result_file = self.task_manager.get_cache_dir(cos_path) + f"/{task_id}.txt"
            result_text = analyzer.merge_and_analyze_json(
                json_files,
                prompt,
                result_file,
                cos_result_prefix=cos_result_prefix
            )
            
            self.logger.info(f"合并分析完成")
            
            # 任务完成
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="分析完成",
                result_file=result_file
            )
            
            self.logger.info(f"任务完成: {task_id}")
        
        except Exception as e:
            self.logger.error(f"任务失败 {task_id}: {e}", exc_info=True)
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                message="任务失败",
                error=str(e)
            )
    
    def start_task(self, task_id: str):
        """
        在后台线程中启动任务
        
        Args:
            task_id: 任务ID
        """
        thread = threading.Thread(target=self.process_task, args=(task_id,))
        thread.daemon = True
        thread.start()
