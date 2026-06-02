# agnes-ai

WorkBuddy 技能 — 封装 Agnes AI 的图像与视频生成能力，OpenAI 兼容协议。

## 功能

- **文生图**：通过自然语言描述生成图片，模型 `agnes-image-2.0-flash`
- **文生视频**：通过自然语言描述生成视频，模型 `agnes-video-2.0`（异步生成，自动轮询等待结果）

## 安装

### 方式一：通过 zip 包安装

将 `agnes-ai.zip` 解压到 WorkBuddy skills 目录：

```bash
unzip -o agnes-ai.zip -d ~/.workbuddy/skills/
```

### 方式二：手动放置

确保以下文件结构存在于 `~/.workbuddy/skills/agnes-ai/`：

```
agnes-ai/
├── SKILL.md
├── README.md
├── scripts/
│   └── generate.py
└── references/
    └── api.md
```

## 配置 API Key

### 方法 1：环境变量（推荐）

```bash
export AGNES_API_KEY="你的API密钥"
```

### 方法 2：配置文件

将 Key 写入本地文件：

```bash
echo "你的API密钥" > ~/.workbuddy/skills/agnes-ai/.api_key
```

> 优先级：环境变量 > 配置文件

## 使用方式

### 在 WorkBuddy 对话中使用

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

## 文件说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | WorkBuddy 技能定义，包含触发条件与调用流程 |
| `scripts/generate.py` | 命令行工具，封装图片与视频生成的 HTTP 调用 |
| `references/api.md` | Agnes AI API 端点、参数、响应格式参考 |
| `README.md` | 本文件 |

## API 地址

```
https://apihub.agnes-ai.com/v1
```

## 安全

- 本技能仅向 Agnes AI 官方 API 地址发起请求
- API Key 仅存储于本地，不会上传至任何第三方
- 零外部依赖，代码完全透明
