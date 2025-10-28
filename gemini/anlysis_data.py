"""基于《麻将规则模板》整理的结构化数据定义。

该文件提供一套对 AI 友好的 Pydantic 数据模型，
用于描述麻将游戏的规则、番型与结算配置，
以便从视频与结算界面提取信息后生成标准化数据。
"""

from pydantic import BaseModel, Field

class MeldOptions(BaseModel):
    """吃、碰、杠等行牌操作权限。"""
    吃牌: bool = Field(..., description="是否发生了吃牌操作。", example=False)
    碰牌: bool = Field(..., description="是否发生了碰牌操作。", example=True)
    杠牌: bool = Field(..., description="是否发生了杠牌操作。", example=True)


class WinOptions(BaseModel):
    点炮胡: bool = Field(..., description="是否点炮胡。", example=True)
    自摸胡: bool = Field(..., description="是否自摸胡。", example=True)
    抢杠胡: bool = Field(..., description="是否抢杠胡。", example=True)
    杠上开花: bool = Field(..., description="是否杠上开花胡。", example=True)
    流局: bool = Field(..., description="是否流局。", example=True)

class WinType(BaseModel):
    """胡牌类型。"""
    牌型: str = Field(..., description="胡牌的牌型名称", example="碰碰胡")
    倍率: str = Field(..., description="该牌型的倍率", example="X2")

class ScorePatternSetting(BaseModel):
    """番型或胡牌方式的启用及倍数描述。"""
    名称: str = Field(..., description="番型的名称", example="碰碰胡")
    番数: str = Field(
        ...,
        description="结算时该番型的番数", example="2番",
    )


class AnalysisData(BaseModel):
    """麻将规则数据总览。"""
    # 结算种类: WinOptions = Field(..., description="牌局结果相关选项")
    番型统计: list[list[ScorePatternSetting]] = Field(..., description="结算界面出现的每个玩家的番型和对应的番数列表")
    # 行牌规则: MeldOptions = Field(..., description="吃、碰、杠等行牌规则。")
    胡牌牌型: WinType = Field(..., description="结算界面显示的赢牌玩家的胡牌牌型。")
    # 玩家分数: list[int] = Field(..., description="结算前玩家身上的分数", example=[100, 23, 15, 33])
    玩家底分: list[int] = Field(..., description="每位玩家结算时的底分。", example=[10, 5, 5, 5])
    番数总计: list[int] = Field(..., description="每位玩家的最终番数。", example=[22, 4, 3, 2])
    最后得分: list[int] = Field(..., description="每位玩家的最终得分。", example=[+12, -4, -4, -4])