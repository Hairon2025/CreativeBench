"""High-precision lexical safeguards before RAG and model invocation."""

import re
from dataclasses import dataclass

from creativebench.models import RiskType
from creativebench.security.models import SecurityFinding


@dataclass(frozen=True)
class SecurityRule:
    id: str
    risk: RiskType
    patterns: tuple[re.Pattern[str], ...]


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


RULES = (
    SecurityRule(
        id="override-ignore-rules",
        risk=RiskType.INSTRUCTION_OVERRIDE,
        patterns=_compile(
            r"忽略.{0,12}(之前|以上|原有|系统|开发者).{0,8}(指令|规则)",
            r"(override|ignore).{0,20}(system|developer|previous).{0,10}(instruction|prompt)",
            r"(最高优先级|取消所有规则|绕过所有限制)",
        ),
    ),
    SecurityRule(
        id="injection-execute-data",
        risk=RiskType.PROMPT_INJECTION,
        patterns=_compile(
            r"(执行|遵循).{0,12}(文档|网页|引用|XML|代码块).{0,8}(中|内).{0,8}(指令|命令)",
            r"(把|将).{0,12}(内容|文本).{0,8}(当作|视为).{0,8}(系统指令|system prompt)",
            r"(reveal|print|输出|泄露).{0,12}(system prompt|系统提示词|隐藏指令)",
        ),
    ),
    SecurityRule(
        id="jailbreak-unrestricted-role",
        risk=RiskType.ROLEPLAY_JAILBREAK,
        patterns=_compile(
            r"(扮演|进入).{0,12}(不受限制|无规则|没有道德约束).{0,8}(角色|模式|AI)",
            r"\b(DAN|developer mode|jailbreak)\b",
            r"假设.{0,12}(安全规则|平台限制).{0,8}(不存在|无效)",
        ),
    ),
    SecurityRule(
        id="sensitive-actionable-harm",
        risk=RiskType.SENSITIVE_INDUCEMENT,
        patterns=_compile(
            r"(详细|逐步|可执行).{0,10}(制作|制造).{0,8}(炸弹|爆炸物|毒药)",
            r"(入侵|攻击).{0,10}(账号|服务器|网站).{0,10}(步骤|代码|教程)",
            r"(伤害|杀死).{0,8}(具体方法|操作步骤|实施方案)",
        ),
    ),
    SecurityRule(
        id="privacy-real-person",
        risk=RiskType.PRIVACY_REQUEST,
        patterns=_compile(
            r"(查找|提供|告诉我|推断).{0,12}(真实|某人|这个人).{0,8}(住址|手机号|身份证|密码)",
            r"(泄露|获取).{0,12}(私人|个人).{0,8}(联系方式|身份信息|定位)",
        ),
    ),
)


def scan_prompt(prompt_text: str) -> SecurityFinding:
    """Return deterministic signals; absence of a match is not a safety guarantee."""

    text = prompt_text.strip()
    if not text:
        raise ValueError("待扫描 Prompt 不能为空")
    matched_rules = [
        rule for rule in RULES if any(pattern.search(text) for pattern in rule.patterns)
    ]
    if not matched_rules:
        return SecurityFinding(
            risks=[RiskType.NORMAL],
            matched_rule_ids=[],
            requires_review=False,
        )
    risks = list(dict.fromkeys(rule.risk for rule in matched_rules))
    return SecurityFinding(
        risks=risks,
        matched_rule_ids=[rule.id for rule in matched_rules],
        requires_review=True,
    )
