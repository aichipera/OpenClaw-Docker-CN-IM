#!/usr/bin/env python3
"""
OpenClaw 配置管理 CLI 入口

用法:
    python -m openclaw_config sync --config-file <path>
    python -m openclaw_config validate --config-file <path>
    python -m openclaw_config migrate --config-file <path>
"""

import argparse
import sys
from pathlib import Path

from openclaw_config.sync_engine import sync
from openclaw_config.validators import validate_config


def main():
    parser = argparse.ArgumentParser(
        prog="openclaw-config",
        description="OpenClaw 配置管理工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    sync_parser = subparsers.add_parser("sync", help="同步配置")
    sync_parser.add_argument(
        "--config-file",
        required=True,
        help="配置文件路径"
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览不实际修改"
    )

    validate_parser = subparsers.add_parser("validate", help="验证配置")
    validate_parser.add_argument(
        "--config-file",
        required=True,
        help="配置文件路径"
    )

    migrate_parser = subparsers.add_parser("migrate", help="迁移配置")
    migrate_parser.add_argument(
        "--config-file",
        required=True,
        help="配置文件路径"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config_path = Path(args.config_file)
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        return 1

    if args.command == "sync":
        import os
        os.environ['CONFIG_FILE'] = str(config_path)
        sync()
    elif args.command == "validate":
        validate_config(str(config_path))
    elif args.command == "migrate":
        print("迁移功能开发中...")

    return 0


if __name__ == "__main__":
    sys.exit(main())