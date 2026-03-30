#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理脚本
保存和读取用户的搜索配置（关键词、数量、排序、定时设置）

说明：
- 默认使用中国时区 Asia/Shanghai
- “取消定时任务”不会删除全部配置，只会禁用 schedule
- 如需彻底删除配置，可使用 --clear-config
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_MAX_RESULTS = 20
DEFAULT_SORT = "date"
# CRON_FIELD_PATTERN = re.compile(r"^[\w\-*/,?LW#]+$")
CRON_FIELD_SPECS = [
    ("分钟", 0, 59),
    ("小时", 0, 23),
    ("日", 1, 31),
    ("月", 1, 12),
    ("星期", 0, 7),
]

def resolve_config_dir() -> str:
    """解析配置目录，优先环境变量，其次推断技能目录，最后回退到标准路径。"""
    # 允许通过环境变量覆盖，方便测试或部署
    env_root = os.environ.get("OPENCLAW_SKILL_ROOT")
    if env_root:
        return os.path.abspath(os.path.expanduser(env_root))
    
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    parent_dir = os.path.dirname(current_dir)

    # 常规放置方式：.../arxiv-paper-searcher/scripts/config_manager.py
    if os.path.basename(current_dir) == "scripts":
        return parent_dir

    # 默认回退到 skill.md 中约定的标准目录
    return os.path.expanduser("~/.openclaw/workspace/skills/arxiv-paper-searcher")


CONFIG_DIR = resolve_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def now_iso() -> str:
    return datetime.now(CHINA_TZ).isoformat(timespec="seconds")


def validate_positive_int(value: str) -> int:
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("论文数量必须是整数") from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("论文数量必须大于 0")
    return ivalue

def _validate_cron_value(token: str, min_value: int, max_value: int, field_name: str) -> None:
    if not token.isdigit(): raise argparse.ArgumentTypeError(f"{field_name}字段包含非法值：{token}")
    value = int(token)
    if value < min_value or value > max_value:
        raise argparse.ArgumentTypeError(f"{field_name}字段超出范围：{value}，允许范围 {min_value}-{max_value}")

def _validate_cron_item(item: str, min_value: int, max_value: int, field_name: str) -> None:
    if not item: raise argparse.ArgumentTypeError(f"{field_name}字段不能为空项")
    if "/" in item:
        base, step = item.split("/", 1)
        if not step.isdigit() or int(step) <= 0: raise argparse.ArgumentTypeError(f"{field_name}字段步长非法：{item}")
        if base == "*": return
        if "-" in base:
            start, end = base.split("-", 1)
            _validate_cron_value(start, min_value, max_value, field_name)
            _validate_cron_value(end, min_value, max_value, field_name)
            if int(start) > int(end): raise argparse.ArgumentTypeError(f"{field_name}字段范围非法：{item}")
            return
        _validate_cron_value(base, min_value, max_value, field_name)
        return
    if item == "*": return
    if "-" in item:
        start, end = item.split("-", 1)
        _validate_cron_value(start, min_value, max_value, field_name)
        _validate_cron_value(end, min_value, max_value, field_name)
        if int(start) > int(end): raise argparse.ArgumentTypeError(f"{field_name}字段范围非法：{item}")
        return
    _validate_cron_value(item, min_value, max_value, field_name)


def validate_cron(expr: str) -> str:
    """
    做基础 cron 校验。
    这里按 5 段 cron 处理，适合常见分钟 小时 日 月 星期表达式。
    """
    parts = expr.strip().split()
    if len(parts) != 5: raise argparse.ArgumentTypeError("cron 表达式必须是 5 段，例如：0 9 * * *")
    for part, (field_name, min_value, max_value) in zip(parts, CRON_FIELD_SPECS):
        items = part.split(",")
        for item in items: _validate_cron_item(item, min_value, max_value, field_name)
    return expr


