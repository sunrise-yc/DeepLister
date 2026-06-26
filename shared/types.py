from typing import Optional
from pydantic import BaseModel

# --- 信号检测结果 ---

class SignalResult(BaseModel):
    """单类信号的检测结果"""
    triggered: bool
    type: Optional[str] = None  # 信号子类型
    detail: Optional[str] = None  # 触发原因描述
    confidence: float = 0.0  # 0-1，模型对此次检测的置信度

class SignalDetection(BaseModel):
    """四类信号的并行检测结果"""
    safety: SignalResult          # P0: 自伤/崩溃/抗拒
    comprehension: SignalResult   # P1: 理解偏差（含糊/误解）
    consistency: SignalResult      # P2: 前后矛盾
    sufficiency: SignalResult      # P3: 信息不足（只有结论无原因）

# --- 仲裁结果 ---

class ArbitrationResult(BaseModel):
    """策略仲裁的输出"""
    strategy: str  # safety_protocol | comprehension_correction | consistency_confirmation | depth_mining | proceed | transition | skip_topic
    priority: str  # P0 | P1 | P2 | P3 | P4
    follow_up_count: int  # 当前话题累计追问轮次
    force_proceed: bool = False  # 是否强制推进（达到上限时）

# --- 校验结果 ---

class VerificationResult(BaseModel):
    """质量校验的输出"""
    passed: bool
    strategy_consistency: bool = True  # 生成内容是否执行了仲裁策略
    repetition_check: bool = True     # 是否与最近2轮重复
    length_check: bool = True         # 是否≤2句话
    safety_check: bool = True         # 是否安全
    correction_direction: Optional[str] = None  # 不通过时的修正方向

# --- 话题状态 ---

class TopicStatus(BaseModel):
    """单个话题在画像中的状态"""
    status: str = "not_started"  # not_started | in_progress | completed | skipped
    core_dimensions_covered: list[str] = []
    key_signals: list[str] = []
    follow_up_count: int = 0
    completeness_score: float = 0.0
    current_sub_question: Optional[str] = None

# --- 一致性标记 ---

class ConsistencyFlag(BaseModel):
    """跨话题一致性问题的标记"""
    topic_pair: list[str]  # 涉及的两个话题ID
    description: str
    resolved: bool = False

# --- 会话记录 ---

class SessionRecord(BaseModel):
    """单次会话的摘要记录"""
    date: str
    topics_completed: list[str] = []
    duration_minutes: int = 0

# --- 用户画像 ---

class UserProfile(BaseModel):
    """跨会话持久化的用户画像，每轮对话都在读写"""
    user_id: str
    cognitive_level: str = "medium"  # low | medium | high
    communication_preference: str = "prefer_concrete_examples"  # prefer_concrete_examples | prefer_abstract | prefer_brief
    topics_status: dict[str, TopicStatus] = {}
    consistency_flags: list[ConsistencyFlag] = []
    session_history: list[SessionRecord] = []

# --- 决策日志单条 ---

class DecisionLogEntry(BaseModel):
    """一轮对话的完整决策链路"""
    turn_id: int
    user_reply: str
    detection_result: SignalDetection
    arbitration_result: ArbitrationResult
    generated_reply: str
    verification_result: VerificationResult
    evaluation: Optional[dict] = None  # 追问有效性评估

# --- 问卷结构 ---

class SubQuestion(BaseModel):
    """话题下的子问题"""
    question_id: str
    text: str
    dimension: str  # 对应core_dimensions中的哪个维度

class Topic(BaseModel):
    """问卷拆解后的话题单元"""
    topic_id: str
    topic_name: str
    description: str
    core_dimensions: list[str]
    opening_question: str
    sub_questions: list[SubQuestion] = []

class Questionnaire(BaseModel):
    """研究者上传的问卷"""
    title: str
    description: str
    topics: list[Topic]
