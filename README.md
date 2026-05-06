# 🧠 AI 情感军师 Agent

一个本地优先的多技能情感分析 Agent。

它把微信聊天记录、RAG 知识库、联系人档案、思维模拟和八字分析整合到同一个项目里，既支持命令行交互，也支持本地浏览器 GUI。项目启动后可以自动监听 WeFlow 的实时消息推送，也可以手动导入历史聊天 JSON 进行增量建档和分析。

## 📖 写在前面

在这个世界里，我似乎总是扮演着“旁观者清”的军师角色——每当朋友带着感情的伤痕来找我，我总能冷静地为他们剖析利弊、指点迷津。可一旦成为故事里的主角，我就成了那个最笨拙、最无可救药的小丑，在自己的感情里一败涂地，医者始终无法自医。

无数个复盘失败经历的深夜里，我萌生了做这个 Agent 的念头。我将 GitHub 上众多优秀的开源思维模型与分析技能汇聚于此，试图用算法的理智，去填补我们在爱情中容易盲目和冲动的缺陷。

我敲下这些代码，不仅仅是为了打造一个工具，更是为了传递一份微光的祝愿：希望它能为你提供最清醒的视角和最妥帖的建议。愿你在爱里能拥有智慧与底气，去拥抱真正对的人，永远不必像我一样，成为那个在回忆里独自苦笑的“小丑”。

## 🌟 项目现状

当前仓库已经包含这些核心能力：

- 🧠 **多技能调度**：自动把自然语言请求分发给 `SimpSkill`、`NuwaSkill`、`BaziSkill` 或多技能组合流程。
- 🖥️ **本地 GUI**：运行 `launcher.py` 或 `gui_main.py` 后，会启动本地 FastAPI 服务，并自动打开浏览器界面。
- ⌨️ **命令行模式**：运行 `main.py` 后进入交互式控制台。
- 🔄 **WeFlow 集成**：支持监听 `GET /api/v1/push/messages` 的 SSE 实时推送，也支持主动调用 `/api/v1/messages` 拉取增量消息。
- 📁 **联系人档案系统**：自动为联系人创建 `profile.md`、`meta.json`、策略记录和媒体记忆目录。
- 🎭 **本人画像提炼**：可从已沉淀的联系人档案中反向总结出你的全局沟通画像。
- 📚 **本地向量知识库**：使用 Chroma 持久化聊天上下文，支持后续问答和策略生成。

## 🧩 核心模块

### 1. 💘 `SimpSkill`

负责情感分析和策略建议，适合：

- 分析某个联系人最近的态度
- 生成回复建议、破冰话术、推进策略
- 根据历史聊天、照片 EXIF、社交媒体文本更新联系人档案
- 自动维护 `crushes/<联系人>/profile.md`

### 2. 🧠 `NuwaSkill`

负责思维模拟和认知视角切换，当前会从 `skills/nuwa-skill/examples/` 自动加载预置人格。

仓库里目前已有 15 个示例人格/视角，包括：

- `naval`
- `elon-musk`
- `feynman`
- `steve-jobs`
- `paul-graham`
- `andrej-karpathy`
- `taleb`
- `munger`
- `trump`
- `zhang-yiming`
- `zhangxuefeng`
- `ilya-sutskever`
- `mrbeast`
- `sun-yuchen`
- `x-mastery-mentor`

另外它还支持通过 `/nuwa extract_user` 从已有联系人档案中提炼你的本人画像，输出到 `user_profile/profile.md`。

### 3. ☯️ `BaziSkill`

负责八字信息提取、排盘和命理分析，支持：

- 逐步补全姓名、性别、生日、时辰、出生地
- 自动把提取出的信息沉淀到 `user_profile/meta.json` 或联系人 `meta.json`
- 使用 `lunar_python` 计算八字
- 与 `SimpSkill` 联动，形成“聊天分析 + 命理分析”的综合建议

### 4. 🔗 `WechatSync`

负责接入 WeFlow 本地接口：

- 后台监听实时 SSE 推送
- 自动去重消息
- 将新增消息保存到 `data/raw/realtime/`
- 把增量消息注入知识库
- 自动静默更新对应联系人档案

## 🚀 启动方式

