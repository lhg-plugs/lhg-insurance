#!/usr/bin/env python3
"""lhg-insurance 插件冒烟测试：全部绿才算过。

检查项：
 1. 三个 JSON 合法（plugin.json / marketplace.json / hooks.json）
 2. 4 个 SKILL.md 都有 name/description frontmatter，且 150~320 行
 3. 3 个 commands 都有 description frontmatter
 4. 2 个 agents 都有 name/description/tools/model frontmatter
 5. skills 平台中立：不含 Claude Code 专有工具名
 6. 合规声明：README 首屏（答案块下方）、每个 SKILL.md 开头、
    每个 command 开头都有合规声明
 7. fixtures：坏 fixture 的埋点规则必须全部命中且脚本 exit!=0；
    好 fixture 零 blocker 且 exit==0
 8. hooks 脚本：违禁词拦截 / 逃生开关 / fail-open

用法：python3 smoke_test.py [--repo <插件根目录>]
退出码：0=全绿，1=有失败。
"""

import argparse
import json
import os
import re
import subprocess
import sys

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    return cond


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    text = read(path)
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


BAD_MUST = {"INS-COVER-001", "INS-WAIT-001", "INS-DUP-001",
            "INS-DISCLAIM-001", "INS-WAITNOTE-001",
            "INS-YIELD-001", "INS-PRODUCT-001", "CMP-DISC-001"}
