import json
import os
import subprocess
import sys
from copy import deepcopy

from openclaw_config.utils import (
    load_config_with_compat, ensure_path, deep_merge,
    parse_bool, parse_csv, parse_json_object, utc_now_iso,
    first_csv_item, normalize_model_ref, resolve_primary_model,
    resolve_image_model, collect_extra_model_providers,
)
from openclaw_config.models import (
    CHANNEL_INSTALLS,
    is_valid_account_id,
    is_feishu_account_config, is_dingtalk_account_config,
    is_wecom_account_config, is_qqbot_account_config,
    get_feishu_accounts, get_dingtalk_accounts,
    get_wecom_accounts, get_qqbot_accounts,
    FEISHU_ACCOUNT_FIELDS, FEISHU_RESERVED_FIELDS,
    DINGTALK_ACCOUNT_FIELDS, DINGTALK_RESERVED_FIELDS,
    WECOM_ACCOUNT_FIELDS, WECOM_RESERVED_FIELDS,
    QQBOT_RESERVED_FIELDS,
)
from openclaw_config.channels import (
    normalize_feishu_config, normalize_dingtalk_config,
    normalize_wecom_config, normalize_qqbot_config,
    merge_feishu_accounts_from_env, merge_dingtalk_accounts_from_env,
    merge_wecom_accounts_from_env, merge_qqbot_bots_from_env,
    validate_feishu_multi_accounts, validate_dingtalk_multi_accounts,
    validate_wecom_multi_accounts, validate_qqbot_multi_accounts,
)


class SyncContext:
    def __init__(self, config, env):
        self.config = config
        self.env = env
        self.channels = ensure_path(config, ['channels'])
        self.plugins = ensure_path(config, ['plugins'])
        self.entries = ensure_path(self.plugins, ['entries'])
        self.installs = ensure_path(self.plugins, ['installs'])
        self.default_dm_policy = env.get('DM_POLICY') or 'open'
        self.default_allow_from = parse_csv(env.get('ALLOW_FROM')) or ['*']
        self.default_group_policy = env.get('GROUP_POLICY') or 'open'
        self.multi_account_channels = {'feishu', 'dingtalk', 'wecom', 'qqbot'}
        self.has_feishu_single_env = bool((env.get('FEISHU_APP_ID') or '').strip() and (env.get('FEISHU_APP_SECRET') or '').strip())
        self.has_feishu_accounts_env = bool((env.get('FEISHU_ACCOUNTS_JSON') or '').strip())
        self.has_feishu_any_env = self.has_feishu_single_env or self.has_feishu_accounts_env
        self.has_dingtalk_single_env = bool((env.get('DINGTALK_CLIENT_ID') or '').strip() and (env.get('DINGTALK_CLIENT_SECRET') or '').strip())
        self.has_dingtalk_accounts_env = bool((env.get('DINGTALK_ACCOUNTS_JSON') or '').strip())
        self.has_dingtalk_any_env = self.has_dingtalk_single_env or self.has_dingtalk_accounts_env
        self.has_wecom_single_env = bool((env.get('WECOM_BOT_ID') or '').strip() and (env.get('WECOM_SECRET') or '').strip())
        self.has_wecom_accounts_env = bool((env.get('WECOM_ACCOUNTS_JSON') or '').strip())
        self.has_wecom_any_env = self.has_wecom_single_env or self.has_wecom_accounts_env
        self.has_qqbot_single_env = bool((env.get('QQBOT_APP_ID') or '').strip() and (env.get('QQBOT_CLIENT_SECRET') or '').strip())
        self.has_qqbot_bots_env = bool((env.get('QQBOT_BOTS_JSON') or '').strip())
        self.has_qqbot_any_env = self.has_qqbot_single_env or self.has_qqbot_bots_env
        self.feishu_plugin_env = (env.get('FEISHU_OFFICIAL_PLUGIN_ENABLED') or '').strip().lower()
        self.feishu_plugin_enabled = self.feishu_plugin_env in ('1', 'true', 'yes', 'on')
        self.feishu_plugin_explicit = self.feishu_plugin_env in ('0', '1', 'false', 'true', 'no', 'yes', 'off', 'on')

    def channel(self, channel_id):
        return ensure_path(self.channels, [channel_id])

    def entry(self, channel_id):
        return ensure_path(self.entries, [channel_id])

    def install(self, channel_id):
        install_info = CHANNEL_INSTALLS.get(channel_id)
        if install_info and channel_id not in self.installs:
            payload = deepcopy(install_info)
            payload['installedAt'] = utc_now_iso()
            self.installs[channel_id] = payload

    def enable_channel(self, channel_id, install=False):
        self.entries[channel_id] = {'enabled': True}
        if install:
            self.install(channel_id)

    def disable_channel(self, channel_id):
        self.entries[channel_id] = {'enabled': False}

    def is_channel_explicitly_disabled(self, channel_id):
        entry = self.entries.get(channel_id)
        return isinstance(entry, dict) and (entry.get('enabled') is False)