def normalize_schedule(schedule: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not schedule:
        return {"enabled": False, "timezone": "Asia/Shanghai"}

    return {
        "enabled": bool(schedule.get("enabled", False)),
        "cron": schedule.get("cron"),
        "timezone": schedule.get("timezone") or "Asia/Shanghai",
    }


def load_config() -> Optional[Dict[str, Any]]:
    """读取配置文件。"""
    if not os.path.exists(CONFIG_FILE):
        return None

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("keyword", None)
    data.setdefault("max_results", DEFAULT_MAX_RESULTS)
    data.setdefault("sort", DEFAULT_SORT)
    data["schedule"] = normalize_schedule(data.get("schedule"))
    data.setdefault("updated_at", None)
    return data


def write_config(config: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config["updated_at"] = now_iso()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"配置已保存：{CONFIG_FILE}")
    return config


def save_config(
    keyword: Optional[str] = None,
    max_results: Optional[int] = None,
    sort: Optional[str] = None,
    schedule: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """保存或更新用户配置。"""
    current = load_config() or {}

    config = {
        "keyword": keyword if keyword is not None else current.get("keyword"),
        "max_results": max_results if max_results is not None else current.get("max_results", DEFAULT_MAX_RESULTS),
        "sort": sort if sort is not None else current.get("sort", DEFAULT_SORT),
        "schedule": normalize_schedule(schedule if schedule is not None else current.get("schedule")),
    }

    return write_config(config)


def disable_schedule() -> Dict[str, Any]:
    """禁用定时任务，但保留关键词、数量、排序等配置。"""
    current = load_config() or {
        "keyword": None,
        "max_results": DEFAULT_MAX_RESULTS,
        "sort": DEFAULT_SORT,
        "schedule": {"enabled": False, "timezone": "Asia/Shanghai"},
    }

    current["schedule"] = {
        "enabled": False,
        "cron": None,
        "timezone": "Asia/Shanghai",
    }
    return write_config(current)


def clear_config() -> bool:
    """彻底删除配置文件。"""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        print("配置文件已删除")
        return True
    return False


def print_config(config: Dict[str, Any]) -> None:
    print("当前配置:")
    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()
    print(f"关键词：{config.get('keyword')}")
    print(f"数量：{config.get('max_results')}")
    print(f"排序：{config.get('sort')}")
    if config.get("schedule", {}).get("enabled"):
        print(f"定时：{config['schedule'].get('cron')}")
        print(f"时区：{config['schedule'].get('timezone')}")
    else:
        print("定时：未启用")
        print(f"时区：{config.get('schedule', {}).get('timezone', 'Asia/Shanghai')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="配置管理工具")
    parser.add_argument("--save", action="store_true", help="保存或更新配置")
    parser.add_argument("--show", action="store_true", help="显示当前配置")
    parser.add_argument("--delete", action="store_true", help="禁用定时任务，但保留其他配置")
    parser.add_argument("--clear-config", action="store_true", help="彻底删除配置文件")
    parser.add_argument("--keyword", "-k", type=str, help="搜索关键词")
    parser.add_argument("--max", "-m", type=validate_positive_int, help="论文数量")
    parser.add_argument("--sort", choices=["date", "relevance"], help="排序方式")
    parser.add_argument("--schedule", type=validate_cron, help="定时表达式（5 段 cron）")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.show:
        config = load_config()
        if config:
            print_config(config)
        else:
            print("暂无配置")
        return 0

    if args.clear_config:
        if clear_config():
            print("✓ 配置已彻底删除")
        else:
            print("✗ 配置文件不存在")
        return 0

    if args.delete:
        config = disable_schedule()
        print("✓ 已取消定时任务，其他配置已保留")
        print_config(config)
        return 0

    if args.save:
        existing = load_config()
        if not existing and args.keyword is None:
            parser.error("首次保存配置时必须提供 --keyword")

        schedule = None
        if args.schedule:
            schedule = {
                "enabled": True,
                "cron": args.schedule,
                "timezone": "Asia/Shanghai",
            }
        elif args.schedule is None and existing is not None:
            schedule = existing.get("schedule")

        config = save_config(
            keyword=args.keyword,
            max_results=args.max,
            sort=args.sort,
            schedule=schedule,
        )
        print()
        print("✓ 配置已更新")
        print_config(config)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
