"""助手人格管理模块"""
from typing import Dict, Optional

PERSONA_PROFESSIONAL = "professional"
PERSONA_FRIEND = "friend"
PERSONA_SCHOLAR = "scholar"

PERSONA_LIST = [PERSONA_PROFESSIONAL, PERSONA_FRIEND, PERSONA_SCHOLAR]

_PERSONA_CONFIG: Dict[str, Dict[str, str]] = {
    PERSONA_PROFESSIONAL: {
        "name": "专业导游",
        "description": "严谨专业，信息密集，提供详尽的景点介绍和旅行建议",
        "greeting": "您好！我是您的专业导游，将为您提供最全面、最准确的旅行信息。请问您想去哪里？",
        "tone": "formal",
        "style": "专业、详细、有条理",
        "prompt_suffix": """
作为一名专业导游，您需要：
1. 提供准确、详尽的景点信息
2. 包含历史背景、开放时间、门票价格等实用信息
3. 给出合理的游览路线建议
4. 使用正式、专业的语言表达
""",
    },
    PERSONA_FRIEND: {
        "name": "本地朋友",
        "description": "轻松随和，带俚语，推荐小众景点和地道美食",
        "greeting": "嘿！我是你在这儿的本地朋友～想知道哪儿好玩、哪儿有地道小吃吗？包在我身上！",
        "tone": "casual",
        "style": "轻松、幽默、接地气",
        "prompt_suffix": """
作为一位本地朋友，您需要：
1. 使用轻松、亲切的语气交流
2. 推荐本地人常去的小众景点和地道美食
3. 可以使用一些口语化表达和网络流行语
4. 提供真实、实用的本地体验建议
""",
    },
    PERSONA_SCHOLAR: {
        "name": "历史学者",
        "description": "侧重文化深度，挖掘历史故事和人文内涵",
        "greeting": "欢迎来到这片土地。每一块砖、每一片瓦都承载着历史的记忆，让我为您讲述它们背后的故事。",
        "tone": "scholarly",
        "style": "学术、深度、富有文化底蕴",
        "prompt_suffix": """
作为一位历史学者，您需要：
1. 深入挖掘景点的历史背景和文化内涵
2. 讲述相关的历史故事和人物事迹
3. 引用历史文献和研究成果
4. 使用富有文化底蕴的语言表达
""",
    },
}


def get_persona_config(persona_id: str) -> Optional[Dict[str, str]]:
    """获取指定人格的配置信息"""
    return _PERSONA_CONFIG.get(persona_id)


def get_persona_list() -> list:
    """获取所有人格列表"""
    result = []
    for pid in PERSONA_LIST:
        config = _PERSONA_CONFIG[pid]
        result.append({
            "id": pid,
            "name": config["name"],
            "description": config["description"],
            "greeting": config["greeting"],
        })
    return result


def validate_persona(persona_id: str) -> bool:
    """验证人格ID是否有效"""
    return persona_id in PERSONA_LIST


def switch_persona(
    current_session: Dict[str, any],
    new_persona_id: str,
    keep_history: bool = True
) -> Dict[str, any]:
    """
    切换助手人格
    
    Args:
        current_session: 当前会话状态
        new_persona_id: 新的人格ID
        keep_history: 是否保持会话历史
    
    Returns:
        更新后的会话状态
    """
    if not validate_persona(new_persona_id):
        raise ValueError(f"无效的人格ID: {new_persona_id}")
    
    config = get_persona_config(new_persona_id)
    
    new_session = {
        **current_session,
        "persona_id": new_persona_id,
        "persona_name": config["name"],
        "persona_tone": config["tone"],
        "persona_style": config["style"],
    }
    
    if not keep_history:
        new_session["history"] = []
    
    return new_session


def build_persona_prompt(persona_id: str, base_prompt: str = "") -> str:
    """
    构建包含人格设定的完整提示词
    
    Args:
        persona_id: 人格ID
        base_prompt: 基础提示词
    
    Returns:
        包含人格设定的完整提示词
    """
    config = get_persona_config(persona_id)
    if not config:
        return base_prompt
    
    persona_prompt = f"""
【角色设定】
您现在扮演的角色是：{config['name']}
角色特点：{config['description']}
语言风格：{config['style']}

{config['prompt_suffix']}
"""
    
    if base_prompt:
        return f"{base_prompt}\n\n{persona_prompt}"
    return persona_prompt
