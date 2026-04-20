# 🧠 AI 情感军师 Agent (Emotional Advisor)

这是一个基于大型语言模型（LLM）和向量知识库（RAG）打造的本地化情感分析与社交辅助智能体（Agent）。它能够实时接入微信聊天记录，自动为你构建联系人专属“性格档案”，分析聊天走向，并提供深度的情感策略与沟通建议。

---

## 📖 写在前面

在这个世界里，我似乎总是扮演着“旁观者清”的军师角色——每当朋友带着感情的伤痕来找我，我总能冷静地为他们剖析利弊、指点迷津。可一旦成为故事里的主角，我就成了那个最笨拙、最无可救药的小丑，在自己的感情里一败涂地，医者始终无法自医。

无数个复盘失败经历的深夜里，我萌生了做这个 Agent 的念头。我将 GitHub 上众多优秀的开源思维模型与分析技能汇聚于此，试图用算法的理智，去填补我们在爱情中容易盲目和冲动的缺陷。

我敲下这些代码，不仅仅是为了打造一个工具，更是为了传递一份微光的祝愿：希望它能为你提供最清醒的视角和最妥帖的建议。愿你在爱里能拥有智慧与底气，去拥抱真正对的人，永远不必像我一样，成为那个在回忆里独自苦笑的“小丑”。

## ✨ 核心特性

- 🤖 **多技能调度架构 (Multi-Skill Agent)**
  - 内置自然语言意图分发系统，自动将你的需求派发给最合适的专有技能（Skill）。
  - **SimpSkill (情感军师)**：基于历史聊天数据，分析对方的情绪状态、捕捉潜在信号、生成专属的破冰或暧昧期回复话术。
  - **NuwaSkill (思维模拟)**：加载特定名人的思维模型（如 Naval、马斯克等），为你提供高阶的认知视角的决策建议。
  - **BaziSkill (命理辅助)**：基于四柱八字的性格及运势推演插件。
