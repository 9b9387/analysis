"""
配置文件 - 管理API服务的配置信息
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Gemini API 配置
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_PROXY_URL = os.getenv('GEMINI_PROXY_URL', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'models/gemini-2.5-pro')
GEMINI_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT', '600000'))

# 豆包模型配置
DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '')
DOUBAO_MODEL = os.getenv('DOUBAO_MODEL', 'doubao-seed-1-6-251015')
DOUBAO_BASE_URL = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
DOUBAO_REASONING = os.getenv('DOUBAO_REASONING', 'medium')
DOUBAO_TEMPERATURE = float(os.getenv('DOUBAO_TEMPERATURE', '0'))

# 腾讯云 COS 配置
COS_SECRET_ID = os.getenv('COS_SECRET_ID') or os.getenv('SECRET_ID')
COS_SECRET_KEY = os.getenv('COS_SECRET_KEY') or os.getenv('SECRET_KEY')
COS_REGION = os.getenv('COS_REGION') or os.getenv('REGION', 'ap-guangzhou')
COS_BUCKET = os.getenv('COS_BUCKET') or os.getenv('BUCKET')
COS_TOKEN = os.getenv('TOKEN')

# 缓存目录配置
CACHE_ROOT_DIR = os.getenv('CACHE_ROOT_DIR', './cache')

# 任务存储配置
TASK_STORAGE_FILE = os.getenv('TASK_STORAGE_FILE', './tasks.json')

# Flask 配置
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '15000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# 麻将分析系统指令
MAHJONG_ANALYSIS_SYSTEM_INSTRUCTION = '你是一位麻将高手和麻将游戏分析专家，擅长游戏记分和分析。'
