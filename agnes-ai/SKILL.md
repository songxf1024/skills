---
name: agnes-ai
description: Wraps the Agnes AI API for image and video generation. Use when the user asks to generate images, pictures, photos, or videos with Agnes AI. Two models: agnes-image-2.0-flash for images, agnes-video-2.0 for video. OpenAI-compatible protocol. Requires an API key provided on first use.
agent_created: true
---

# Agnes AI — Image & Video Generation

## Overview

Agnes AI provides image and video generation models accessible through an OpenAI-compatible HTTP API.
Use this skill whenever the user wants to generate images or videos with Agnes AI.

- **API Base URL**: `https://apihub.agnes-ai.com/v1`
- **Auth**: Bearer token (`AGNES_API_KEY`)
- **Protocol**: OpenAI-compatible request/response format

## Model Selection

| User Intent | Model | Endpoint |
|---|---|---|
| Generate images, pictures, photos, illustrations | `agnes-image-2.0-flash` | `POST /v1/images/generations` |
| Generate videos, clips, animations | `agnes-video-2.0` | `POST /v1/video/generations` |

## API Key Setup

On first use the skill requires an API key. Check these locations in order:

1. Environment variable `AGNES_API_KEY`
2. File `~/.workbuddy/skills/agnes-ai/.api_key`

If neither is found, ask the user: **"请提供你的 Agnes AI API Key，我会安全存储它。"**

Save the key the user provides by writing it to `~/.workbuddy/skills/agnes-ai/.api_key` (plain text, no trailing newline).
Then set the environment variable for the current session:

```bash
export AGNES_API_KEY=$(cat ~/.workbuddy/skills/agnes-ai/.api_key)
```

Never echo or log the API key value in any user-visible output.

## Image Generation

Trigger: user asks to generate / create / make an image, picture, photo, illustration, poster, or visual with Agnes.

### Call the API

Use the bundled script for reliable execution:

```bash
/Users/songxf/.workbuddy/binaries/python/envs/default/bin/python \
  /Users/songxf/.workbuddy/skills/agnes-ai/scripts/generate.py \
  image \
  --prompt "<prompt>" \
  --size "<size>" \
  --output "<output_path>"
```

Or call the API directly with curl:

```bash
curl -s -X POST "https://apihub.agnes-ai.com/v1/images/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-image-2.0-flash",
    "prompt": "<prompt>",
    "n": 1,
    "size": "<size>"
  }'
```

### Parameters

| Parameter | Description | Default |
|---|---|---|
| `prompt` | Text description of the desired image (required) | — |
| `size` | Image dimensions. Supported: `1024x1024`, `1792x1024`, `1024x1792` | `1024x1024` |
| `n` | Number of images to generate | `1` |

### Response Handling

The API returns an OpenAI-compatible response:

```json
{
  "data": [
    {
      "url": "https://...",
      "b64_json": "..."
    }
  ]
}
```

The `url` field contains a temporary download link. Download the image with `curl` or `wget` and save locally.
If `b64_json` is present, decode it with `base64 -d` to get the raw image bytes.

After saving the image file, deliver it to the user with `deliver_attachments`.

## Video Generation

Trigger: user asks to generate / create / make a video, clip, animation, or motion content with Agnes.

### Call the API

Use the bundled script:

```bash
/Users/songxf/.workbuddy/binaries/python/envs/default/bin/python \
  /Users/songxf/.workbuddy/skills/agnes-ai/scripts/generate.py \
  video \
  --prompt "<prompt>" \
  --duration <seconds> \
  --output "<output_path>"
```

Or call the API directly with curl:

```bash
curl -s -X POST "https://apihub.agnes-ai.com/v1/video/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-video-2.0",
    "prompt": "<prompt>",
    "duration": <seconds>
  }'
```

### Parameters

| Parameter | Description | Default |
|---|---|---|
| `prompt` | Text description of the desired video (required) | — |
| `duration` | Video duration in seconds | `5` |

### Response Handling

Video generation is asynchronous. The API returns a task ID:

```json
{
  "id": "task_abc123",
  "status": "processing"
}
```

Poll for completion:

```bash
curl -s "https://apihub.agnes-ai.com/v1/video/generations/<task_id>" \
  -H "Authorization: Bearer $AGNES_API_KEY"
```

When `status` becomes `completed`, the response contains a `url` or `output` field with the video download link.
Download it and deliver to the user with `deliver_attachments`.

The bundled `scripts/generate.py` script handles polling automatically — prefer using it over raw curl.

## Supported Image Sizes

- `1024x1024` — square (default)
- `1792x1024` — landscape
- `1024x1792` — portrait

## Error Handling

If the API returns a non-200 status:

1. Check that the API key is valid and has not expired
2. Verify the prompt is not empty and does not violate content policy
3. If the error persists, tell the user the error message and suggest checking their Agnes AI dashboard

## After Generation

After successfully generating and saving an image or video file:

1. Use `deliver_attachments` to send the file to the user
2. For images, optionally display a preview using `preview_url`
3. For videos, use `open_result_view` or `preview_url` to let the user view it