- 🔄 **微信无缝实时同步**
  - 原生适配 [WeFlow](https://github.com/weflow-app/weflow) 的本地 HTTP API 和 SSE 推送接口。
  - 支持后台静默监听微信新消息，也支持输入指令主动**增量拉取**历史记录。
- 📚 **长短期记忆与档案管理 (RAG)**
  - 使用 `langchain-chroma` 本地向量数据库存储所有的聊天上下文，解决大模型上下文窗口限制。
  - 为每个重点联系人自动生成并动态维护一份详尽的 `Profile.md`（性格档案），包含互动频率、高频词汇、深夜互动分析等。
- 🔒 **隐私至上 (Privacy First)**
  - 所有聊天记录、知识库索引以及生成的联系人档案均严格保存在本地 data/、db/和crushes/目录中。
  - 项目配置了严格的 `.gitignore`，防止敏感信息泄露至云端。

---

## 🚀 快速开始

### 1. 环境准备

**1. 安装并配置 WeFlow（核心数据源）**
本项目依赖 WeFlow 实时获取本地微信聊天记录。请先完成以下准备工作：
- 前往 [WeFlow Releases](https://github.com/hicccc77/WeFlow/releases) 下载并安装适用于你操作系统的版本。
- 登录微信后打开 WeFlow 客户端，依次点击 **设置 → API 服务 → 启动服务**，启用本地 HTTP API。
- 默认服务地址为 `http://127.0.0.1:5031`，请确保服务已正常启动。

**2. 准备 Python 环境**
确保你已安装 Python 3.10 或更高版本。

```bash
# 克隆仓库
git clone https://github.com/kumoyatyou/emotionalAdvisor.git
cd emotionalAdvisor

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量
项目根目录提供了一个 `.env.example` 模板文件。
复制该文件并重命名为 `.env`，然后填入你的 API 密钥

`.env` 配置示例：
```env
# LLM 接口配置 (支持 OpenAI 格式，可配置国产大模型或本地模型)
OPENAI_API_KEY=sk-xxxxxx
OPENAI_API_BASE=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# WeFlow 微信同步接口配置 (本地默认端口)
WECHAT_SYNC_URL=http://127.0.0.1:5031/api/v1/push/messages
WECHAT_SYNC_TOKEN=your_weflow_token_here
```

### 3. 手动导入历史聊天记录（强烈建议）
为了防止首次启动时自动同步历史记录不完全，**强烈建议在首次运行前**，手动导入与目标联系人的历史聊天记录：
1. 使用 WeFlow 导出聊天记录，请务必选择 **JSON 格式**。
2. 将导出的文件放入 `data/raw/` 目录下。系统会在启动后自动解析并构建性格档案。

### 4. 启动 Agent
在终端中运行主程序：

```bash
python main.py
```

启动成功后，你将进入交互式控制台，并看到微信实时监听服务已在后台挂起。

---

## 💬 交互指令示例

在终端的 `User ❯` 提示符下，你可以使用自然语言下发指令：

**主动拉取与同步记录：**
> “更新一下我和 Alice 的聊天记录”  
> “从WeChat Realtime Sync拉取 Bob 的最新消息”

**情感分析与策略：**
> “分析一下 Alice 今天是什么情况，为什么回消息这么慢？”  
> “如果明天想约她出来看电影，有什么好的开场白建议？”

**思维模拟与决策：**
> “用 Naval 的视角建议我如何处理这段关系”  
> “提炼一下我在这段对话里的表现画像”

---

## 📂 目录结构说明

```text
emotionalAdvisor/
├── core/                   # 核心引擎层
│   ├── agent.py            # Agent 意图分发与调度中枢
│   ├── knowledge_base.py   # Chroma 向量知识库 (RAG) 封装
│   ├── wechat_sync.py      # WeFlow 微信本地接口与 SSE 监听
│   └── async_bus.py        # 异步事件总线
├── data/                   # 本地数据存储
│   └── raw/                # 存放手动导出的历史聊天记录
├── skills/                 # 技能插件层
│   ├── base.py             # Skill 抽象基类
│   ├── simp_skill.py       # 核心情感分析与回复生成技能
│   ├── nuwa_skill.py       # 角色思维模拟技能
│   └── bazi_skill.py       # 命理推演技能
├── user_profile/           # 用户的个人画像与档案
├── crushes/                # 目标联系人独立性格档案
├── db/                     # Chroma 向量数据库文件
├── main.py                 # 项目启动入口
└── requirements.txt        # Python 依赖清单
```

---

## 🎉 致谢与声明 (Acknowledgements)

本项目在开发过程中，深受开源社区的启发，并直接参考或集成了以下优秀的开源项目及理念，特此致谢。我们在使用和借鉴这些项目时，严格遵守了它们各自的开源许可协议：

- **[simp-skill](https://github.com/BeamusWayne/simp-skill)**: 提供了核心的情感分析逻辑，包括信号解读、情话生成、破冰策略与危机处理框架。
- **[nuwa-skill](https://github.com/alchaincyf/nuwa-skill)**: 提供了人物思维方式蒸馏和认知框架提取的设计思路，用于构建高阶认知视角的决策模拟。
- **[bazi-skill](https://github.com/jinchenma94/bazi-skill)**: 提供了四柱八字排盘与传统命理分析的实现参考。
- **[WeFlow](https://github.com/hicccc77/WeFlow)**: 提供了本地微信聊天记录获取与导出的技术基础，本项目原生适配了其 HTTP API 和实时消息推送能力。

*声明：以上引用项目的核心代码、设计思路及衍生功能均归原作者所有。本项目在借鉴和集成时均遵循原项目的开源许可要求。如涉及具体项目的源码复用或二次分发，请使用者同样遵守原项目的 License 规定。*

---

## 📜 许可证 (License)

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

> *P.S. 你可以自由地复制、修改和分发这些代码，甚至完全不需要在你的项目中保留我的署名。毕竟，把“感情小丑”的经历四处声张确实有些难为情。只要这个工具能帮你避开我曾踩过的坑，那就足够了。祝你在爱里得偿所愿。*
