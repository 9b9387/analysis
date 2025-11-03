from pydantic import BaseModel, Field

class ScorePattern(BaseModel):
    """番型数据描述。"""
    名称: str = Field(..., description="番型的名称", example="花牌")
    番数: int = Field(..., description="结算时该番型的番数", example=2)

class WinPattern(BaseModel):
    """胡牌方式数据描述。"""
    名称: str = Field(..., description="胡牌方式的名称", example="自摸")
    倍数: int = Field(..., description="结算时该胡牌方式的倍数", example=1)

class PlayerScoreData(BaseModel):
    """玩家分数数据。"""
    玩家名字: str = Field(..., description="玩家的名字", example="张三")
    番数列表: list[ScorePattern] = Field(..., description="玩家的单项番型的列表")
    胡牌信息: WinPattern = Field(..., description="玩家的胡牌牌型及其倍数")
    总番数: int = Field(..., description="玩家的总番数，通常为各个番型的番数之和，并可能会乘以胡牌牌型的倍数", example=15)
    庄家: bool = Field(..., description="玩家是否为庄家", example=False)
    连庄数: int = Field(..., description="玩家的连庄次数，庄家连庄时底分会增加", example=1)
    底分: int = Field(..., description="玩家的底分，根据庄家或闲家身份及连庄情况确定", example=10)
    分数变化: int = Field(..., description="玩家分数的变化量，带正负符号", example=5000)

class ScoreData(BaseModel):
    玩家分数数据: list[PlayerScoreData] = Field(..., description="所有玩家的分数数据列表")