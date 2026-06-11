import os

class Config:
    """全局配置，从环境变量读取，有合理默认值"""
    
    # LLM配置
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # openai | ollama
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    # Ollama配置（开发调试用）
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    # 数据存储
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    PROFILE_DIR: str = os.getenv("PROFILE_DIR", "./data/profiles")
    LOG_DIR: str = os.getenv("LOG_DIR", "./data/logs")
    
    # Harness参数
    MAX_FOLLOW_UP_PER_TOPIC: int = 3  # 每话题最多追问轮次
    MAX_CONSECUTIVE_VAGUE: int = 2     # 连续敷衍回复上限
    MAX_VERIFY_RETRY: int = 1          # 校验不通过最大重试次数
    
    # LLM调用参数
    TEMPERATURE_DETECT: float = 0.1    # 检测层：低温度保证稳定
    TEMPERATURE_GENERATE: float = 0.7  # 生成层：适当温度增加自然度
    TEMPERATURE_VERIFY: float = 0.1    # 校验层：低温度保证准确
    
    @classmethod
    def ensure_dirs(cls):
        """确保数据目录存在"""
        for d in [cls.DATA_DIR, cls.PROFILE_DIR, cls.LOG_DIR]:
            os.makedirs(d, exist_ok=True)
