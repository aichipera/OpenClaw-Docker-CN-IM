import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def load_config(config_file: str) -> dict:
    """加载配置文件"""
    with open(config_file, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)
        raw = re.sub(r'(^|\s)//.*?$', '', raw, flags=re.M)
        raw = re.sub(r'(^|\s)#.*?$', '', raw, flags=re.M)
        raw = re.sub(r',(?=\s*[}\]])', '', raw)
        return json.loads(raw)


def save_config(config_file: str, config: dict) -> None:
    """保存配置文件"""
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sync_config(config_file: str, dry_run: bool = False) -> None:
    """根据环境变量同步配置"""
    config = load_config(config_file)

    env_mappings = {
        "MODEL_ID": ("agents", "defaults", "model", "model"),
        "PRIMARY_MODEL": ("agents", "defaults", "model", "primary"),
        "BASE_URL": ("model", "provider", "baseURL"),
        "API_KEY": ("model", "provider", "apiKey"),
        "API_PROTOCOL": ("model", "provider", "protocol"),
    }

    modified = False
    for env_key, path in env_mappings.items():
        value = os.environ.get(env_key)
        if value:
            target = config
            for key in path[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            if target.get(path[-1]) != value:
                target[path[-1]] = value
                modified = True
                print(f"更新: {env_key} = {value}")

    if modified:
        if dry_run:
            print("[DRY-RUN] 配置文件不会实际修改")
        else:
            save_config(config_file, config)
            print(f"配置已同步到: {config_file}")
    else:
        print("配置无需同步")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: sync.py <config-file> [--dry-run]")
        sys.exit(1)

    config_file = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    sync_config(config_file, dry_run=dry_run)