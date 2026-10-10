<!-- About 简介（推送后填写到仓库 About 栏）：
保险配置助手：家庭保障缺口分析→四险种配置方案→条款坑点清单 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-insurance
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, insurance, protection-planning, family-finance -->

# lhg-insurance：保险配置助手，家庭保障缺口一算就清

> **一句话介绍**：给 AI 编程助手装上"保险配置助手"——家庭结构/收入/负债输入 → 寿险/重疾/医疗/意外四维度保障缺口分析 → 险种配置方案 → 条款坑点清单（免责/等待期/续保）；**确定性审计 + 写入硬门双保险，收益率承诺与具体产品推荐出现即拦截**。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-insurance
> /plugin install lhg-insurance@lhg-plugs
> ```

> ⚠️ **合规声明（首屏置顶）**：本插件仅提供**保险知识科普与配置思路**，**非持牌保险建议**；投保前请咨询持牌保险顾问。本插件**不推荐任何具体保险产品**，**不承诺任何收益**。

## 它是什么

`lhg-insurance` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **3 个命令**（小白入口）：`insurance` 保障配置一条龙，`insurance-term` 条款五查（健康告知/免责/等待期/续保/理赔），`insurance-check` 方案自查
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：保障需求分析四张表、四大险种知识、条款阅读五查法、配置方案设计五步法
- **2 个专家 agent**：配置顾问、方案审计专家
- **1 个合规硬门 hook**：写入文件命中收益率承诺违禁词（年化收益/复利/稳赚/保本/锁定利率等）或产品推荐话术（推荐产品/产品链接/点击投保等）直接拦截，可一键关闭
- **8 条确定性审计规则**：纯 Python 标准库、零第三方依赖，含保额覆盖率计算、等待期冲突、重复投保、免责/等待期提示检查、违禁词与合规声明检查

## 合规设计：三层防护

1. **声明置顶**：README 首屏答案块下方、每个 SKILL.md 开头、每条命令输出开头，都有显著的合规声明。
2. **写入硬门**：hook 在文件写入前扫描收益率承诺与产品推荐关键词，命中即拦截（exit 2）；`LHG_INSURANCE_COMPLY_OFF=1` 可关闭。
3. **审计兜底**：`insurance_audit.py` 的 INS-YIELD-001（收益率承诺）、INS-PRODUCT-001（产品推荐）、CMP-DISC-001（声明缺失）是 blocker，`insurance-check` 命令逐条清零。

## 3 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-insurance:insurance` | 家庭信息→四维度缺口→配置方案→条款坑点清单 | `/lhg-insurance:insurance "夫妻35岁+1孩，年收入40万，房贷120万"` |
| `/lhg-insurance:insurance-term` | 条款五查：健康告知/免责/等待期/续保/理赔逐项拆解 | `/lhg-insurance:insurance-term "<条款文本>"` |
| `/lhg-insurance:insurance-check` | 方案自查：保额覆盖/等待期冲突/重复投保/合规 | `/lhg-insurance:insurance-check ./我的保障方案` |

## 目录结构

```
lhg-insurance/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 3 个命令：insurance / insurance-term / insurance-check
├── skills/                  # 4 个平台中立 skill（需求分析/四大险种/条款五查/方案设计，合规声明置顶）
├── agents/                  # 2 个专家 agent（advisor / auditor）
├── hooks/                   # 收益率承诺与产品推荐关键词拦截 hook（fail-open，可一键关闭）
├── scripts/audit/           # 确定性审计：insurance_audit.py（零第三方依赖）
├── fixtures/                # 好/坏对照用例
├── smoke_test.py            # 冒烟测试
├── ATTRIBUTION.md           # 灵感来源声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**Q：它能告诉我买哪款保险产品吗？**
A：不能，这是设计红线。本插件只给"险种配置思路"（买什么险种、多少保额、注意哪些条款坑），不点名任何具体产品。选产品请咨询持牌保险顾问。

**Q：它能告诉我保险的收益率吗？**
A：不能。保险首先是保障，任何收益率承诺都会被 hook 与审计脚本拦截。本插件不讨论收益。

**Q：我家已经有几份保单了，能用吗？**
A：能。`insurance` 命令会先登记已有保单（险种/保额/状态），再算缺口，避免重复投保；`insurance-check` 还能查出等待期冲突和重复投保。

**Q：一定要用 Claude Code 吗？**
A：`skills/` 下的方法论是平台中立的纯 Markdown，可直接搬到豆包、Workbuddy 等 agent 平台用。只有 commands/agents/hooks 需要 Claude Code。

**Q：我的家庭财务数据安全吗？**
A：家庭档案只存在你的本地工作目录，插件不上传任何数据到外部服务。合规硬门只做本地关键词扫描。

**Q：hook 把我正常的内容拦了怎么办？**
A：两种处理：① 确认内容确实合规后，`export LHG_INSURANCE_COMPLY_OFF=1` 关闭本次拦截；② 到本仓库提 issue（标题前缀 `[hook]`），我们优化关键词表。

## 自迭代

- 每个 skill 末尾有「自检与反馈」节：质检门 + 标准冒烟用例 + 一键提 issue。
- 发现规则误报/漏报、方法论不合理：到本仓库提 issue（标题带对应 skill 前缀，如 `[lhg-ins-need]`），附家庭结构特征与期望行为。

## 出品：刘洪光

刘洪光（https://github.com/lhg-skills）出品，lhg-plugs「小白专家插件」系列之一。
灵感来源见 [ATTRIBUTION.md](./ATTRIBUTION.md)（借鉴思路，实现与文案均为原创）。

---
⚠️ 合规声明：本插件仅提供保险知识科普与配置思路，**非持牌保险建议**；投保前请咨询持牌保险顾问。