def is_openclaw_sync_enabled(env):
    sync_all = (env.get('SYNC_OPENCLAW_CONFIG') or 'true').strip().lower()
    return sync_all in ('', 'true', '1', 'yes')


def sync_models(ctx):
    if not is_openclaw_sync_enabled(ctx.env):
        print('ℹ️ 已关闭整体配置同步，跳过模型同步')
        return

    sync_model = (ctx.env.get('SYNC_MODEL_CONFIG') or 'true').strip().lower()
    if sync_model not in ('', 'true', '1', 'yes'):
        return

    def sync_provider(provider_name, api_key, base_url, protocol, model_ids_raw, context_window, max_tokens):
        if not ((api_key and base_url) or model_ids_raw):
            return None
        provider = ensure_path(ctx.config, ['models', 'providers', provider_name])
        if api_key:
            provider['apiKey'] = api_key
        if base_url:
            provider['baseUrl'] = base_url
        provider['api'] = protocol or 'openai-completions'
        models = provider.get('models', [])
        model_ids = parse_csv(model_ids_raw)
        for model_id in model_ids:
            model_obj = next((item for item in models if item.get('id') == model_id), None)
            if not model_obj:
                model_obj = {
                    'id': model_id, 'name': model_id, 'reasoning': False,
                    'input': ['text', 'image'],
                    'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0},
                }
                models.append(model_obj)
            model_obj['contextWindow'] = int(context_window or 200000)
            model_obj['maxTokens'] = int(max_tokens or 8192)
        provider['models'] = models
        return provider_name

    sync_provider(
        'default', ctx.env.get('API_KEY'), ctx.env.get('BASE_URL'),
        ctx.env.get('API_PROTOCOL'), ctx.env.get('MODEL_ID') or 'gpt-4o',
        ctx.env.get('CONTEXT_WINDOW'), ctx.env.get('MAX_TOKENS'),
    )
    enabled_extra_providers = []
    for provider_cfg in collect_extra_model_providers(ctx.env):
        synced_name = sync_provider(
            provider_cfg['provider_name'], provider_cfg['api_key'],
            provider_cfg['base_url'], provider_cfg['protocol'],
            provider_cfg['model_ids'], provider_cfg['context_window'],
            provider_cfg['max_tokens'],
        )
        if synced_name:
            enabled_extra_providers.append(synced_name)

    default_model_id = first_csv_item(ctx.env.get('MODEL_ID') or 'gpt-4o', 'gpt-4o')
    primary_model_raw = str(ctx.env.get('PRIMARY_MODEL') or '').strip()
    image_model_raw = str(ctx.env.get('IMAGE_MODEL_ID') or '').strip()
    provider_names = set(ensure_path(ctx.config, ['models', 'providers']).keys())

    primary_model = resolve_primary_model(ctx.env, default_model_id, provider_names=provider_names)
    primary_image_model = resolve_image_model(ctx.env, default_model_id, provider_names=provider_names)

    ensure_path(ctx.config, ['agents', 'defaults', 'model'])['primary'] = primary_model
    ensure_path(ctx.config, ['agents', 'defaults', 'imageModel'])['primary'] = primary_image_model

    workspace_root = (ctx.env.get('OPENCLAW_WORKSPACE_ROOT') or '/home/node/.openclaw').rstrip('/') or '/'
    workspace = f"{workspace_root}/workspace" if workspace_root != '/' else '/workspace'
    ctx.config['agents']['defaults']['workspace'] = workspace

    memory = ensure_path(ctx.config, ['memory'])
    memory.setdefault('backend', 'qmd')
    memory.setdefault('citations', 'auto')
    memory_cfg = ensure_path(memory, ['qmd'])
    memory_cfg.setdefault('includeDefaultMemory', True)
    ensure_path(memory_cfg, ['sessions']).setdefault('enabled', True)
    limits_cfg = ensure_path(memory_cfg, ['limits'])
    limits_cfg.setdefault('timeoutMs', 8000)
    limits_cfg.setdefault('maxResults', 16)
    update_cfg = ensure_path(memory_cfg, ['update'])
    update_cfg.setdefault('onBoot', True)
    update_cfg.setdefault('interval', '5m')
    update_cfg.setdefault('debounceMs', 15000)
    paths = memory_cfg.get('paths')
    if not isinstance(paths, list):
        paths = []
        memory_cfg['paths'] = paths
    workspace_path = next((item for item in paths if isinstance(item, dict) and item.get('name') == 'workspace'), None)
    if not workspace_path:
        workspace_path = {'name': 'workspace'}
        paths.append(workspace_path)
    workspace_path['path'] = workspace
    workspace_path['pattern'] = '**/*.md'

    if memory.get('backend') == 'qmd':
        qmd_path = '/usr/local/bin/qmd'
        try:
            subprocess.run([qmd_path, '--version'], capture_output=True, check=True)
        except Exception:
            try:
                qmd_path = 'qmd'
                subprocess.run([qmd_path, '--version'], capture_output=True, check=True)
                qmd_path = subprocess.check_output(['which', 'qmd']).decode().strip()
            except Exception:
                print('⚠️ 警告: qmd 命令执行失败，向量内存功能可能受限')
                qmd_path = None
        if qmd_path:
            memory_cfg['command'] = qmd_path
        else:
            if memory.get('backend') == 'qmd':
                print('⚠️ 自动禁用 qmd 内存后端（命令不可用或架构不兼容）')
                memory['backend'] = 'off'
    else:
        memory_cfg.setdefault('command', '/usr/local/bin/qmd')

    msg = f'✅ 模型同步完成: 主模型={primary_model}'
    if primary_model_raw:
        msg += f' (来自 PRIMARY_MODEL={primary_model_raw})'
    msg += f', 图片模型={primary_image_model}'
    if enabled_extra_providers:
        msg += f", 已启用额外提供商: {', '.join(enabled_extra_providers)}"
    print(msg)


