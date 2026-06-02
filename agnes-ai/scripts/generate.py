#!/usr/bin/env python3
"""Agnes AI — Image and Video Generation CLI.

Usage:
  python generate.py image --prompt "..." [--size 1024x1024] --output path.png
  python generate.py video --prompt "..." [--duration 5] --output path.mp4
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://apihub.agnes-ai.com/v1"


def get_api_key():
    """Retrieve API key from environment or config file."""
    key = os.environ.get("AGNES_API_KEY")
    if key:
        return key
    key_file = os.path.expanduser("~/.workbuddy/skills/agnes-ai/.api_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    print("ERROR: AGNES_API_KEY not set.", file=sys.stderr)
    print("Set the environment variable or write it to ~/.workbuddy/skills/agnes-ai/.api_key", file=sys.stderr)
    sys.exit(1)


def api_request(method, endpoint, body=None):
    """Make an authenticated request to the Agnes AI API."""
    url = f"{API_BASE}{endpoint}"
    api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"API Error ({e.code}): {err_body}", file=sys.stderr)
        sys.exit(1)


def download_file(url, output_path):
    """Download a file from URL to local path."""
    print(f"Downloading to {output_path} ...")
    urllib.request.urlretrieve(url, output_path)
    print(f"Saved: {output_path}")


def generate_image(prompt, size, output_path):
    """Generate an image using agnes-image-2.0-flash."""
    print(f"Generating image: {prompt[:80]}...")
    resp = api_request("POST", "/images/generations", {
        "model": "agnes-image-2.0-flash",
        "prompt": prompt,
        "n": 1,
        "size": size,
    })

    data = resp.get("data", [])
    if not data:
        print("ERROR: No image data in response", file=sys.stderr)
        sys.exit(1)

    item = data[0]

    # Prefer b64_json over URL
    if item.get("b64_json"):
        print("Decoding base64 image data...")
        img_bytes = base64.b64decode(item["b64_json"])
        with open(output_path, "wb") as f:
            f.write(img_bytes)
        print(f"Saved: {output_path}")
        return output_path

    if item.get("url"):
        download_file(item["url"], output_path)
        return output_path

    print("ERROR: No url or b64_json in image response", file=sys.stderr)
    sys.exit(1)


def generate_video(prompt, duration, output_path):
    """Generate a video using agnes-video-2.0 with polling."""
    print(f"Generating video ({duration}s): {prompt[:80]}...")

    # Create generation task
    resp = api_request("POST", "/video/generations", {
        "model": "agnes-video-2.0",
        "prompt": prompt,
        "duration": duration,
    })

    task_id = resp.get("id")
    if not task_id:
        print("ERROR: No task ID in response", file=sys.stderr)
        sys.exit(1)

    print(f"Task ID: {task_id}")

    # Poll for completion
    max_attempts = 120  # ~10 minutes at 5s intervals
    for attempt in range(max_attempts):
        time.sleep(5)
        status_resp = api_request("GET", f"/video/generations/{task_id}")
        status = status_resp.get("status", "unknown")
        print(f"  [{attempt + 1}] Status: {status}")

        if status == "completed":
            url = status_resp.get("url") or status_resp.get("output")
            if url:
                download_file(url, output_path)
                return output_path
            else:
                print("ERROR: Completed but no video URL", file=sys.stderr)
                sys.exit(1)

        if status == "failed":
            err = status_resp.get("error", "Unknown error")
            print(f"ERROR: Generation failed: {err}", file=sys.stderr)
            sys.exit(1)

    print("ERROR: Timed out waiting for video generation", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Agnes AI Generator")
    sub = parser.add_subparsers(dest="command", required=True)

    # Image subcommand
    img = sub.add_parser("image", help="Generate an image")
    img.add_argument("--prompt", required=True, help="Image description")
    img.add_argument("--size", default="1024x1024", help="Image size (default: 1024x1024)")
    img.add_argument("--output", required=True, help="Output file path")

    # Video subcommand
    vid = sub.add_parser("video", help="Generate a video")
    vid.add_argument("--prompt", required=True, help="Video description")
    vid.add_argument("--duration", type=int, default=5, help="Duration in seconds (default: 5)")
    vid.add_argument("--output", required=True, help="Output file path")

    args = parser.parse_args()

    if args.command == "image":
        generate_image(args.prompt, args.size, args.output)
    elif args.command == "video":
        generate_video(args.prompt, args.duration, args.output)

    print("Done.")


if __name__ == "__main__":
    main()
