# agnes-ai

AI Agent 技能 — 封装 Agnes AI 的图像与视频生成能力，OpenAI 兼容协议。
适用于任何支持 Skill 机制的 AI Agent 平台（WorkBuddy、OpenClaw、Hermes 等）。

> 具体可看：https://mp.weixin.qq.com/s/YKNlgJfTfNlPGGrzRFoEUA

## 功能

- **文生图**：通过自然语言描述生成图片，模型 `agnes-image-2.0-flash`
- **文生视频**：通过自然语言描述生成视频，模型 `agnes-video-2.0`（异步生成，自动轮询等待结果）

## 安装

### 手动安装
1、将本目录放置到你的 AI Agent 的 skills 目录下（各平台路径不同）：

```
agnes-ai/
├── SKILL.md              # 技能定义（触发条件、调用流程）
├── README.md             # 本文件
├── scripts/
│   └── generate.py       # 命令行工具（纯标准库，零依赖）
└── references/
    └── api.md            # API 端点参考文档
```

**各平台安装路径**

| 平台 | 技能目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/` |
| OpenClaw / Hermes | 按其约定的 skills 目录 |
| 通用 | 克隆到任意目录，确保 AI Agent 能访问 `scripts/generate.py` |

### 自动安装
给Agent发Prompt：
```bash
安装skill：https://github.com/songxf1024/skills/tree/main/agnes-ai
```

## 配置 API Key

> 先登录 https://apihub.agnes-ai.com 获取 API Key

### 手动配置
**方法 1：环境变量（推荐）**

```bash
export AGNES_API_KEY="你的API密钥"
```

**方法 2：配置文件**

将 Key 写入本地文件：

```bash
mkdir -p ~/.agnes-ai
echo "你的API密钥" > ~/.agnes-ai/api_key
```

> 优先级：环境变量 > `~/.agnes-ai/api_key` > `scripts/api_key`（脚本同级目录）

### 自动配置

给Agent发Prompt：
```bash
agnes key是sk-GqbtQSGGxxxx
```


## 使用方式

### 在 AI Agent 对话中使用

安装后直接在对话中下达指令，技能会自动触发：

| 你说的 | 发生的事情 |
|---|---|
| "用 Agnes 生成一张日落海景图" | → 调用 `agnes-image-2.0-flash` |
| "用 Agnes 做一个 5 秒的星空延时视频" | → 调用 `agnes-video-2.0` |

### 命令行直接调用

```bash
# 生成图片
python3 scripts/generate.py image \
  --prompt "A serene mountain landscape at sunset" \
  --size 1024x1024 \
  --output sunset.png

# 生成视频
python3 scripts/generate.py video \
  --prompt "A drone flying over a city skyline" \
  --duration 5 \
  --output skyline.mp4
```

### 图片尺寸

| 尺寸 | 方向 |
|---|---|
| `1024x1024` | 正方形（默认） |
| `1792x1024` | 横版 |
| `1024x1792` | 竖版 |

## 依赖

- Python 3.8+（纯标准库，零外部依赖）
- 有效的 Agnes AI API Key

## API 地址

```
https://apihub.agnes-ai.com/v1
```

## 安全

- 仅向 Agnes AI 官方 API 地址（`apihub.agnes-ai.com`）发起请求
- API Key 仅存储于本地，不会上传至任何第三方
- 零外部依赖，代码完全透明