def sync_agent_and_tools(ctx):
    if not is_openclaw_sync_enabled(ctx.env):
        print('ℹ️ 已关闭整体配置同步，跳过 Agent 与工具同步')
        return

    sandbox = ensure_path(ctx.config, ['agents', 'defaults', 'sandbox'])
    sandbox_mode = (ctx.env.get('OPENCLAW_SANDBOX_MODE') or 'off').strip().lower()
    sandbox['mode'] = sandbox_mode
    sandbox_scope = (ctx.env.get('OPENCLAW_SANDBOX_SCOPE') or 'agent').strip().lower()
    sandbox['scope'] = sandbox_scope
    sandbox_workspace_access = (ctx.env.get('OPENCLAW_SANDBOX_WORKSPACE_ACCESS') or 'none').strip().lower()
    sandbox['workspaceAccess'] = sandbox_workspace_access

    if sandbox_mode != 'off':
        docker_cfg = ensure_path(sandbox, ['docker'])
        if ctx.env.get('OPENCLAW_SANDBOX_DOCKER_IMAGE'):
            docker_cfg['image'] = ctx.env['OPENCLAW_SANDBOX_DOCKER_IMAGE']
        elif 'image' not in docker_cfg:
            docker_cfg['image'] = 'openclaw-sandbox:bookworm-slim'
        if parse_bool(ctx.env.get('OPENCLAW_SANDBOX_JOIN_NETWORK'), False):
            hostname = ctx.env.get('HOSTNAME')
            if hostname:
                docker_cfg['network'] = f"container:{hostname}"
                docker_cfg['dangerouslyAllowContainerNamespaceJoin'] = True

    sandbox_json = parse_json_object(ctx.env.get('OPENCLAW_SANDBOX_JSON'), 'OPENCLAW_SANDBOX_JSON')
    if sandbox_json is not None:
        deep_merge(sandbox, sandbox_json)
        print('✅ 已从 OPENCLAW_SANDBOX_JSON 同步沙箱配置')

    tools = ensure_path(ctx.config, ['tools'])
    tools_json = parse_json_object(ctx.env.get('OPENCLAW_TOOLS_JSON'), 'OPENCLAW_TOOLS_JSON')
    if tools_json is not None:
        deep_merge(tools, tools_json)
        print('✅ 已从 OPENCLAW_TOOLS_JSON 同步工具配置')
    else:
        tools['profile'] = 'full'
        ensure_path(tools, ['sessions'])['visibility'] = 'all'
        ensure_path(tools, ['fs'])['workspaceOnly'] = True
        print(f'✅ Agent/工具配置同步完成: sandbox.mode={sandbox_mode}, scope={sandbox_scope}, workspaceAccess={sandbox_workspace_access}, profile=full')


def sync():
    path = os.environ.get('CONFIG_FILE', '/home/node/.openclaw/openclaw.json')
    try:
        if not is_openclaw_sync_enabled(os.environ):
            print('ℹ️ 已关闭整体配置同步，跳过所有环境变量同步逻辑')
            return
        from openclaw_config.migrate import migrate_tts_config
        config = load_config_with_compat(path)
        migrate_tts_config(config)
        ctx = SyncContext(config, os.environ)
        normalize_feishu_config(ctx.channels)
        normalize_dingtalk_config(ctx.channels)
        normalize_wecom_config(ctx.channels)
        normalize_qqbot_config(ctx.channels)
        sync_models(ctx)
        sync_agent_and_tools(ctx)
        ensure_path(ctx.config, ['meta'])['lastTouchedAt'] = utc_now_iso()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ctx.config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f'❌ 同步失败: {exc}', file=sys.stderr)
        sys.exit(1)