# Agnes AI API Reference

## Base URL

```
https://apihub.agnes-ai.com/v1
```

## Authentication

All requests require an `Authorization: Bearer <api_key>` header.

## Models

| Model ID | Type | Description |
|---|---|---|
| `agnes-image-2.0-flash` | Image | Fast image generation model |
| `agnes-video-2.0` | Video | Video generation model |

## Endpoints

### Image Generation

```
POST /v1/images/generations
```

**Request Body:**

```json
{
  "model": "agnes-image-2.0-flash",
  "prompt": "A serene mountain landscape at sunset",
  "n": 1,
  "size": "1024x1024"
}
```

**Response:**

```json
{
  "data": [
    {
      "url": "https://cdn.agnes-ai.com/output/abc123.png",
      "b64_json": null
    }
  ]
}
```

### Video Generation (Create)

```
POST /v1/video/generations
```

**Request Body:**

```json
{
  "model": "agnes-video-2.0",
  "prompt": "A drone flying over a city skyline",
  "duration": 5
}
```

**Response:**

```json
{
  "id": "task_abc123",
  "status": "processing"
}
```

### Video Generation (Poll)

```
GET /v1/video/generations/{task_id}
```

**Response (completed):**

```json
{
  "id": "task_abc123",
  "status": "completed",
  "url": "https://cdn.agnes-ai.com/output/abc123.mp4"
}
```

**Response (processing):**

```json
{
  "id": "task_abc123",
  "status": "processing"
}
```

**Response (failed):**

```json
{
  "id": "task_abc123",
  "status": "failed",
  "error": "Generation failed: content policy violation"
}
```