### 方式一：推荐，启动 GUI + 首次配置向导

```bash
python launcher.py
```

适合第一次使用。

`launcher.py` 会：

- 检查并生成 `.env`
- 在首次启动时引导你补全完整配置
- 启动本地 GUI 服务
- 自动在浏览器打开 `http://127.0.0.1:8000`

### 方式二：直接启动本地 GUI

```bash
python gui_main.py
```

会启动 FastAPI 服务，并提供：

- `POST /api/chat`：聊天接口
- `GET /api/thoughts/stream`：SSE 思考过程流
- `GET /`：浏览器界面

前端界面支持：

- 聊天历史保存在浏览器 `localStorage`
- Markdown 渲染回复
- 通过 SSE 实时显示 Agent 当前“正在做什么”

### 方式三：命令行模式

```bash
python main.py
```

命令行模式会：

- 初始化 Agent 和全部技能
- 后台静默处理 `data/raw/` 中的历史 JSON
- 尝试启动 WeFlow 实时监听
- 进入 `User ❯` 交互式咨询模式

## 💻 环境要求

- Python `3.10+`
- 可用的 OpenAI 兼容大模型接口
- 可选：本地 WeFlow 服务，用于读取和推送微信消息

如果你要使用完整能力，建议在 Windows 环境下配合微信与 WeFlow 一起使用。

## 🛠️ 安装

### 1. 克隆项目

```bash
git clone https://github.com/kumoyatyou/emotionalAdvisor.git
cd emotionalAdvisor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

## ⚙️ 配置 `.env`

项目根目录提供了 `.env.example` 模板，也可以直接运行 `python launcher.py` 让程序交互式生成。

一个和当前代码匹配的配置示例如下：

```env
# ==========================================
# Core LLM Configuration
# ==========================================
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
MODEL_NAME=gpt-4o
TEMPERATURE=0.7

# ==========================================
# Skill-specific Models
# 留空则继承 MODEL_NAME
# ==========================================
SIMP_MODEL=
NUWA_MODEL=
BAZI_MODEL=

# ==========================================
# RAG & Storage
# ==========================================
EMBEDDING_MODEL=text-embedding-3-small
DB_PERSIST_PATH=./db

# ==========================================
# WeChat Sync
# ==========================================
WECHAT_SYNC_URL=http://127.0.0.1:5031/api/v1/push/messages
WECHAT_SYNC_TOKEN=your_weflow_token_here
```

### 📝 配置说明

- `OPENAI_API_KEY`：你的模型服务密钥
- `OPENAI_API_BASE`：OpenAI 兼容接口地址，也可以换成其他供应商或本地中转
- `MODEL_NAME`：默认主模型
- `TEMPERATURE`：默认温度
- `SIMP_MODEL` / `NUWA_MODEL` / `BAZI_MODEL`：按技能单独覆写模型
- `EMBEDDING_MODEL`：向量模型名称
- `DB_PERSIST_PATH`：Chroma 数据库存储路径
- `WECHAT_SYNC_URL`：WeFlow SSE 地址
- `WECHAT_SYNC_TOKEN`：WeFlow Token，不填时实时同步大概率不可用

## 🔗 WeFlow 接入

项目内已经附带一份 [HTTP-API.md](./HTTP-API.md) 作为 WeFlow 接口说明，当前接入逻辑依赖它的本地 HTTP API 和 SSE 推送能力。

### 基本步骤

1. 安装并启动 WeFlow。
2. 在 WeFlow 中开启 `API 服务`。
3. 如需实时监听，再开启 `主动推送`。
4. 记录 Token，填入 `.env` 中的 `WECHAT_SYNC_TOKEN`。
5. 默认基础地址通常是 `http://127.0.0.1:5031`。

### 降级行为

如果 WeFlow 没有启动、端口不通或 Token 配置错误，项目会在多次重试后自动降级为手动模式。你仍然可以把历史聊天记录放进 `data/raw/`，继续使用建档与分析功能。

## 📥 历史聊天导入

首次使用时，强烈建议先导入历史聊天记录，再进行问答。

### 推荐流程

