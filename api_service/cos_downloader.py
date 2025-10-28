"""
COS下载器 - 从腾讯云COS下载PNG文件
"""
import os
import logging
from typing import List
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError, CosClientError

from . import config


class COSDownloader:
    """腾讯云COS文件下载器"""
    
    def __init__(self):
        """初始化COS客户端"""
        # 检查是否为公开访问模式
        self.is_public = not all([config.COS_SECRET_ID, config.COS_SECRET_KEY])
        
        if self.is_public:
            # 公开访问模式
            if not all([config.COS_REGION, config.COS_BUCKET]):
                raise ValueError("公开访问模式下，需要配置COS_REGION和COS_BUCKET参数")
            
            cos_config = CosConfig(
                Region=config.COS_REGION,
                SecretId='',
                SecretKey='',
                Token=config.COS_TOKEN,
                Scheme='https',
                Anonymous=True
            )
        else:
            # 认证访问模式
            if not all([config.COS_SECRET_ID, config.COS_SECRET_KEY, 
                       config.COS_REGION, config.COS_BUCKET]):
                raise ValueError("缺少必要的COS配置参数")
            
            cos_config = CosConfig(
                Region=config.COS_REGION,
                SecretId=config.COS_SECRET_ID,
                SecretKey=config.COS_SECRET_KEY,
                Token=config.COS_TOKEN,
                Scheme='https'
            )
        
        self.client = CosS3Client(cos_config)
        self.bucket = config.COS_BUCKET
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def list_png_files(self, prefix: str) -> List[str]:
        """
        列出指定前缀下的所有PNG文件
        
        Args:
            prefix: COS路径前缀
            
        Returns:
            PNG文件key列表
        """
        try:
            self.logger.info(f"正在获取PNG文件列表 - 前缀: '{prefix}'")
            
            png_files = []
            marker = ''
            
            # 确保prefix以/结尾
            if prefix and not prefix.endswith('/'):
                prefix = prefix + '/'
            
            while True:
                response = self.client.list_objects(
                    Bucket=self.bucket,
                    Prefix=prefix,
                    Marker=marker,
                    MaxKeys=1000
                )
                
                # 处理文件对象
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        # 只保留PNG文件
                        if key.lower().endswith('.png'):
                            png_files.append(key)
                
                # 检查是否还有更多对象
                if response.get('IsTruncated') == 'true':
                    marker = response.get('NextMarker', '')
                    if not marker and 'Contents' in response:
                        marker = response['Contents'][-1]['Key']
                else:
                    break
            
            self.logger.info(f"找到 {len(png_files)} 个PNG文件")
            return png_files
            
        except CosServiceError as e:
            self.logger.error(f"COS服务错误: {e.get_error_code()} - {e.get_error_msg()}")
            raise
        except CosClientError as e:
            self.logger.error(f"COS客户端错误: {e}")
            raise
    
    def download_file(self, key: str, local_path: str) -> bool:
        """
        下载单个文件
        
        Args:
            key: COS对象key
            local_path: 本地保存路径
            
        Returns:
            下载是否成功
        """
        try:
            # 创建目录
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 下载文件
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key
            )
            
            body = response['Body']
            with open(local_path, 'wb') as f:
                while True:
                    chunk = body.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            
            self.logger.info(f"下载完成: {key} -> {local_path}")
            return True
            
        except CosServiceError as e:
            self.logger.error(f"下载失败: {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            self.logger.error(f"下载时发生错误: {e}")
            return False
    
    def download_png_files(self, prefix: str, local_dir: str, 
                          progress_callback=None) -> List[str]:
        """
        下载指定前缀下的所有PNG文件
        
        Args:
            prefix: COS路径前缀
            local_dir: 本地保存目录
            progress_callback: 进度回调函数 callback(current, total, message)
            
        Returns:
            下载成功的本地文件路径列表
        """
        # 获取PNG文件列表
        png_keys = self.list_png_files(prefix)
        
        if not png_keys:
            self.logger.warning(f"在 '{prefix}' 下未找到PNG文件")
            return []
        
        # 创建本地目录
        os.makedirs(local_dir, exist_ok=True)
        
        downloaded_files = []
        total = len(png_keys)
        
        for i, key in enumerate(png_keys, 1):
            # 构建本地文件路径，保持COS的目录结构
            relative_path = key[len(prefix):].lstrip('/')
            local_path = os.path.join(local_dir, relative_path)
            
            # 检查文件是否已存在
            if os.path.exists(local_path):
                self.logger.info(f"文件已存在，跳过: {local_path}")
                downloaded_files.append(local_path)
                if progress_callback:
                    progress_callback(i, total, f"跳过已存在的文件: {os.path.basename(key)}")
                continue
            
            # 下载文件
            if progress_callback:
                progress_callback(i, total, f"下载中: {os.path.basename(key)}")
            
            if self.download_file(key, local_path):
                downloaded_files.append(local_path)
            else:
                self.logger.error(f"下载失败: {key}")
        
        self.logger.info(f"下载完成，成功 {len(downloaded_files)}/{total} 个文件")
        return downloaded_files
    
    def list_directory(self, prefix: str) -> dict:
        """
        列出指定路径下的文件和文件夹
        
        Args:
            prefix: COS路径前缀
            
        Returns:
            包含files和directories的字典
        """
        try:
            self.logger.info(f"列出目录内容 - 路径: '{prefix}'")
            
            # 确保prefix以/结尾（除非是根目录）
            if prefix and not prefix.endswith('/'):
                prefix = prefix + '/'
            
            files = []
            directories = []
            marker = ''
            
            while True:
                response = self.client.list_objects(
                    Bucket=self.bucket,
                    Prefix=prefix,
                    Delimiter='/',  # 使用分隔符来区分文件和目录
                    Marker=marker,
                    MaxKeys=1000
                )
                
                # 处理文件对象
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        # 跳过目录本身（以/结尾且大小为0）
                        if key == prefix:
                            continue
                        if key.endswith('/') and obj['Size'] == 0:
                            continue
                        
                        # 提取文件名（去掉前缀路径）
                        file_name = key[len(prefix):]
                        if file_name:  # 确保不是空字符串
                            files.append({
                                'name': file_name,
                                'key': key,
                                'size': obj['Size'],
                                'size_human': self._format_size(obj['Size']),
                                'last_modified': obj['LastModified'],
                                'type': 'file'
                            })
                
                # 处理子目录
                if 'CommonPrefixes' in response:
                    for prefix_info in response['CommonPrefixes']:
                        dir_key = prefix_info['Prefix']
                        # 提取目录名
                        dir_name = dir_key[len(prefix):].rstrip('/')
                        if dir_name:
                            directories.append({
                                'name': dir_name,
                                'key': dir_key,
                                'type': 'directory'
                            })
                
                # 检查是否还有更多对象
                if response.get('IsTruncated') == 'true':
                    marker = response.get('NextMarker', '')
                    if not marker and 'Contents' in response:
                        marker = response['Contents'][-1]['Key']
                else:
                    break
            
            result = {
                'path': prefix.rstrip('/') if prefix else '/',
                'files': files,
                'directories': directories,
                'total_files': len(files),
                'total_directories': len(directories)
            }
            
            self.logger.info(f"找到 {len(directories)} 个目录和 {len(files)} 个文件")
            return result
            
        except CosServiceError as e:
            self.logger.error(f"COS服务错误: {e.get_error_code()} - {e.get_error_msg()}")
            raise
        except CosClientError as e:
            self.logger.error(f"COS客户端错误: {e}")
            raise
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f}{units[unit_index]}"
