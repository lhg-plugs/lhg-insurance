#!/usr/bin/env python3
"""lhg-insurance 硬门：收益率承诺 / 具体产品推荐拦截。

触发：PreToolUse / Edit|Write。扫描本次写入/编辑的文件内容，
若命中收益率承诺违禁词（年化收益/复利/稳赚/保本/锁定利率等）
或具体产品推荐话术（推荐产品/产品链接/点击投保等），
以 exit code 2 拦截该操作，并给出改写指引。

逃生方式（按推荐度排序）：
  1. LHG_INSURANCE_COMPLY_OFF=1（环境变量，当前会话有效；关闭后
     关键词拦截不再触发，但审计脚本的 INS-YIELD-001 / INS-PRODUCT-001
     仍会在 insurance-check 时报 blocker）。
  2. /plugin disable lhg-insurance（整个插件停用，hooks 不再触发）。

设计原则：只有"命中关键词"才拦截；内部出错一律 fail-open
（直接放行，不报错）；零第三方依赖。

注意：本 hook 只做关键词层面的硬拦截，真正的合规判断
（上下文、语气）仍由 agent 按 skill 规范负责。
"""

import json
import os
import sys

# 收益率承诺违禁词（原创整理：常见收益承诺话术）
YIELD_KEYWORDS = [
    "年化收益", "复利", "稳赚", "保本", "必涨",
    "锁定利率", "收益演示", "承诺收益", "保证收益",
    "跑赢通胀", "翻倍收益",
]

# 具体产品推荐话术（原创整理）
PRODUCT_KEYWORDS = [
    "推荐产品", "首选产品", "产品链接", "点击投保",
    "购买链接", "投保链接", "必买", "限时抢购",
]

REWRITE_GUIDE = (
    "改写指引：删除收益率承诺与具体产品推荐；只保留保障缺口分析、"
    "险种知识科普与配置思路；标准话术替代："
    "“本插件仅提供保险知识科普与配置思路，非持牌保险建议；"
    "投保前请咨询持牌保险顾问。”"
)


def extract_text(tool_input):
    """从 Edit/Write 的输入中抽取待写入文本。"""
    parts = []
    for key in ("content", "new_string", "old_string", "file_text"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            parts.append(v)
    return "\n".join(parts)


def find_hits(text):
    hits = []
    for kw in YIELD_KEYWORDS + PRODUCT_KEYWORDS:
        if kw in text:
            hits.append(kw)
    return hits


def main() -> int:
    if os.environ.get("LHG_INSURANCE_COMPLY_OFF") == "1":
        return 0  # 逃生开关

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # 输入解析失败：fail-open

    tool_input = payload.get("tool_input", {}) or {}
    text = extract_text(tool_input)
    if not text:
        return 0

    try:
        hits = find_hits(text)
    except Exception:
        return 0  # 内部错误：fail-open

    if not hits:
        return 0

    msg = (
        "⛔ 合规硬门（lhg-insurance）：本次写入内容命中保险合规违禁词：%s。\n"
        "本插件仅提供保险知识科普与配置思路，不推荐具体产品、不承诺收益。\n%s\n"
        "确认为合规内容但被误拦：export LHG_INSURANCE_COMPLY_OFF=1 后重试。"
        % ("、".join(hits), REWRITE_GUIDE)
    )
    sys.stderr.write(msg + "\n")
    return 2  # exit 2 = 拦截本次工具调用


if __name__ == "__main__":
    sys.exit(main())
