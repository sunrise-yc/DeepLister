from shared.config import Config

class LLMClient:
    """统一的LLM调用客户端"""
    
    def __init__(
        self,
        provider: str = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.provider = provider or Config.LLM_PROVIDER
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.model = model or Config.OPENAI_MODEL
        self.base_url = base_url or Config.OPENAI_BASE_URL
        self._openai_client = None
        self.call_count = 0
    
    @property
    def openai_client(self):
        """懒加载OpenAI客户端"""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._openai_client
    
    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """
        统一的聊天接口
        Args:
            messages: OpenAI格式的消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 生成温度
            max_tokens: 最大生成token数
        Returns:
            模型的文本回复
        """
        if self.provider == "openai":
            self.call_count += 1
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        
        elif self.provider == "ollama":
            import requests
            self.call_count += 1
            response = requests.post(
                f"{Config.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": Config.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature}
                }
            )
            return response.json()["message"]["content"]
        
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
    
    def chat_json(self, messages: list[dict], temperature: float = 0.1) -> dict:
        """
        调用LLM并期望返回JSON格式
        在messages中提示模型输出JSON，解析返回结果
        如果解析失败，返回空dict并打印警告
        """
        import json
        text = self.chat(messages, temperature=temperature)
        # 尝试从markdown代码块中提取JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[WARNING] LLM返回的内容无法解析为JSON: {text[:200]}")
            return {}
