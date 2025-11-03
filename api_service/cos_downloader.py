"""
COS下载器 - 从腾讯云COS下载PNG文件
"""
import json
import mimetypes
import os
import logging
from typing import Any, List, Optional
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
    
    def upload_file(self, local_path: str, key: str, *, content_type: Optional[str] = None) -> bool:
        """上传本地文件到COS"""
        if self.is_public:
            raise PermissionError("当前为匿名访问模式，无法上传文件")

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"文件不存在: {local_path}")

        norm_key = key.lstrip('/')
        guessed_type = content_type or mimetypes.guess_type(local_path)[0] or 'application/octet-stream'

        try:
            self.logger.info(f"上传文件到COS: {local_path} -> {norm_key}")
            with open(local_path, 'rb') as fp:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=norm_key,
                    Body=fp.read(),
                    ContentType=guessed_type
                )
            return True
        except CosServiceError as e:
            self.logger.error(f"上传失败: {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            self.logger.error(f"上传时发生错误: {e}")
            return False

    def upload_text(self, content: str, key: str, *, encoding: str = 'utf-8', content_type: str = 'text/plain; charset=utf-8') -> bool:
        """将文本内容上传到COS"""
        if self.is_public:
            raise PermissionError("当前为匿名访问模式，无法上传文本")

        norm_key = key.lstrip('/')

        try:
            self.logger.info(f"上传文本到COS: {norm_key}")
            self.client.put_object(
                Bucket=self.bucket,
                Key=norm_key,
                Body=content.encode(encoding),
                ContentType=content_type
            )
            return True
        except CosServiceError as e:
            self.logger.error(f"文本上传失败: {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            self.logger.error(f"文本上传时发生错误: {e}")
            return False

    def upload_json(self, data: Any, key: str, *, ensure_ascii: bool = False,
                    indent: int = 2, encoding: str = 'utf-8') -> bool:
        """将JSON数据上传到COS"""
        if self.is_public:
            raise PermissionError("当前为匿名访问模式，无法上传JSON数据")

        norm_key = key.lstrip('/')

        try:
            payload = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
            self.logger.info(f"上传JSON到COS: {norm_key}")
            self.client.put_object(
                Bucket=self.bucket,
                Key=norm_key,
                Body=payload.encode(encoding),
                ContentType=f'application/json; charset={encoding}'
            )
            return True
        except CosServiceError as e:
            self.logger.error(f"JSON上传失败: {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            self.logger.error(f"JSON上传时发生错误: {e}")
            return False

    def list_png_files(self, prefix: str) -> List[str]:
        """
        列出指定前缀下的所有PNG文件（兼容旧接口）
        
        Args:
            prefix: COS路径前缀
            
        Returns:
            PNG文件key列表
        """
        return self.list_target_files(prefix, extensions=['.png'])
    
    def list_target_files(self, prefix: str, extensions: List[str] = None) -> List[str]:
        """
        列出指定前缀下的目标文件
        
        Args:
            prefix: COS路径前缀
            extensions: 文件扩展名列表，例如 ['.png', '.json']，None表示所有文件
            
        Returns:
            目标文件key列表
        """
        if extensions is None:
            extensions = ['.png', '.json']
        
        extensions = [ext.lower() for ext in extensions]
        
        try:
            self.logger.info(f"正在获取文件列表 - 前缀: '{prefix}', 扩展名: {extensions}")
            
            target_files = []
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
                        # 检查文件扩展名
                        if any(key.lower().endswith(ext) for ext in extensions):
                            target_files.append(key)
                
                # 检查是否还有更多对象
                if response.get('IsTruncated') == 'true':
                    marker = response.get('NextMarker', '')
                    if not marker and 'Contents' in response:
                        marker = response['Contents'][-1]['Key']
                else:
                    break
            
            self.logger.info(f"找到 {len(target_files)} 个目标文件")
            return target_files
            
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
        下载指定前缀下的所有PNG文件（兼容旧接口）
        
        Args:
            prefix: COS路径前缀
            local_dir: 本地保存目录
            progress_callback: 进度回调函数 callback(current, total, message)
            
        Returns:
            下载成功的本地文件路径列表
        """
        return self.download_files(prefix, local_dir, extensions=['.png'], 
                                   progress_callback=progress_callback)
    
    def download_files(self, prefix: str, local_dir: str, 
                      extensions: List[str] = None,
                      progress_callback=None) -> dict:
        """
        下载指定前缀下的目标文件
        
        Args:
            prefix: COS路径前缀
            local_dir: 本地保存目录
            extensions: 文件扩展名列表，例如 ['.png', '.json']，None表示下载PNG和JSON
            progress_callback: 进度回调函数 callback(current, total, message)
            
        Returns:
            包含不同类型文件路径列表的字典，例如：
            {
                'png': ['/path/to/file1.png', ...],
                'json': ['/path/to/file1.json', ...],
                'all': ['/path/to/file1.png', '/path/to/file1.json', ...]
            }
        """
        if extensions is None:
            extensions = ['.png', '.json']
        
        # 获取目标文件列表
        target_keys = self.list_target_files(prefix, extensions)
        
        if not target_keys:
            self.logger.warning(f"在 '{prefix}' 下未找到目标文件")
            return {'png': [], 'json': [], 'all': []}
        
        # 创建本地目录
        os.makedirs(local_dir, exist_ok=True)
        
        downloaded_files = {'png': [], 'json': [], 'all': []}
        total = len(target_keys)
        
        for i, key in enumerate(target_keys, 1):
            # 构建本地文件路径，保持COS的目录结构
            relative_path = key[len(prefix):].lstrip('/')
            local_path = os.path.join(local_dir, relative_path)
            
            # 检查文件是否已存在
            if os.path.exists(local_path):
                self.logger.info(f"文件已存在，跳过: {local_path}")
                downloaded_files['all'].append(local_path)
                
                # 根据扩展名分类
                if local_path.lower().endswith('.png'):
                    downloaded_files['png'].append(local_path)
                elif local_path.lower().endswith('.json'):
                    downloaded_files['json'].append(local_path)
                
                if progress_callback:
                    progress_callback(i, total, f"跳过已存在的文件: {os.path.basename(key)}")
                continue
            
            # 下载文件
            if progress_callback:
                progress_callback(i, total, f"下载中: {os.path.basename(key)}")
            
            if self.download_file(key, local_path):
                downloaded_files['all'].append(local_path)
                
                # 根据扩展名分类
                if local_path.lower().endswith('.png'):
                    downloaded_files['png'].append(local_path)
                elif local_path.lower().endswith('.json'):
                    downloaded_files['json'].append(local_path)
            else:
                self.logger.error(f"下载失败: {key}")
        
        self.logger.info(f"下载完成，成功 {len(downloaded_files['all'])}/{total} 个文件 "
                        f"(PNG: {len(downloaded_files['png'])}, JSON: {len(downloaded_files['json'])})")
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
