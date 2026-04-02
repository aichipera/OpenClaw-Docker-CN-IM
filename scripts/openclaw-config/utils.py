import re
import json
from typing import Any, Optional


def strip_json_comments_and_trailing_commas(raw: str) -> str:
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)
    raw = re.sub(r'(^|\s)//.*?$', '', raw, flags=re.M)
    raw = re.sub(r'(^|\s)#.*?$', '', raw, flags=re.M)
    raw = re.sub(r',(?=\s*[}\]])', '', raw)
    return raw


def load_config_with_compat(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as original_error:
        sanitized = strip_json_comments_and_trailing_commas(raw)
        try:
            config = json.loads(sanitized)
            print('⚠️ 检测到 openclaw.json 含注释或尾随逗号，已按兼容模式自动解析并在保存时标准化为合法 JSON')
            return config
        except json.JSONDecodeError:
            raise ValueError(f'openclaw.json 格式非法: {original_error}')


def ensure_path(cfg: dict, keys: list) -> dict:
    curr = cfg
    for key in keys:
        if key not in curr or not isinstance(curr.get(key), dict):
            curr[key] = {}
        curr = curr[key]
    return curr


def deep_merge(dst: dict, src: dict) -> dict:
    if not isinstance(dst, dict) or not isinstance(src, dict):
        return src
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            dst[key] = deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def parse_csv(value: Optional[str]) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(',') if item.strip()]


def parse_json_object(raw: Optional[str], env_name: str) -> Optional[dict]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception as ex:
        raise ValueError(f'{env_name} 不是合法 JSON: {ex}')
    if not isinstance(parsed, dict):
        raise ValueError(f'{env_name} 必须是 JSON 对象')
    return parsed


def utc_now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def first_csv_item(raw: Optional[str], default: str = '') -> str:
    values = parse_csv(raw)
    return values[0] if values else default


def normalize_model_ref(raw: str, provider_names: Optional[set] = None, default_provider: str = 'default') -> str:
    val = str(raw or '').strip()
    if not val:
        return ''

    provider_names = set(provider_names or [])
    provider_names.add(default_provider)

    if '/' not in val:
        return f'{default_provider}/{val}'

    provider_prefix = val.split('/', 1)[0].strip()
    if provider_prefix in provider_names:
        return val

    return f'{default_provider}/{val}'


def resolve_primary_model(env: dict, default_model_id: str, provider_names: Optional[set] = None) -> str:
    raw = str(env.get('PRIMARY_MODEL') or '').strip()
    if raw:
        return normalize_model_ref(raw, provider_names=provider_names)
    return normalize_model_ref(default_model_id, provider_names=provider_names)


def resolve_image_model(env: dict, default_model_id: str, provider_names: Optional[set] = None) -> str:
    raw = str(env.get('IMAGE_MODEL_ID') or '').strip()
    if raw:
        return normalize_model_ref(raw, provider_names=provider_names)
    return normalize_model_ref(default_model_id, provider_names=provider_names)


def collect_extra_model_providers(env: dict, start: int = 2, end: int = 6) -> list:
    providers = []
    for index in range(start, end + 1):
        prefix = f'MODEL{index}'
        raw_name = str(env.get(f'{prefix}_NAME') or '').strip()
        provider_name = raw_name or f'model{index}'
        model_ids = str(env.get(f'{prefix}_MODEL_ID') or '').strip()
        base_url = str(env.get(f'{prefix}_BASE_URL') or '').strip()
        api_key = str(env.get(f'{prefix}_API_KEY') or '').strip()
        protocol = str(env.get(f'{prefix}_PROTOCOL') or '').strip()
        context_window = str(env.get(f'{prefix}_CONTEXT_WINDOW') or '').strip()
        max_tokens = str(env.get(f'{prefix}_MAX_TOKENS') or '').strip()

        has_any = any([raw_name, model_ids, base_url, api_key, protocol, context_window, max_tokens])
        if not has_any:
            continue

        providers.append({
            'index': index,
            'provider_name': provider_name,
            'model_ids': model_ids,
            'base_url': base_url,
            'api_key': api_key,
            'protocol': protocol,
            'context_window': context_window,
            'max_tokens': max_tokens,
        })
    return providers