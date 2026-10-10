#!/usr/bin/env python3
"""lhg-insurance 确定性审计：扫描目标目录下的家庭档案/保单/配置方案文件。

输入约定（--target 目录）：
  profile.json    家庭档案：{"家庭年收入": 数, "负债总额": 数, "成员": [...]}
  policies.json   保单清单：[{"成员": 名, "险种": 寿险/重疾险/医疗险/意外险,
                            "保额": 数, "状态": "waiting|active"}]
  *.md            配置方案报告（须含合规声明）

检查：
  INS-COVER-001   寿险保额 < 负债总额 + 5×家庭年收入（warning）
  INS-WAIT-001    同一成员同一险种 ≥2 条 waiting 保单：等待期冲突（blocker）
  INS-DUP-001     同一成员同一险种 ≥2 条 active 保单：重复投保（warning）
  INS-DISCLAIM-001 报告未提及“免责”（warning）
  INS-WAITNOTE-001 报告未提及“等待期”（warning）
  INS-YIELD-001   报告含收益率承诺违禁词（blocker）
  INS-PRODUCT-001 报告含具体产品推荐话术（blocker）
  CMP-DISC-001    报告缺少合规声明（blocker）

用法：
    python3 insurance_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning]

exit code：0=无命中（按 --fail-on 口径），2=有 blocker，1=仅 warning（且 --fail-on=warning）。
零第三方依赖。规则文案均为本项目原创。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-insurance/insurance-audit"

VALID_TYPES = ("寿险", "重疾险", "医疗险", "意外险")
COMPLIANCE_STMT = "非持牌保险建议"
YIELD_KEYWORDS = [
    "年化收益", "复利", "稳赚", "保本", "必涨",
    "锁定利率", "收益演示", "承诺收益", "保证收益",
    "跑赢通胀", "翻倍收益",
]
PRODUCT_KEYWORDS = [
    "推荐产品", "首选产品", "产品链接", "点击投保",
    "购买链接", "投保链接", "必买", "限时抢购",
]


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line=0, snippet="", detail=""):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {"rule_id": self.rule_id, "severity": self.severity,
                "category": self.category, "title": self.title,
                "file": self.file, "line": self.line,
                "snippet": self.snippet, "detail": self.detail}


findings = []


def add(rule_id, severity, category, title, file, line=0, snippet="", detail=""):
    findings.append(Finding(rule_id, severity, category, title, file, line, snippet, detail))


def read_text(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def load_json(path):
    return json.loads(read_text(path))


# ---------------------------------------------------------------- 家庭档案 + 保单

def check_profile(path):
    try:
        d = load_json(path)
        income = float(d["家庭年收入"])
        debt = float(d.get("负债总额", 0))
        if income <= 0:
            raise ValueError("家庭年收入须为正数")
        return income, debt
    except Exception as e:
        add("INS-COVER-001", "blocker", "档案", "profile.json 无法解析或字段非法",
            path, detail=str(e))
        return None, None


def check_policies(path, income, debt):
    try:
        policies = load_json(path)
    except Exception as e:
        add("INS-COVER-001", "blocker", "保单", "policies.json 无法解析",
            path, detail=str(e))
        return
    if not isinstance(policies, list):
        policies = [policies]

    # 保额覆盖率：寿险保额总和 vs 负债 + 5 年收入
    life_total = 0.0
    groups = {}  # (成员, 险种, 状态) -> 计数
    for i, p in enumerate(policies):
        member = p.get("成员", "?")
        kind = p.get("险种", "?")
        status = p.get("状态", "active")
        try:
            amt = float(p.get("保额", 0))
        except Exception:
            amt = 0.0
        if kind == "寿险" and status == "active" and amt > 0:
            life_total += amt
        key = (member, kind, status)
        groups[key] = groups.get(key, 0) + 1

    if income is not None:
        need = debt + 5 * income
        ratio = (life_total / need) if need > 0 else 1.0
        if ratio < 1.0:
            add("INS-COVER-001", "warning", "保额", "寿险保额覆盖率不足",
                path, snippet="覆盖率 %.0f%%" % (ratio * 100),
                detail="寿险保额合计 %.0f 元，负债总额 + 5 年家庭年收入 = %.0f 元，"
                       "覆盖率 %.0f%% < 100%%；建议在配置方案中补足缺口或说明原因"
                       % (life_total, need, ratio * 100))

    # 等待期冲突：同一成员同一险种 ≥2 条 waiting
    for (member, kind, status), n in sorted(groups.items()):
        if status == "waiting" and n >= 2:
            add("INS-WAIT-001", "blocker", "保单", "等待期冲突：同一成员同一险种有多份等待期保单",
                path, snippet="%s·%s" % (member, kind),
                detail="成员 %r 的 %s 有 %d 份状态为 waiting 的保单；"
                       "等待期内出险可能无法理赔，重复投保浪费保费，请合并或退保其中一份"
                       % (member, kind, n))
        elif status == "active" and n >= 2:
            add("INS-DUP-001", "warning", "保单", "疑似重复投保",
                path, snippet="%s·%s" % (member, kind),
                detail="成员 %r 的 %s 有 %d 份生效中保单；请确认是刻意叠加保额"
                       "还是重复购买，重复购买建议退保止损" % (member, kind, n))


# ---------------------------------------------------------------- 报告合规

def check_report(path):
    text = read_text(path)
    for kw in YIELD_KEYWORDS:
        idx = text.find(kw)
        if idx >= 0:
            line = text.count("\n", 0, idx) + 1
            add("INS-YIELD-001", "blocker", "合规", "报告含收益率承诺违禁词",
                path, line=line, snippet=kw,
                detail="第 %d 行命中“%s”；本插件不承诺任何收益，请删除该表述" % (line, kw))
            break  # 每类每文件报一次即可
    for kw in PRODUCT_KEYWORDS:
        idx = text.find(kw)
        if idx >= 0:
            line = text.count("\n", 0, idx) + 1
            add("INS-PRODUCT-001", "blocker", "合规", "报告含具体产品推荐话术",
                path, line=line, snippet=kw,
                detail="第 %d 行命中“%s”；本插件不推荐具体产品，请改为险种配置思路" % (line, kw))
            break
    if "免责" not in text:
        add("INS-DISCLAIM-001", "warning", "条款", "报告未提示免责条款",
            path, detail="配置方案未提及“免责条款”；每份保单都应列出主要免责情形，"
                         "避免用户误以为“什么都赔”")
    if "等待期" not in text:
        add("INS-WAITNOTE-001", "warning", "条款", "报告未标注等待期",
            path, detail="配置方案未提及“等待期”；医疗/重疾险等待期（常见 30/90/180 天）"
                         "内出险多不赔，必须明确标注")
    if COMPLIANCE_STMT not in text:
        add("CMP-DISC-001", "blocker", "合规", "报告缺少合规声明",
            path, detail="报告须原样附带合规声明块（含“%s”）" % COMPLIANCE_STMT)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--format", default="json", choices=["json", "text"])
    ap.add_argument("--fail-on", default="blocker", choices=["blocker", "warning"])
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if os.path.isdir(target):
        files = [os.path.join(target, f) for f in sorted(os.listdir(target))]
    else:
        files = [target]

    income, debt = None, None
    for p in files:
        base = os.path.basename(p)
        if not os.path.isfile(p):
            continue
        if base == "profile.json":
            income, debt = check_profile(p)
        elif base == "policies.json":
            # 延迟到 profile 解析完再跑：先收集
            pass
        elif base.endswith(".md"):
            check_report(p)

    for p in files:
        if os.path.isfile(p) and os.path.basename(p) == "policies.json":
            check_policies(p, income, debt)

    n_blocker = sum(1 for f in findings if f.severity == "blocker")
    n_warning = sum(1 for f in findings if f.severity == "warning")
    summary = {"tool": TOOL, "version": VERSION, "target": target,
               "blocker": n_blocker, "warning": n_warning,
               "total": len(findings)}

    if args.format == "json":
        out = {"summary": summary,
               "findings": [f.to_dict() for f in findings]}
        sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        lines = ["[%s] %s blocker=%d warning=%d" % (TOOL, target, n_blocker, n_warning)]
        for f in findings:
            lines.append("%s %s %s:%s %s" % (f.severity.upper(), f.rule_id, f.file, f.line, f.title))
            if f.detail:
                lines.append("    " + f.detail)
        sys.stdout.write("\n".join(lines) + "\n")

    if n_blocker:
        return 2
    if n_warning and args.fail_on == "warning":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