1. 用 WeFlow 导出目标联系人的聊天记录，格式选择 JSON。
2. 把导出的文件放进 `data/raw/`。
3. 启动 `main.py` 或 `gui_main.py`。
4. 程序会自动增量处理新增 JSON，写入向量库并更新联系人档案。

### 实时同步文件位置

实时监听到的新消息会额外备份到：

```text
data/raw/realtime/
```

## 💡 使用示例

### 📝 建档与更新

- `帮我建一个李雷的档案`
- `更新一下王雪的记录`
- `分析一下小雅最近的态度`

### 📥 WeFlow 增量拉取

- `获取 xxx 的最新记录`
- `从 WeChat Realtime Sync 拉取 Alice 的最新消息`

### 💬 情感分析与策略

- `如果明天约她看电影，有什么建议？`
- `她这两天回得很慢，是在冷淡我吗？`
- `帮我写一个不油腻的回复`

### 🧠 思维模拟与本人画像

- `用 Naval 的视角建议我如何处理这段关系`
- `用马斯克的视角给我一个更直接的判断`
- `提炼一下我自己的画像`

### ☯️ 八字与综合判断

- `我的名字是张三，出生于 2001 年 x 月 x 日 x 时，帮我排一下八字`
- `结合我和 xxx 的八字，分析一下今天适不适合推进`

## 📂 数据存储

项目默认是本地优先设计，核心数据都保存在本机。

### 主要目录

```text
emotionalAdvisor/
├── core/                         # Agent 核心逻辑、知识库和 WeFlow 同步
├── gui/                          # 浏览器界面静态资源
├── skills/                       # 三大技能及外部技能资源
├── data/
│   └── raw/                      # 手动导入的原始聊天 JSON
├── crushes/                      # 每个联系人独立档案目录
├── user_profile/                 # 用户本人画像与八字信息
├── db/                           # Chroma 持久化向量库
├── main.py                       # 命令行入口
├── gui_main.py                   # 本地 GUI 服务入口
├── launcher.py                   # 首次配置 + GUI 启动入口
├── HTTP-API.md                   # WeFlow 接口说明
└── README.md
```

### 联系人目录结构

每个联系人通常会在 `crushes/<联系人_slug>/` 下生成：

- `profile.md`
- `strategy.md`
- `meta.json`
- `memories/chats/`
- `memories/social/`
- `memories/photos/`

## 🔄 工作流概览

当前代码里的大致流程是：

1. 初始化 Agent 和技能注册表。
2. 加载或创建本地 Chroma 知识库。
3. 扫描 `data/raw/` 中新增的 JSON 文件。
4. 从聊天记录中识别联系人并自动创建档案。
5. 将消息写入向量库。
6. 根据请求意图调度到 `SimpSkill`、`NuwaSkill`、`BaziSkill` 或多技能联合分析。
7. 如果启用了 WeFlow，则持续监听新消息并进行增量更新。

## ⚠️ 注意事项

- 当前仓库是本地工具型项目，真实效果高度依赖你提供的模型质量和聊天数据质量。
- `WECHAT_SYNC_TOKEN` 配置错误时，实时同步通常会返回 `401`。
- 实时同步逻辑当前默认跳过群聊消息，主要聚焦私聊联系人分析。
- 打包运行时，`launcher.py` 和 `gui_main.py` 会把数据目录切换到用户主目录下的 `.emotionalAdvisor/`。

## 🙏 致谢

本项目参考并整合了多个优秀开源项目的思路与资源：

- [simp-skill](https://github.com/BeamusWayne/simp-skill)
- [nuwa-skill](https://github.com/alchaincyf/nuwa-skill)
- [bazi-skill](https://github.com/jinchenma94/bazi-skill)
- [WeFlow](https://github.com/hicccc77/WeFlow)

相关开源资源的原始版权、设计和许可证归各自作者所有。若你在自己的项目中继续复用这些内容，请同时遵守对应项目的许可证要求。

## 📜 License

本项目采用 [MIT License](./LICENSE)。

> P.S. 你可以自由地复制、修改和分发这些代码，甚至完全不需要在你的项目中保留我的署名。 毕竟，把“感情小丑”的经历四处声张确实有些难为情。只要这个工具能帮你避开我曾踩过的坑，那就足够了。 祝你在爱里得偿所愿。

