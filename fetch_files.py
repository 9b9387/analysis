import os
import logging
from typing import List, Optional, Dict
from datetime import datetime
import argparse
import sys
import json

from api_service.cos_downloader import COSDownloader

class COSFetcher:
	"""
	使用COSDownloader从COS列出/下载文件的工具。
	"""
	def __init__(self):
		self.logger = logging.getLogger(__name__)
		self.cd = COSDownloader()

	def list_directories(self, prefix: str) -> List[Dict]:
		"""
		返回指定前缀下的目录（非递归）。
		调用COSDownloader.list_directory并提取 directories 字段。
		"""
		info = self.cd.list_directory(prefix or '')
		return info.get('directories', [])

	def _normalize_prefix(self, prefix: str) -> str:
		if not prefix:
			return ''
		return prefix if prefix.endswith('/') else prefix + '/'

	def _normalize_exts(self, extensions: Optional[List[str]]) -> Optional[set]:
		if not extensions:
			return None
		return set(e.lower() if e.startswith('.') else f".{e.lower()}" for e in extensions)

	def list_files(self, prefix: str, extensions: Optional[List[str]] = None, recursive: bool = False) -> List[Dict]:
		"""
		列出指定前缀下的文件。非递归时使用 list_directory，递归时使用 list_objects。
		extensions: 列表或None（例如 ['.png','jpg']）。
		返回与之前类似的文件字典列表。
		"""
		prefix = self._normalize_prefix(prefix or '')
		exts = self._normalize_exts(extensions)

		files = []
		# 非递归：使用 list_directory 返回的 files 字段
		if not recursive:
			info = self.cd.list_directory(prefix)
			for f in info.get('files', []):
				if exts:
					_, e = os.path.splitext(f['name'])
					if e.lower() not in exts:
						continue
				files.append({
					'name': f['name'],
					'path': f['key'][len(prefix):].lstrip('/'),
					'size': f['size'],
					'size_human': f['size_human'],
					'last_modified': f['last_modified'],
					'type': 'file'
				})
			return files

		# 递归：使用 list_objects 遍历全部对象
		marker = ''
		client = self.cd.client
		bucket = self.cd.bucket
		while True:
			resp = client.list_objects(Bucket=bucket, Prefix=prefix, Marker=marker, MaxKeys=1000)
			if 'Contents' in resp:
				for obj in resp['Contents']:
					key = obj['Key']
					# 跳过目录占位
					if key.endswith('/') and obj.get('Size', 0) == 0:
						continue
					rel = key[len(prefix):].lstrip('/')
					if not rel:
						continue
					if exts:
						_, e = os.path.splitext(rel)
						if e.lower() not in exts:
							continue
					files.append({
						'name': rel,
						'path': rel,
						'size': obj.get('Size', 0),
						'size_human': self._format_size(obj.get('Size', 0)),
						'last_modified': obj.get('LastModified'),
						'type': 'file'
					})
			# 翻页处理
			if resp.get('IsTruncated') == 'true':
				marker = resp.get('NextMarker', '')
				if not marker and 'Contents' in resp:
					marker = resp['Contents'][-1]['Key']
			else:
				break
		return files

	def download_files_in_dir(self, src_prefix: str, dest_dir: str,
	                          extensions: Optional[List[str]] = None,
	                          recursive: bool = True,
	                          progress_callback=None) -> List[str]:
		"""
		将 COS 上 src_prefix 下的文件下载到本地 dest_dir（保留相对路径）。
		extensions: 过滤扩展名列表或 None。
		recursive: 是否递归查找。
		"""
		prefix = self._normalize_prefix(src_prefix or '')
		exts = self._normalize_exts(extensions)

		# 获取文件键列表（递归或非递归）
		if recursive:
			keys = [f"{prefix}{f['path']}" if prefix and not f['path'].startswith(prefix) else (prefix + f['path']).lstrip('/') for f in self.list_files(prefix, extensions=extensions, recursive=True)]
			# Above line assembles keys incorrectly if list_files already returns full-rels; rebuild keys properly below:
			keys = []
			marker = ''
			client = self.cd.client
			bucket = self.cd.bucket
			while True:
				resp = client.list_objects(Bucket=bucket, Prefix=prefix, Marker=marker, MaxKeys=1000)
				if 'Contents' in resp:
					for obj in resp['Contents']:
						key = obj['Key']
						# 跳过目录占位
						if key.endswith('/') and obj.get('Size', 0) == 0:
							continue
						rel = key[len(prefix):].lstrip('/')
						if not rel:
							continue
						if exts:
							_, e = os.path.splitext(rel)
							if e.lower() not in exts:
								continue
						keys.append(key)
				if resp.get('IsTruncated') == 'true':
					marker = resp.get('NextMarker', '')
					if not marker and 'Contents' in resp:
						marker = resp['Contents'][-1]['Key']
				else:
					break
		else:
			# 非递归：使用 list_directory
			info = self.cd.list_directory(prefix)
			keys = []
			for f in info.get('files', []):
				rel = f['name']
				if exts:
					_, e = os.path.splitext(rel)
					if e.lower() not in exts:
						continue
				keys.append(f['key'])

		if not keys:
			self.logger.warning(f"在 '{src_prefix}' 下未找到匹配的文件")
			return []

		os.makedirs(dest_dir, exist_ok=True)
		downloaded = []
		total = len(keys)

		for i, key in enumerate(keys, start=1):
			relative_path = key[len(prefix):].lstrip('/') if prefix else key.lstrip('/')
			local_path = os.path.join(dest_dir, *relative_path.split('/'))

			# Ensure parent exists
			os.makedirs(os.path.dirname(local_path), exist_ok=True)

			if os.path.exists(local_path):
				self.logger.info(f"文件已存在，跳过: {local_path}")
				downloaded.append(local_path)
				if progress_callback:
					progress_callback(i, total, f"跳过已存在的文件: {relative_path}")
				continue

			if progress_callback:
				progress_callback(i, total, f"下载中: {relative_path}")

			if self.cd.download_file(key, local_path):
				downloaded.append(local_path)
			else:
				self.logger.error(f"下载失败: {key}")

		self.logger.info(f"下载完成，成功 {len(downloaded)}/{total} 个文件")
		return downloaded

	def _format_size(self, size_bytes: int) -> str:
		if size_bytes == 0:
			return "0B"
		units = ['B', 'KB', 'MB', 'GB', 'TB']
		i = 0
		s = float(size_bytes)
		while s >= 1024.0 and i < len(units) - 1:
			s /= 1024.0
			i += 1
		return f"{s:.1f}{units[i]}"


