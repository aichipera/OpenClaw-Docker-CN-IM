import json
from pathlib import Path
from openclaw_config.utils import load_config_with_compat
from openclaw_config.channels import validate_all_channels


def validate_config(config_file: str) -> bool:
    try:
        config = load_config_with_compat(config_file)
        errors = []

        if "agents" not in config:
            errors.append("缺少 agents 配置")

        if "model" in config:
            provider = config.get("model", {}).get("provider", {})
            if not provider.get("baseURL"):
                errors.append("缺少 model.provider.baseURL")

        channels = config.get("channels", {})
        errors.extend(validate_all_channels(channels))

        if errors:
            print("验证失败:")
            for e in errors:
                print(f"  - {e}")
            return False

        print("配置验证通过")
        return True

    except Exception as e:
        print(f"验证失败: {e}")
        return False