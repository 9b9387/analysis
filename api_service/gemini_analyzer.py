"""
Gemini分析器 - 使用Gemini AI进行麻将游戏分析
"""
import base64
import os
import json
import time
import logging
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from google import genai
from google.genai import types
from google.genai.types import HttpOptions

from pydantic import ValidationError

from api_service.google_client_files import Files
from gemini.score_data import ScoreData

from . import config
from .cos_downloader import COSDownloader

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - 控制在运行时降级
    OpenAI = None


ANALYSIS_JSON_SCHEMA = ScoreData.model_json_schema()
ANALYSIS_SCHEMA_JSON = json.dumps(ANALYSIS_JSON_SCHEMA, ensure_ascii=False)
ANALYSIS_SCHEMA_HINT = (
    "请严格输出一个符合以下JSON Schema的JSON对象，禁止添加解释或额外文本:\n"
    f"{ANALYSIS_SCHEMA_JSON}"
)
ANALYSIS_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": ScoreData.__name__,
        "schema": ANALYSIS_JSON_SCHEMA,
        "strict_schema": True
    }
}


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
        self.cos_uploader: Optional[COSDownloader] = None

        self.doubao_client = None
        self.doubao_model = config.DOUBAO_MODEL
        self.doubao_reasoning = config.DOUBAO_REASONING or 'medium'
        self.doubao_temperature = config.DOUBAO_TEMPERATURE

        if OpenAI and config.DOUBAO_API_KEY:
            try:
                self.doubao_client = OpenAI(
                    base_url=config.DOUBAO_BASE_URL,
                    api_key=config.DOUBAO_API_KEY
                )
                self.logger.info(
                    "Doubao client initialized with model: %s", self.doubao_model
                )
            except Exception as exc:  # pragma: no cover - 记录初始化失败
                self.logger.warning(f"初始化豆包客户端失败: {exc}")
                self.doubao_client = None
        elif not OpenAI:
            self.logger.warning("未安装openai库，豆包模型调用被禁用")
        else:
            self.logger.info("未配置DOUBAO_API_KEY，豆包模型调用被跳过")

        self.logger.info(f"GeminiAnalyzer initialized with model: {self.model}")
        self.logger.info(f"Using Gemini Proxy URL: {config.GEMINI_PROXY_URL}")
        
    
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

        gemini_result = self._analyze_with_gemini(image_path, prompt)

        # 关闭豆包辅助分析功能
        # doubao_result = None

        # if self.doubao_client:
        #     try:
        #         doubao_result = self._analyze_with_doubao(image_path, prompt)
        #     except Exception as exc:  # pragma: no cover - 确保主流程不中断
        #         self.logger.warning(f"豆包模型分析失败，忽略该结果: {exc}")

        # merged_result, meta = self._merge_analysis_results(gemini_result, doubao_result)

        # if meta:
        #     merged_result['cross_model_notes'] = meta

        self.logger.info(f"图片分析完成: {image_path}")
        return gemini_result
    
    def _analyze_with_gemini(self, image_path: str, prompt: str) -> Dict[str, Any]:
        file_name = self.upload_file(image_path)
        file_obj = self.client.files.get(name=file_name)

        response = self.client.models.generate_content(
            model=self.model,
            contents=[file_obj, prompt],
            config={
                'system_instruction': config.MAHJONG_ANALYSIS_SYSTEM_INSTRUCTION,
                'response_mime_type': 'application/json',
                'response_schema': ScoreData,
                'http_options': types.HttpOptions(timeout=config.GEMINI_TIMEOUT)
            }
        )
        raw_text = getattr(response, "text", "")
        return self._parse_analysis_json(raw_text)

    def _analyze_with_doubao(self, image_path: str, prompt: str) -> Dict[str, Any]:
        if not self.doubao_client:
            raise RuntimeError("豆包客户端未初始化")

        self.logger.info(f"使用豆包模型进行辅助分析: {image_path}")
        image_base64 = self._encode_image_to_base64(image_path)
        enhanced_prompt = (
            f"{prompt.strip()}\n\n{ANALYSIS_SCHEMA_HINT}"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    },
                    {"type": "text", "text": enhanced_prompt}
                ],
            }
        ]

        response_format = deepcopy(ANALYSIS_RESPONSE_FORMAT)
        completion = self.doubao_client.chat.completions.create(
            model=self.doubao_model,
            messages=messages,
            temperature=self.doubao_temperature,
            reasoning_effort=self.doubao_reasoning,
            response_format=response_format
        )

        content = completion.choices[0].message.content
        if isinstance(content, list):
            content = "".join(
                part.get('text', '') if isinstance(part, dict) else str(part)
                for part in content
            )

        raw_content = str(content)
        doubao_data = self._parse_analysis_json(raw_content)
        self.logger.info("豆包模型返回结果已解析")
        return doubao_data

    def _safe_parse_json(self, raw: str) -> Dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start:end + 1])
            raise

    def _parse_analysis_json(self, raw: str) -> Dict[str, Any]:
        try:
            return ScoreData.model_validate_json(raw).model_dump()
        except ValidationError as exc:
            self.logger.debug("结构化JSON解析失败，尝试修正: %s", exc)
            parsed = self._safe_parse_json(raw)
            return self._validate_analysis_dict(parsed)

    def _validate_analysis_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return ScoreData.model_validate(data).model_dump()
        except ValidationError as exc:  # pragma: no cover - 调试信息
            self.logger.error("分析结果不符合Schema: %s", exc)
            raise

    def _merge_analysis_results(
        self,
        gemini_data: Dict[str, Any],
        doubao_data: Optional[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        基于新版 ScoreData 结构对两个模型的结果进行合并与交叉验证。
        数据部分默认使用gemini结果，仅在meta中记录与doubao的差异。
        """

        # 元信息统计
        differences: List[Dict[str, Any]] = []
        agreement_count = 0
        total_checks = 0

        # 单模型可用时，直接返回
        if not isinstance(doubao_data, dict) or not doubao_data:
            meta = {
                'strategy': '单模型结果',
                'model': self.model,
                'notes': ['豆包模型不可用或调用失败'],
                'differences': []
            }
            return deepcopy(gemini_data), meta

        # 数据部分使用gemini结果
        result_data = deepcopy(gemini_data)

        def _list_to_map_by_name(players: Any) -> Dict[str, Dict[str, Any]]:
            result: Dict[str, Dict[str, Any]] = {}
            if isinstance(players, list):
                for p in players:
                    if isinstance(p, dict):
                        name = p.get('玩家名字')
                        if isinstance(name, str) and name:
                            result[name] = p
            return result

        gem_players = _list_to_map_by_name(gemini_data.get('玩家分数数据')) if isinstance(gemini_data, dict) else {}
        dou_players = _list_to_map_by_name(doubao_data.get('玩家分数数据')) if isinstance(doubao_data, dict) else {}

        # 获取所有玩家名字
        all_names = set(gem_players.keys()) | set(dou_players.keys())

        # 检查每个玩家的数据差异
        for name in all_names:
            gp = gem_players.get(name)
            dp = dou_players.get(name)

            if gp is None:
                differences.append({
                    'field': f'玩家[{name}]',
                    'note': '仅豆包识别到此玩家',
                    'doubao_value': dp
                })
                continue
            
            if dp is None:
                differences.append({
                    'field': f'玩家[{name}]',
                    'note': '仅Gemini识别到此玩家'
                })
                continue

            # 比较番数列表
            g_list = gp.get('番数列表', [])
            d_list = dp.get('番数列表', [])
            if isinstance(g_list, list) and isinstance(d_list, list):
                total_checks += 1
                g_map = {item.get('名称'): item.get('番数') for item in g_list if isinstance(item, dict)}
                d_map = {item.get('名称'): item.get('番数') for item in d_list if isinstance(item, dict)}
                
                if g_map != d_map:
                    differences.append({
                        'field': f'玩家[{name}].番数列表',
                        'gemini_value': g_list,
                        'doubao_value': d_list
                    })
                else:
                    agreement_count += 1

            # 比较胡牌信息
            g_win = gp.get('胡牌信息')
            d_win = dp.get('胡牌信息')
            if g_win is not None and d_win is not None:
                total_checks += 1
                if g_win != d_win:
                    differences.append({
                        'field': f'玩家[{name}].胡牌信息',
                        'gemini_value': g_win,
                        'doubao_value': d_win
                    })
                else:
                    agreement_count += 1

            # 比较标量字段
            for field in ['总番数', '庄家', '连庄数', '底分', '分数变化']:
                gv = gp.get(field)
                dv = dp.get(field)
                if gv is not None and dv is not None:
                    total_checks += 1
                    if gv != dv:
                        differences.append({
                            'field': f'玩家[{name}].{field}',
                            'gemini_value': gv,
                            'doubao_value': dv
                        })
                    else:
                        agreement_count += 1

        # 全局一致性检查：分数变化总和应为0
        try:
            gem_deltas = [p.get('分数变化') for p in gemini_data.get('玩家分数数据', []) if isinstance(p.get('分数变化'), int)]
            dou_deltas = [p.get('分数变化') for p in doubao_data.get('玩家分数数据', []) if isinstance(p.get('分数变化'), int)]
            
            if len(gem_deltas) == len(gemini_data.get('玩家分数数据', [])):
                total_checks += 1
                gem_sum = sum(gem_deltas)
                if gem_sum == 0:
                    agreement_count += 1
                else:
                    differences.append({
                        'field': '全局校验.分数变化总和',
                        'gemini_value': gem_sum,
                        'expected': 0,
                        'note': '分数变化总和应为0'
                    })
            
            if len(dou_deltas) == len(doubao_data.get('玩家分数数据', [])):
                dou_sum = sum(dou_deltas)
                if dou_sum != 0:
                    differences.append({
                        'field': '豆包全局校验.分数变化总和',
                        'doubao_value': dou_sum,
                        'expected': 0,
                        'note': '豆包的分数变化总和应为0'
                    })
        except Exception:  # pragma: no cover
            pass

        confidence = (agreement_count / total_checks) if total_checks else 1.0
        meta = {
            'strategy': '双模型交叉验证',
            'primary_model': self.model,
            'validation_model': self.doubao_model,
            'agreement_count': agreement_count,
            'total_checks': total_checks,
            'confidence': round(confidence, 3),
            'differences': differences if differences else []
        }

        return result_data, meta

    def _encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, 'rb') as fp:
            return base64.b64encode(fp.read()).decode('utf-8')

    def _get_or_create_cos_uploader(self) -> Optional[COSDownloader]:
        if self.cos_uploader is not None:
            return self.cos_uploader

        try:
            self.cos_uploader = COSDownloader()
        except Exception as exc:  # pragma: no cover - 运行时初始化失败
            self.logger.warning(f"初始化COS上传器失败: {exc}")
            self.cos_uploader = None

        return self.cos_uploader

    def _upload_to_cos(self, local_path: str, remote_key: Optional[str]) -> None:
        if not remote_key:
            return

        uploader = self._get_or_create_cos_uploader()
        if not uploader:
            self.logger.warning("未能获取COS上传器，跳过上传: %s", local_path)
            return

        try:
            success = uploader.upload_file(local_path, remote_key)
            if success:
                self.logger.info(f"结果已上传至COS: {remote_key}")
            else:
                self.logger.error(f"上传到COS失败: {remote_key}")
        except PermissionError as exc:
            self.logger.warning(f"COS匿名模式无法上传: {exc}")
        except Exception as exc:  # pragma: no cover - 上传异常
            self.logger.error(f"上传COS时发生异常: {exc}")

    def _upload_analysis_json(self, data: Dict[str, Any], remote_key: Optional[str]) -> None:
        if not remote_key:
            return

        uploader = self._get_or_create_cos_uploader()
        if not uploader:
            self.logger.warning("未能获取COS上传器，跳过JSON上传")
            return

        try:
            success = uploader.upload_json(data, remote_key, ensure_ascii=False, indent=2)
            if success:
                self.logger.info(f"JSON结果已上传至COS: {remote_key}")
            else:
                self.logger.error(f"JSON上传至COS失败: {remote_key}")
        except PermissionError as exc:
            self.logger.warning(f"COS匿名模式无法上传JSON: {exc}")
        except Exception as exc:  # pragma: no cover - 上传异常
            self.logger.error(f"上传JSON至COS时发生异常: {exc}")

    def _build_remote_key(self, prefix: Optional[str], filename: str) -> Optional[str]:
        if not prefix:
            return None

        sanitized_prefix = prefix.strip('/')
        if not sanitized_prefix:
            return filename

        return f"{sanitized_prefix}/{filename}"

    def _ensure_merged_txt_path(self, output_file: str) -> str:
        """
        生成合并数据的文件名
        例如: id.txt -> id_merged.txt
        """
        base, ext = os.path.splitext(output_file)
        return f"{base}_merged.txt"

    def batch_analyze_images(self, image_paths: List[str], prompt: str,
                            output_dir: str, progress_callback=None,
                            cos_result_prefix: Optional[str] = None,
                            force_reanalyze: bool = False) -> List[str]:
        """
        批量分析图片
        
        Args:
            image_paths: 图片路径列表
            prompt: 分析提示词
            output_dir: JSON输出目录
            progress_callback: 进度回调函数 callback(current, total, message)
            cos_result_prefix: 上传至COS的目标前缀（可选）
            force_reanalyze: 是否强制重新分析（即使JSON已存在）
            
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
                
                # 如果JSON已存在且不强制重新分析，则跳过
                if os.path.exists(json_path) and not force_reanalyze:
                    self.logger.info(f"JSON文件已存在，跳过分析 ({i}/{total}): {json_path}")
                    # 跳过时确保JSON已上传至COS，并补充图片COS路径（如果缺失）
                    if cos_result_prefix:
                        try:
                            with open(json_path, 'r+', encoding='utf-8') as f:
                                data = json.load(f)
                                
                                # 补充图片COS路径（如果缺失或为null）
                                if not data.get('图片COS路径'):
                                    image_cos_key = self._build_remote_key(
                                        cos_result_prefix,
                                        os.path.basename(image_path)
                                    )
                                    data['图片COS路径'] = image_cos_key
                                    # 更新本地JSON文件
                                    f.seek(0)
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                    f.truncate()
                                
                                # 同步上传JSON到COS
                                remote_key = self._build_remote_key(
                                    cos_result_prefix,
                                    os.path.basename(json_path)
                                )
                                self._upload_analysis_json(data, remote_key)
                        except Exception as exc:
                            self.logger.warning(f"处理已存在JSON失败: {exc}")
                            self.logger.warning(f"上传JSON至COS失败: {exc}")
                    json_files.append(json_path)
                    if progress_callback:
                        progress_callback(i, total, f"跳过已分析: {os.path.basename(image_path)}")
                    continue
                
                # 分析图片
                self.logger.info(f"开始分析图片 {i}/{total}: {image_path}")
                result = self.analyze_image(image_path, prompt)

                # 构建图片的COS路径：使用图片文件名
                image_cos_key = None
                if cos_result_prefix:
                    image_cos_key = self._build_remote_key(
                        cos_result_prefix,
                        os.path.basename(image_path)
                    )
                result['图片COS路径'] = image_cos_key
                
                # 保存JSON结果
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                if cos_result_prefix:
                    remote_key = self._build_remote_key(
                        cos_result_prefix,
                        os.path.basename(json_path)
                    )
                    self._upload_analysis_json(result, remote_key)

                json_files.append(json_path)
                self.logger.info(f"分析结果已保存: {json_path}")
                
            except Exception as e:
                self.logger.error(f"分析失败 {image_path}: {e}")
                if progress_callback:
                    progress_callback(i, total, f"分析失败: {os.path.basename(image_path)}")
        
        self.logger.info(f"批量分析完成，成功 {len(json_files)}/{total} 个")
        return json_files
    
    def merge_and_analyze_json(self, json_files: List[str], prompt: str,
                              output_file: str,
                              cos_result_prefix: Optional[str] = None) -> str:
        """
        合并JSON数据并进行二次分析
        
        Args:
            json_files: JSON文件路径列表
            prompt: 分析提示词
            output_file: 输出文件路径
            cos_result_prefix: 上传至COS的目标前缀（可选）
            
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
        
        # 生成合并数据文件名（例如: id.txt -> id_merged.txt）
        merged_json_file = self._ensure_merged_txt_path(output_file)
        
        # 保存合并数据到文件
        with open(merged_json_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=0)
        
        self.logger.info(f"合并数据已保存到: {merged_json_file}")
        if cos_result_prefix:
            merged_key = self._build_remote_key(
                cos_result_prefix,
                os.path.basename(merged_json_file)
            )
            self._upload_to_cos(merged_json_file, merged_key)
        
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
        
        # 保存最终分析结果到output_file（例如: id.txt）
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_output)
        
        self.logger.info(f"最终分析结果已保存到: {output_file}")
        self.logger.info(f"合并数据已保存到: {merged_json_file}")

        if cos_result_prefix:
            result_key = self._build_remote_key(
                cos_result_prefix,
                os.path.basename(output_file)
            )
            self._upload_to_cos(output_file, result_key)
        
        return final_output