NEUTRAL_DENY = ["Task tool", "Bash tool", "Edit tool", "Write tool", "Read tool",
                "AskUserQuestion", "subagent_type", "PreToolUse", "PostToolUse",
                "${CLAUDE_", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"]
COMPLIANCE = "非持牌保险建议"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    AUDIT = os.path.join(repo, "scripts", "audit")

    # 1. JSON 合法
    for rel in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                "hooks/hooks.json"]:
        p = os.path.join(repo, rel)
        try:
            d = json.loads(read(p))
            check("JSON 合法: " + rel, True)
            if rel.endswith("plugin.json"):
                check("plugin.json name==lhg-insurance", d.get("name") == "lhg-insurance",
                      str(d.get("name")))
                check("plugin.json 有 version/description/author",
                      all(d.get(k) for k in ("version", "description", "author")))
            if rel.endswith("marketplace.json"):
                ps = d.get("plugins", [])
                check("marketplace.json source==./",
                      len(ps) == 1 and ps[0].get("source") == "./" and
                      ps[0].get("name") == "lhg-insurance", str(ps))
            if rel.endswith("hooks.json"):
                check("hooks.json 顶层有 hooks 包装", "hooks" in d)
                check("hooks.json 有 PreToolUse", "PreToolUse" in d["hooks"],
                      str(list(d["hooks"].keys())))
        except Exception as e:
            check("JSON 合法: " + rel, False, str(e))

    # 2. SKILL.md
    for skill in ["lhg-ins-need", "lhg-ins-four", "lhg-ins-terms", "lhg-ins-plan"]:
        p = os.path.join(repo, "skills", skill, "SKILL.md")
        fm = frontmatter(p)
        check("skill frontmatter: " + skill,
              bool(fm.get("name")) and bool(fm.get("description")),
              "name=%s" % fm.get("name"))
        nlines = len(read(p).split("\n"))
        check("skill 行数 150~320: %s (%d 行)" % (skill, nlines),
              150 <= nlines <= 320, str(nlines))
        body = read(p)
        bad_words = [w for w in NEUTRAL_DENY if w in body]
        check("skill 平台中立: " + skill, not bad_words, "命中: %s" % bad_words)
        check("skill 有出品区: " + skill,
              "出品：刘洪光" in body and "https://github.com/lhg-skills" in body)
        check("skill 有自检与反馈: " + skill, "自检与反馈" in body)
        check("skill 开头有合规声明: " + skill, COMPLIANCE in body.split("## 1.")[0],
              "首屏声明缺失")

    # 3. commands
    for cmd in ["insurance", "insurance-term", "insurance-check"]:
        p = os.path.join(repo, "commands", cmd + ".md")
        fm = frontmatter(p)
        check("command description: " + cmd, bool(fm.get("description")),
              str(fm.get("description"))[:60])
        check("command 有 argument-hint: " + cmd, bool(fm.get("argument-hint")))
        head = read(p).split("## 流程")[0]
        check("command 开头有合规声明: " + cmd, COMPLIANCE in head, "开头声明缺失")

    # 4. agents
    for ag in ["advisor", "auditor"]:
        p = os.path.join(repo, "agents", ag + ".md")
        fm = frontmatter(p)
        check("agent frontmatter: " + ag,
              all(fm.get(k) for k in ("name", "description", "tools", "model")),
              str({k: fm.get(k) for k in ("name", "model")}))

    # 5. README 合规声明置顶（答案块正下方）
    readme = read(os.path.join(repo, "README.md"))
    first_block = readme.split("## 它是什么")[0]
    check("README 首屏有合规声明", COMPLIANCE in first_block, "首屏声明缺失")
    check("README 有答案块", "一键安装" in first_block and "一句话介绍" in first_block)
    check("README 答案块下方紧跟合规声明",
          first_block.find(COMPLIANCE) > first_block.find("一键安装"), "声明位置不对")

    # 6. 审计脚本冒烟
    def audit_hits(target):
        r = run([sys.executable, os.path.join(AUDIT, "insurance_audit.py"),
                 "--target", os.path.join(repo, target), "--format", "json"])
        try:
            d = json.loads(r.stdout)
        except Exception:
            return None, r.returncode, []
        return d["summary"], r.returncode, [f["rule_id"] for f in d["findings"]]

    s, code, ids = audit_hits("fixtures/plan-bad")
    check("坏 fixture exit!=0", code != 0, "exit=%d" % code)
    check("坏 fixture blocker>0", s and s["blocker"] > 0, str(s))
    missing = BAD_MUST - set(ids)
    check("埋点全命中 (%d/%d)" % (len(BAD_MUST - missing), len(BAD_MUST)),
          not missing, "缺失: %s" % sorted(missing))

    s, code, _ = audit_hits("fixtures/plan-good")
    check("好 fixture 零 blocker", s and s["blocker"] == 0, str(s))
    check("好 fixture exit==0", code == 0, "exit=%d" % code)

    # 7. hooks：违禁词拦截
    def hook(payload, env=None):
        e = dict(os.environ)
        e.update(env or {})
        return run([sys.executable, os.path.join(repo, "hooks", "pre_compliance_gate.py")],
                   input=payload, env=e)

    r = hook('{"tool_input":{"file_path":"a.md","content":"这款产品年化收益可达4%，推荐产品速看。"}}')
    check("hook: 命中违禁词被拦截", r.returncode == 2 and "合规硬门" in r.stderr,
          "exit=%d" % r.returncode)

    r = hook('{"tool_input":{"file_path":"a.md","content":"寿险缺口=负债+5年收入，配置思路如下。"}}')
    check("hook: 合规内容放行", r.returncode == 0 and not r.stderr.strip(),
          r.stderr[:80])

    r = hook('{"tool_input":{"file_path":"a.md","content":"年化收益可达4%。"}}',
             {"LHG_INSURANCE_COMPLY_OFF": "1"})
    check("hook: 逃生开关生效", r.returncode == 0, "exit=%d" % r.returncode)

    r = hook("not-json{{{")
    check("hook: 非法输入 fail-open", r.returncode == 0, r.stderr[:80])

    # 报告
    print("=" * 60)
    print("lhg-insurance 冒烟测试报告")
    print("=" * 60)
    fails = 0
    for st, name, detail in results:
        mark = "✓" if st == PASS else "✗"
        print("%s %s %s" % (mark, st, name))
        if detail and st == FAIL:
            print("    → %s" % detail)
        if st == FAIL:
            fails += 1
    print("=" * 60)
    print("共 %d 项，通过 %d，失败 %d" % (len(results), len(results) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
