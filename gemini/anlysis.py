from google import genai
import time
import os
import argparse
import json
import glob
from anlysis_data import AnalysisData
from google.genai import types

class MahjongVideoAnalyzer:
    """
    基于Gemini的麻将视频分析器
    """
    
    def __init__(self):
        """
        初始化分析器
        
        Args:
            api_key: Gemini API密钥，如果不提供则从环境变量GEMINI_API_KEY获取
        """
        api_key = "AIzaSyAnLAvq3I9Md70gnFWYo7jJRPGkJNK4xho"
        # api_key=os.getenv('GEMINI_API_KEY')
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=6000_000))

    def upload_file(self, video_path: str) -> str:
        """
        上传视频文件到Gemini
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            上传后的文件名
        """
        print(f"正在上传文件: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"文件不存在: {video_path}")
        
        video_file = self.client.files.upload(file=video_path)
        
        # 等待文件处理完成
        while video_file.state.name == "PROCESSING":
            print('.', end='', flush=True)
            time.sleep(1)
            video_file = self.client.files.get(name=video_file.name)
        
        if video_file.state.name == "FAILED":
            raise ValueError(f"文件处理失败: {video_file.state.name}")
        
        print(f"\n文件上传成功: {video_file.name}")
        return video_file.name
    
    def analyze_mahjong_game(self, media_file_name: str, media_path: str = "") -> AnalysisData:
        """
        分析麻将游戏媒体（视频或图片）
        
        Args:
            media_file_name: 已上传的媒体文件名
            media_path: 原始媒体文件路径（用于记录）
            
        Returns:
            分析结果
        """
        media_file = self.client.files.get(name=media_file_name)
        print(f"分析文件: {media_file.uri}")
        
        prompt = self._get_analysis_prompt()
        
        response = self.client.models.generate_content(
            model="models/gemini-2.5-pro",
            contents=[media_file, prompt],
            config={
                'system_instruction': '你是一位麻将高手和麻将游戏分析专家，擅长游戏记分和分析。',
                'response_mime_type': 'application/json',
                'response_schema': AnalysisData,
                'http_options': types.HttpOptions(timeout=600_000)
            },
        )
        
        # 解析响应
        result_data = json.loads(response.text)
        
        return AnalysisData(**result_data)
    
    def _get_analysis_prompt(self) -> str:
        """
        获取麻将游戏分析提示词
        """
        return """
你是一个专业的麻将游戏分析专家。
请仔细观看这个麻将游戏的结算截图，详细分析出：
该游戏的具体玩法规则，以及结算的计分规则。
返回标准的JSON格式数据。

如果有获胜玩家，请通过结算界面识别出胜利玩家的胡牌牌型以及对应的倍数（不是番数），例如：平胡 X1，填入对应的 `胡牌类型` 字段，只可以是以下列出的牌型名称。
如果没有完结获胜，则填入流局即可。

胡牌牌型的名词解释和定义，胡牌类型只可以是以下列出的牌型名称：
一、 基本/复合牌型
平胡: 由四个顺子（例如123万）或刻子（例如444筒）和一个对子（例如99筒）组成的标准胡牌结构。
碰碰胡: 由四个刻子（例如111万, 222筒, 333条, 888万）和一个对子（例如东东）组成的胡牌结构，牌中不含任何顺子。
七小对: 由七个独立的对子（例如11万, 22万, 33万...）组成的胡牌结构，不含任何顺子或刻子。
豪华七小对: 在七小对结构中，包含一组四张相同牌（例如2222万）和五个独立的对子。
双豪华七小对: 在七小对结构中，包含两组四张相同牌（例如2222万, 4444筒）和三个独立的对子。
三豪华七小对: 在七小对结构中，包含三组四张相同牌（例如2222万, 4444筒, 6666条）和一个独立的对子。
清一色: 胡牌时，手牌中所有14张牌均由同一花色（万、筒、或条）组成，不含字牌。
混一色: 胡牌时，手牌由单一花色（万、筒、或条）的牌和字牌（风牌、箭牌）组成，不含其他花色的牌。
清一色碰碰胡: 牌型既是“清一色”，又是“碰碰胡”。所有牌为同一花色，且结构为四个刻子加一对子。
混一色碰碰胡: 牌型既是“混一色”，又是“碰碰胡”。所有牌为同一花色和字牌，且结构为四个刻子加一对子。
混幺九: 牌型中所有顺子、刻子、对子仅由牌面为“1”或“9”的数牌和字牌组成。
清幺九: 牌型中所有顺子、刻子、对子仅由牌面为“1”或“9”的数牌组成，不含任何字牌。
将对: 牌型为“碰碰胡”，且所有刻子和对子仅由牌面为“2”、“5”、“8”的数牌组成。
中张（无1和9）: 牌型中所有牌仅由牌面为“2”至“8”的数牌组成，不含1、9和任何字牌。

二、 字牌特殊牌型（风牌、箭牌）
小三元: 牌型中包含两种箭牌（中、发、白）的刻子/杠，和剩下的另一种箭牌作对子（将牌）。
大三元: 牌型中包含所有三种箭牌（中、发、白）的刻子/杠，外加任意一个对子和任意一个刻子/顺子。
小四喜: 牌型中包含三种风牌（东、南、西、北）的刻子/杠，和剩下的第四种风牌作对子（将牌）。
大四喜: 牌型中包含所有四种风牌（东、南、西、北）的刻子/杠，外加任意一个对子（将牌）。
十三幺: 牌型由所有幺九牌（1、9的万筒条）和所有字牌（东南西北中发白）各一张，外加其中任意一张作为将牌（对子）组成。

三、 特殊牌张/数量牌型
十八罗汉: 牌型中包含四组杠（明杠或暗杠），外加一个对子。
一条龙: 牌型中包含同一花色从1到9的数字牌组成的三个顺子（123, 456, 789）。
全球人: 玩家通过吃、碰、杠，使得落地牌（面子）累计达到12张，手中只剩下一张单张牌，通过自摸或点炮胡这张单张牌（单吊）。

四、 特殊胡牌方式（倍数与动作相关）
天胡: 庄家（东家）在起手拿到14张牌后，无需摸牌即达成胡牌。
地胡: 非庄家玩家在第一巡内（庄家打出第一张牌后）通过自摸达成胡牌，期间未发生吃、碰、杠。
人胡: 第一巡内，玩家通过直杠或暗杠后摸牌达成胡牌。
抢杠胡: 其他玩家宣布补明杠时，正好胡这张补杠的牌。
杠上开花: 玩家通过杠牌（直杠、补杠、暗杠）后，摸取牌墙顶部的补牌（杠牌）达成自摸胡牌。
海底捞月: 玩家摸到牌墙中的最后一张牌达成自摸胡牌。
门清: 玩家在胡牌前，手牌没有经过任何吃、碰、明杠的操作。
卡五星: 玩家以一张数牌5作为胡牌张，形成一个456的顺子中的“卡张”胡法（例如胡5筒，卡在4筒和6筒之间）。
一炮多响: 玩家打出的点炮牌导致多个其他玩家同时胡牌。

五、 鬼牌/百搭牌相关（假设鬼牌为“中”）
无鬼胡: 胡牌时手牌中不包含任何“鬼牌”/“百搭牌”，且为自摸胡牌。
四鬼胡: 手牌中拥有四张“鬼牌”/“百搭牌”时，直接宣告胡牌（特殊规则）。
三金到: 庄家或闲家起手拿到的14张牌中，包含三张“鬼牌”/“百搭牌”时，直接宣告胡牌（特殊规则）。
鬼归位: 胡牌时，所有鬼牌/百搭牌都作为它们原始的牌面参与组成顺子、刻子或对子，没有作为其他牌型替代。
鬼吊: 玩家的手牌结构已构成一个听牌状态，且只需一张“鬼牌”即可听多张牌胡牌。
飞鬼（漂财，金）: 在“鬼吊”听牌情况下，打出一张鬼牌，但仍能维持鬼吊状态（听多张牌胡牌）。打出两张鬼牌为X4。

另外，请注意分析头像上的庄家信息，将其写入番型统计字段，如："{庄家，2连庄}，必须包含庄家信息"
"""

    def analyze_media_file(self, media_path: str) -> AnalysisData:
        """
        完整的媒体分析流程：上传并分析
        
        Args:
            media_path: 媒体文件路径
            
        Returns:
            分析结果
        """
        # 上传媒体
        media_file_name = self.upload_file(media_path)
        
        # 分析媒体
        result = self.analyze_mahjong_game(media_file_name, media_path)
        
        return result

def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description='麻将媒体分析工具 - 使用Gemini AI分析麻将游戏视频或图片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python anlysis.py -d /path/to/directory --type video
  python anlysis.py -d /path/to/directory --type image
        """
    )
    
    parser.add_argument(
        '-d', '--directory',
        required=True,
        dest='directory',
        help='包含媒体文件的目录路径'
    )
    
    parser.add_argument(
        '--type',
        choices=['video', 'image'],
        default='video',
        help='媒体类型：video (MP4) 或 image (PNG)'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # 验证目录是否存在
    if not os.path.isdir(args.directory):
        print(f"错误: 目录不存在: {args.directory}")
        exit(1)
    
    # 根据类型设置文件扩展名
    if args.type == 'video':
        extension = '*.mp4'
        media_type_desc = 'MP4'
    else:
        extension = '*.png'
        media_type_desc = 'PNG'
    
    # 查找所有媒体文件
    media_files = glob.glob(os.path.join(args.directory, '**', extension), recursive=True)
    
    if not media_files:
        print(f"在目录 {args.directory} 中未找到任何{media_type_desc}文件。")
        exit(0)
    
    print(f"找到 {len(media_files)} 个{media_type_desc}文件，开始分析...")
    
    analyzer = MahjongVideoAnalyzer()
    
    for i, media_path in enumerate(media_files, 1):
        print(f"\n[{i}/{len(media_files)}] 正在分析: {media_path}")
        
        try:
            result = analyzer.analyze_media_file(media_path)
            
            # 保存结果到JSON文件
            timestamp = int(time.time())
            media_name = os.path.splitext(os.path.basename(media_path))[0]
            output_file = f"analysis_{media_name}_{timestamp}.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"结果已保存到: {output_file}")
        
        except Exception as e:
            print(f"分析失败: {media_path} - {e}")
    
    print("\n所有文件分析完成。")
    exit(0)