def _print_progress(current, total, message):
	print(f"[{current}/{total}] {message}")

def main():
	parser = argparse.ArgumentParser(description="Fetch files from COS")
	sub = parser.add_subparsers(dest="cmd", required=True)

	# list-dirs (COS)
	p_list_dirs = sub.add_parser("list-dirs", help="列出指定COS前缀下的目录（非递归）")
	p_list_dirs.add_argument("prefix", nargs='?', default='', help="COS前缀（可为空字符串表示根）")

	# list-files
	p_list_files = sub.add_parser("list-files", help="列出COS前缀下的文件")
	p_list_files.add_argument("prefix", nargs='?', default='', help="COS前缀（可为空）")
	p_list_files.add_argument("--ext", "-e", nargs="*", help="扩展名过滤，例如 .png .jpg 或 png jpg")
	p_list_files.add_argument("--recursive", "-r", action="store_true", help="递归子前缀")

	# download
	p_download = sub.add_parser("download", help="从COS下载指定前缀下的文件到本地目录")
	p_download.add_argument("prefix", nargs='?', default='', help="COS前缀")
	p_download.add_argument("local_dir", help="本地目标目录")
	p_download.add_argument("--ext", "-e", nargs="*", help="扩展名过滤，例如 .png .jpg 或 png jpg")
	p_download.add_argument("--no-recursive", action="store_true", help="仅当前前缀，不递归")
	p_download.add_argument("--show-progress", action="store_true", help="显示进度")

	args = parser.parse_args()
	fetcher = COSFetcher()

	try:
		if args.cmd == "list-dirs":
			res = fetcher.list_directories(args.prefix)
			print(json.dumps(res, default=str, ensure_ascii=False, indent=2))

		elif args.cmd == "list-files":
			exts = args.ext if args.ext else None
			files = fetcher.list_files(args.prefix, extensions=exts, recursive=args.recursive)
			print(json.dumps(files, default=str, ensure_ascii=False, indent=2))

		elif args.cmd == "download":
			exts = args.ext if args.ext else None
			recursive = not args.no_recursive
			progress_cb = _print_progress if args.show_progress else None
			res = fetcher.download_files_in_dir(args.prefix, args.local_dir, extensions=exts, recursive=recursive, progress_callback=progress_cb)
			print(json.dumps({"downloaded": res}, default=str, ensure_ascii=False, indent=2))

	except Exception as e:
		print(f"错误: {e}", file=sys.stderr)
		sys.exit(1)

if __name__ == "__main__":
	main()
