"""
Gemini分析器 - 使用Gemini AI进行麻将游戏分析
"""
import os
import json
import time
import logging
import sys
from typing import List, Optional
from google import genai
from google.genai import types

from api_service.google_client_files import Files

from . import config


class GeminiAnalyzer:
    """Gemini AI分析器"""
    
    def __init__(self):
        """初始化Gemini客户端"""
        http_options = types.HttpOptions(
            base_url=config.GEMINI_PROXY_URL,
            timeout=config.GEMINI_TIMEOUT
        )
        self.client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=http_options

        )
        self.client._files = Files(self.client._api_client)
        self.model = config.GEMINI_MODEL
        self.logger = logging.getLogger(__name__)
    
    def upload_file(self, file_path: str) -> str:
        """
        上传文件到Gemini
        
        Args:
            file_path: 文件路径
            
        Returns:
            上传后的文件名
        """
        self.logger.info(f"上传文件: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        uploaded_file = self.client.files.upload(file=file_path)
        
        # 等待文件处理完成
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = self.client.files.get(name=uploaded_file.name)
        
        if uploaded_file.state.name == "FAILED":
            raise ValueError(f"文件处理失败: {uploaded_file.state.name}")
        
        self.logger.info(f"文件上传成功: {uploaded_file.name}")
        return uploaded_file.name
    
    def analyze_image(self, image_path: str, prompt: str) -> dict:
        """
        分析单张图片
        
        Args:
            image_path: 图片路径
            prompt: 分析提示词
            
        Returns:
            分析结果的JSON数据
        """
        self.logger.info(f"分析图片: {image_path}")
        
        # 上传图片
        file_name = self.upload_file(image_path)
        file_obj = self.client.files.get(name=file_name)
        
        # 导入数据模型
        from gemini.anlysis_data import AnalysisData
        
        # 调用Gemini分析
        response = self.client.models.generate_content(
            model=self.model,
            contents=[file_obj, prompt],
            config={
                'system_instruction': config.MAHJONG_ANALYSIS_SYSTEM_INSTRUCTION,
                'response_mime_type': 'application/json',
                'response_schema': AnalysisData,
                'http_options': types.HttpOptions(timeout=config.GEMINI_TIMEOUT)
            }
        )
        
        # 解析响应
        result_data = json.loads(response.text)
        self.logger.info(f"图片分析完成: {image_path}")
        
        return result_data
    
    def batch_analyze_images(self, image_paths: List[str], prompt: str,
                            output_dir: str, progress_callback=None) -> List[str]:
        """
        批量分析图片
        
        Args:
            image_paths: 图片路径列表
            prompt: 分析提示词
            output_dir: JSON输出目录
            progress_callback: 进度回调函数 callback(current, total, message)
            
        Returns:
            生成的JSON文件路径列表
        """
        os.makedirs(output_dir, exist_ok=True)
        
        json_files = []
        total = len(image_paths)
        
        for i, image_path in enumerate(image_paths, 1):
            try:
                if progress_callback:
                    progress_callback(i, total, f"分析中: {os.path.basename(image_path)}")
                
                # 检查是否已有对应的JSON文件
                json_filename = os.path.splitext(os.path.basename(image_path))[0] + '.json'
                json_path = os.path.join(output_dir, json_filename)
                
                if os.path.exists(json_path):
                    self.logger.info(f"JSON文件已存在，跳过: {json_path}")
                    json_files.append(json_path)
                    continue
                
                # 分析图片
                result = self.analyze_image(image_path, prompt)
                
                # 保存JSON结果
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                json_files.append(json_path)
                self.logger.info(f"分析结果已保存: {json_path}")
                
            except Exception as e:
                self.logger.error(f"分析失败 {image_path}: {e}")
                if progress_callback:
                    progress_callback(i, total, f"分析失败: {os.path.basename(image_path)}")
        
        self.logger.info(f"批量分析完成，成功 {len(json_files)}/{total} 个")
        return json_files
    
    def merge_and_analyze_json(self, json_files: List[str], prompt: str,
                              output_file: str) -> str:
        """
        合并JSON数据并进行二次分析
        
        Args:
            json_files: JSON文件路径列表
            prompt: 分析提示词
            output_file: 输出文件路径
            
        Returns:
            分析结果文本
        """
        self.logger.info(f"合并 {len(json_files)} 个JSON文件")
        
        # 合并所有JSON数据
        merged_data = []
        for json_path in json_files:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    merged_data.append(data)
            except Exception as e:
                self.logger.error(f"读取JSON失败 {json_path}: {e}")
        
        if not merged_data:
            raise ValueError("没有有效的JSON数据可供分析")
        
        # 保存合并数据到JSON文件（保留，不删除）
        merged_json_file = output_file
        with open(merged_json_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=0)
        
        self.logger.info(f"数据已合并并保存到: {merged_json_file}")
        self.logger.info(f"开始二次分析")
        
        # 上传合并的JSON文件
        file_name = self.upload_file(merged_json_file)
        file_obj = self.client.files.get(name=file_name)
        
        # 流式分析
        chunks = []
        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=[file_obj, prompt],
                config={
                    'system_instruction': config.MAHJONG_ANALYSIS_SYSTEM_INSTRUCTION,
                    'response_mime_type': 'text/plain',
                    'http_options': types.HttpOptions(timeout=config.GEMINI_TIMEOUT)
                }
            )
            
            for chunk in response_stream:
                text = getattr(chunk, "text", str(chunk))
                chunks.append(text)
                self.logger.debug(text)
        
        except Exception as e:
            # 流式失败，尝试非流式
            self.logger.warning(f"流式请求失败，尝试非流式: {e}")
            response = self.client.models.generate_content(
                model=self.model,
                contents=[file_obj, prompt],
                config={
                    'system_instruction': config.MAHJONG_ANALYSIS_SYSTEM_INSTRUCTION,
                    'response_mime_type': 'text/plain',
                    'http_options': types.HttpOptions(timeout=config.GEMINI_TIMEOUT)
                }
            )
            text = getattr(response, "text", str(response))
            chunks.append(text)
        
        final_output = "".join(chunks)
        
        # 保存最终分析结果（保留，不删除）
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_output)
        
        self.logger.info(f"分析结果已保存: {output_file}")
        self.logger.info(f"合并数据已保存: {merged_json_file}")
        
        return final_output
