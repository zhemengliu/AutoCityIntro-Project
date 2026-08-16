"""LangChain LLM 封装（Kimi / Moonshot OpenAI 兼容接口）"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.moonshot.cn/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "kimi-k2.6")
# kimi-k2.6：thinking 开启时 temperature=1；关闭 thinking 时 temperature=0.6
OPENAI_THINKING = os.getenv("OPENAI_THINKING", "disabled").lower() not in ("0", "false", "off", "disabled")
OPENAI_TEMPERATURE = float(
    os.getenv(
        "OPENAI_TEMPERATURE",
        "1" if OPENAI_THINKING else "0.6",
    )
)


def get_llm(*, streaming: bool = False, temperature: float | None = None) -> ChatOpenAI:
    extra_body = {"thinking": {"type": "enabled" if OPENAI_THINKING else "disabled"}}
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        streaming=streaming,
        temperature=temperature if temperature is not None else OPENAI_TEMPERATURE,
        max_tokens=1500,
        extra_body=extra_body,
    )
