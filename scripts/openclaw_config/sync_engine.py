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
    merge_wecom_accounts_from_env, merge_qqbot_accounts_from_env,
    validate_feishu_multi_accounts, validate_dingtalk_multi_accounts,
    validate_wecom_multi_accounts, validate_qqbot_multi_accounts,
    migrate_feishu_config,
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

    primary_provider = sync_provider(
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
        if 'docker' in sandbox and isinstance(sandbox['docker'], dict):
            d_cfg = sandbox['docker']
            net = d_cfg.get('network')
            if isinstance(net, str) and net.startswith('container:'):
                if d_cfg.get('dangerouslyAllowContainerNamespaceJoin') is not True:
                    d_cfg['dangerouslyAllowContainerNamespaceJoin'] = True
                    print(f'✅ 检测到沙箱网络配置为 {net}，已自动开启 dangerouslyAllowContainerNamespaceJoin')
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


def sync_feishu_channel(ctx, channel):
    env = ctx.env
    account_id = (env.get('FEISHU_DEFAULT_ACCOUNT') or 'default').strip() or 'default'
    channel.update({
        'enabled': True,
        'appId': env['FEISHU_APP_ID'],
        'appSecret': env['FEISHU_APP_SECRET'],
        'dmPolicy': env.get('FEISHU_DM_POLICY') or ctx.default_dm_policy,
        'allowFrom': parse_csv(env.get('FEISHU_ALLOW_FROM')) or ctx.default_allow_from,
        'groupPolicy': env.get('FEISHU_GROUP_POLICY') or ctx.default_group_policy,
        'groupAllowFrom': parse_csv(env.get('FEISHU_GROUP_ALLOW_FROM')),
        'streaming': parse_bool(env.get('FEISHU_STREAMING', 'true'), True),
        'requireMention': parse_bool(env.get('FEISHU_REQUIRE_MENTION', 'true'), True),
    })

    feishu_groups = parse_json_object(env.get('FEISHU_GROUPS_JSON'), 'FEISHU_GROUPS_JSON')
    if feishu_groups is not None:
        channel['groups'] = feishu_groups

    channel.setdefault('accounts', {})
    channel['accounts'][account_id] = {
        'appId': env['FEISHU_APP_ID'],
        'appSecret': env['FEISHU_APP_SECRET'],
        'name': env.get('FEISHU_NAME') or 'OpenClaw Bot',
    }


def sync_dingtalk_channel(ctx, channel):
    env = ctx.env
    channel.update({
        'enabled': True,
        'clientId': env['DINGTALK_CLIENT_ID'],
        'clientSecret': env['DINGTALK_CLIENT_SECRET'],
        'robotCode': env.get('DINGTALK_ROBOT_CODE') or env['DINGTALK_CLIENT_ID'],
        'dmPolicy': env.get('DINGTALK_DM_POLICY') or ctx.default_dm_policy,
        'groupPolicy': env.get('DINGTALK_GROUP_POLICY') or ctx.default_group_policy,
        'messageType': env.get('DINGTALK_MESSAGE_TYPE') or 'markdown',
        'allowFrom': parse_csv(env.get('DINGTALK_ALLOW_FROM')) or ctx.default_allow_from,
    })
    if env.get('DINGTALK_CORP_ID'):
        channel['corpId'] = env['DINGTALK_CORP_ID']
    if env.get('DINGTALK_AGENT_ID'):
        channel['agentId'] = env['DINGTALK_AGENT_ID']
    if env.get('DINGTALK_CARD_TEMPLATE_ID'):
        channel['cardTemplateId'] = env['DINGTALK_CARD_TEMPLATE_ID']
    if env.get('DINGTALK_CARD_TEMPLATE_KEY'):
        channel['cardTemplateKey'] = env['DINGTALK_CARD_TEMPLATE_KEY']
    if env.get('DINGTALK_MAX_RECONNECT_CYCLES'):
        channel['maxReconnectCycles'] = int(env['DINGTALK_MAX_RECONNECT_CYCLES'])
    if env.get('DINGTALK_DEBUG'):
        channel['debug'] = parse_bool(env.get('DINGTALK_DEBUG'), False)
    if env.get('DINGTALK_JOURNAL_TTL_DAYS'):
        channel['journalTTLDays'] = int(env['DINGTALK_JOURNAL_TTL_DAYS'])
    if env.get('DINGTALK_SHOW_THINKING'):
        channel['showThinking'] = parse_bool(env.get('DINGTALK_SHOW_THINKING'), False)
    if env.get('DINGTALK_THINKING_MESSAGE'):
        channel['thinkingMessage'] = env['DINGTALK_THINKING_MESSAGE']
    if env.get('DINGTALK_ASYNC_MODE'):
        channel['asyncMode'] = parse_bool(env.get('DINGTALK_ASYNC_MODE'), False)
    if env.get('DINGTALK_ASYNC_ACK_TEXT'):
        channel['asyncAckText'] = env['DINGTALK_ASYNC_ACK_TEXT']

    account = ensure_path(channel, ['accounts', 'default'])
    account.update({
        'clientId': env['DINGTALK_CLIENT_ID'],
        'clientSecret': env['DINGTALK_CLIENT_SECRET'],
        'robotCode': env.get('DINGTALK_ROBOT_CODE') or env['DINGTALK_CLIENT_ID'],
        'dmPolicy': env.get('DINGTALK_DM_POLICY') or ctx.default_dm_policy,
        'groupPolicy': env.get('DINGTALK_GROUP_POLICY') or ctx.default_group_policy,
        'messageType': env.get('DINGTALK_MESSAGE_TYPE') or 'markdown',
        'allowFrom': parse_csv(env.get('DINGTALK_ALLOW_FROM')) or ctx.default_allow_from,
    })
    if env.get('DINGTALK_CORP_ID'):
        account['corpId'] = env['DINGTALK_CORP_ID']
    if env.get('DINGTALK_AGENT_ID'):
        account['agentId'] = env['DINGTALK_AGENT_ID']
    if env.get('DINGTALK_CARD_TEMPLATE_ID'):
        account['cardTemplateId'] = env['DINGTALK_CARD_TEMPLATE_ID']
    if env.get('DINGTALK_CARD_TEMPLATE_KEY'):
        account['cardTemplateKey'] = env['DINGTALK_CARD_TEMPLATE_KEY']
    if env.get('DINGTALK_MAX_RECONNECT_CYCLES'):
        account['maxReconnectCycles'] = int(env['DINGTALK_MAX_RECONNECT_CYCLES'])
    if env.get('DINGTALK_DEBUG'):
        account['debug'] = parse_bool(env.get('DINGTALK_DEBUG'), False)


def sync_qqbot_channel(ctx, channel):
    env = ctx.env
    channel.update({
        'enabled': True,
        'appId': env['QQBOT_APP_ID'],
        'clientSecret': env['QQBOT_CLIENT_SECRET'],
        'dmPolicy': env.get('QQBOT_DM_POLICY') or ctx.default_dm_policy,
        'allowFrom': parse_csv(env.get('QQBOT_ALLOW_FROM')) or ctx.default_allow_from,
        'groupPolicy': env.get('QQBOT_GROUP_POLICY') or ctx.default_group_policy,
    })
    ensure_path(channel, ['accounts', 'default']).update({
        'enabled': True,
        'appId': env['QQBOT_APP_ID'],
        'clientSecret': env['QQBOT_CLIENT_SECRET'],
    })


def sync_napcat_channel(ctx, channel):
    env = ctx.env
    channel.update({
        'enabled': True,
        'reverseWsPort': int(env['NAPCAT_REVERSE_WS_PORT']),
        'requireMention': True,
        'rateLimitMs': 1000,
        'dmPolicy': env.get('NAPCAT_DM_POLICY') or ctx.default_dm_policy,
        'allowFrom': parse_csv(env.get('NAPCAT_ALLOW_FROM')) or ctx.default_allow_from,
        'groupPolicy': env.get('NAPCAT_GROUP_POLICY') or ctx.default_group_policy,
    })
    if env.get('NAPCAT_HTTP_URL'):
        channel['httpUrl'] = env['NAPCAT_HTTP_URL']
    if env.get('NAPCAT_ACCESS_TOKEN'):
        channel['accessToken'] = env['NAPCAT_ACCESS_TOKEN']
    if env.get('NAPCAT_ADMINS'):
        channel['admins'] = [int(item) for item in parse_csv(env.get('NAPCAT_ADMINS'))]


def sync_wecom_channel(ctx, channel):
    env = ctx.env
    channel['enabled'] = True
    channel['dmPolicy'] = env.get('WECOM_DM_POLICY') or ctx.default_dm_policy
    channel['allowFrom'] = parse_csv(env.get('WECOM_ALLOW_FROM')) or ctx.default_allow_from
    channel['groupPolicy'] = env.get('WECOM_GROUP_POLICY') or ctx.default_group_policy

    if env.get('WECOM_ADMIN_USERS'):
        channel['adminUsers'] = parse_csv(env.get('WECOM_ADMIN_USERS'))

    commands = ensure_path(channel, ['commands'])
    commands['enabled'] = parse_bool(env.get('WECOM_COMMANDS_ENABLED'), True)
    commands['allowlist'] = parse_csv(env.get('WECOM_COMMANDS_ALLOWLIST')) or ['/new', '/compact', '/help', '/status']

    dynamic_agents = ensure_path(channel, ['dynamicAgents'])
    dynamic_agents['enabled'] = parse_bool(env.get('WECOM_DYNAMIC_AGENTS_ENABLED'), True)
    dynamic_agents['adminBypass'] = parse_bool(env.get('WECOM_DYNAMIC_AGENTS_ADMIN_BYPASS'), False)

    has_single_account = bool((env.get('WECOM_BOT_ID') or '').strip() and (env.get('WECOM_SECRET') or '').strip())
    if not has_single_account:
        return

    account_id = (env.get('WECOM_DEFAULT_ACCOUNT') or 'default').strip() or 'default'
    channel['defaultAccount'] = account_id
    account = ensure_path(channel, [account_id])
    account.update({'botId': env['WECOM_BOT_ID'], 'secret': env['WECOM_SECRET']})

    optional_fields = {
        'WECOM_WELCOME_MESSAGE': 'welcomeMessage',
        'WECOM_DM_POLICY': 'dmPolicy',
        'WECOM_GROUP_POLICY': 'groupPolicy',
        'WECOM_WORKSPACE_TEMPLATE': 'workspaceTemplate',
    }
    for env_name, field_name in optional_fields.items():
        if env.get(env_name):
            account[field_name] = env[env_name]

    if env.get('WECOM_ALLOW_FROM'):
        account['allowFrom'] = parse_csv(env.get('WECOM_ALLOW_FROM'))
    if env.get('WECOM_GROUP_ALLOW_FROM'):
        account['groupAllowFrom'] = parse_csv(env.get('WECOM_GROUP_ALLOW_FROM'))
    account['sendThinkingMessage'] = parse_bool(env.get('WECOM_SEND_THINKING_MESSAGE'), False)

    dm_cfg = ensure_path(account, ['dm'])
    dm_cfg['createAgentOnFirstMessage'] = parse_bool(env.get('WECOM_DM_CREATE_AGENT_ON_FIRST_MESSAGE'), True)

    group_chat = ensure_path(account, ['groupChat'])
    group_chat['enabled'] = parse_bool(env.get('WECOM_GROUP_CHAT_ENABLED'), True)
    group_chat['requireMention'] = parse_bool(env.get('WECOM_GROUP_CHAT_REQUIRE_MENTION'), True)
    group_chat['mentionPatterns'] = parse_csv(env.get('WECOM_GROUP_CHAT_MENTION_PATTERNS')) or ['@']

    if env.get('WECOM_AGENT_CORP_ID') or env.get('WECOM_AGENT_CORP_SECRET') or env.get('WECOM_AGENT_ID'):
        agent = ensure_path(account, ['agent'])
        if env.get('WECOM_AGENT_CORP_ID'):
            agent['corpId'] = env['WECOM_AGENT_CORP_ID']
        if env.get('WECOM_AGENT_CORP_SECRET'):
            agent['corpSecret'] = env['WECOM_AGENT_CORP_SECRET']
        if env.get('WECOM_AGENT_ID'):
            agent['agentId'] = int(env['WECOM_AGENT_ID'])

    webhook_map = parse_json_object(env.get('WECOM_WEBHOOKS_JSON'), 'WECOM_WEBHOOKS_JSON')
    if webhook_map is not None:
        account['webhooks'] = webhook_map

    network = {}
    if env.get('WECOM_NETWORK_EGRESS_PROXY_URL'):
        network['egressProxyUrl'] = env['WECOM_NETWORK_EGRESS_PROXY_URL']
    if env.get('WECOM_NETWORK_API_BASE_URL'):
        network['apiBaseUrl'] = env['WECOM_NETWORK_API_BASE_URL']
    if network:
        account['network'] = deep_merge(account.get('network', {}), network)


def apply_channel_rules(ctx):
    channel_labels = {
        'telegram': 'Telegram',
        'feishu': '飞书',
        'dingtalk': '钉钉',
        'qqbot': 'QQ 机器人',
        'napcat': 'NapCat',
        'wecom': '企业微信',
    }

    rules = [
        {
            'channel': 'telegram',
            'required_envs': ['TELEGRAM_BOT_TOKEN'],
            'sync': lambda channel: channel.update({
                'botToken': ctx.env['TELEGRAM_BOT_TOKEN'],
                'dmPolicy': ctx.env.get('TELEGRAM_DM_POLICY') or ctx.default_dm_policy,
                'allowFrom': parse_csv(ctx.env.get('TELEGRAM_ALLOW_FROM')) or ctx.default_allow_from,
                'groupPolicy': ctx.env.get('TELEGRAM_GROUP_POLICY') or ctx.default_group_policy,
                'streaming': 'partial',
            }),
            'install': False,
        },
        {
            'channel': 'feishu',
            'required_envs': ['FEISHU_APP_ID', 'FEISHU_APP_SECRET'],
            'sync': lambda channel: sync_feishu_channel(ctx, channel),
            'install': True,
        },
        {
            'channel': 'dingtalk',
            'required_envs': ['DINGTALK_CLIENT_ID', 'DINGTALK_CLIENT_SECRET'],
            'sync': lambda channel: sync_dingtalk_channel(ctx, channel),
            'install': True,
        },
        {
            'channel': 'qqbot',
            'plugin_id': 'openclaw-qqbot',
            'required_envs': ['QQBOT_APP_ID', 'QQBOT_CLIENT_SECRET'],
            'sync': lambda channel: sync_qqbot_channel(ctx, channel),
            'install': True,
        },
        {
            'channel': 'napcat',
            'required_envs': ['NAPCAT_REVERSE_WS_PORT'],
            'sync': lambda channel: sync_napcat_channel(ctx, channel),
            'install': True,
        },
        {
            'channel': 'wecom',
            'required_envs': ['WECOM_BOT_ID', 'WECOM_SECRET'],
            'sync': lambda channel: sync_wecom_channel(ctx, channel),
            'install': True,
        },
    ]

    for rule in rules:
        channel_id = rule['channel']
        plugin_id = rule.get('plugin_id', channel_id)
        channel_label = channel_labels.get(channel_id, channel_id)
        has_env = all(ctx.env.get(key) for key in rule['required_envs'])

        if has_env:
            channel = ctx.channel(channel_id)
            rule['sync'](channel)
            ctx.enable_channel(plugin_id, install=rule['install'])
            if plugin_id != channel_id:
                ctx.disable_channel(channel_id)
            print(f"✅ 渠道同步: {channel_label}")
            continue

        if channel_id == 'feishu' and not ctx.has_feishu_any_env:
            ctx.disable_channel(plugin_id)
            continue

        if channel_id == 'dingtalk' and not ctx.has_dingtalk_any_env:
            ctx.disable_channel(plugin_id)
            continue

        if channel_id == 'wecom' and not ctx.has_wecom_any_env:
            ctx.disable_channel(plugin_id)
            continue

        if channel_id == 'qqbot' and not ctx.has_qqbot_any_env:
            ctx.disable_channel(plugin_id)
            ctx.entries.pop('qqbot', None)
            continue

        if ctx.entries.get(plugin_id, {}).get('enabled'):
            ctx.disable_channel(plugin_id)
            print(f"🚫 {channel_label} 环境变量缺失，已禁用渠道")
        else:
            print(f"ℹ️ {channel_label} 未提供环境变量，保持禁用")


def apply_wecom_legacy_v1_compat(ctx):
    has_new_single_account = bool((ctx.env.get('WECOM_BOT_ID') or '').strip() and (ctx.env.get('WECOM_SECRET') or '').strip())
    has_legacy_v1 = bool((ctx.env.get('WECOM_TOKEN') or '').strip() and (ctx.env.get('WECOM_ENCODING_AES_KEY') or '').strip())
    if has_new_single_account or not has_legacy_v1:
        return

    channel = ctx.channel('wecom')
    sync_wecom_channel(ctx, channel)
    ctx.enable_channel('wecom', install=True)
    print('✅ 渠道同步: 企业微信（兼容旧版环境变量）')


def apply_multi_account_plugin_state(ctx):
    feishu_accounts = get_feishu_accounts(ctx.channels.get('feishu'))
    if ctx.has_feishu_accounts_env:
        if feishu_accounts:
            ctx.enable_channel('feishu', install=True)
            print('✅ 已根据飞书多账号环境变量启用插件')
        else:
            ctx.disable_channel('feishu')
            print('ℹ️ 飞书多账号环境变量未生成有效账号，保持插件禁用')
    elif not ctx.has_feishu_any_env and not feishu_accounts:
        ctx.disable_channel('feishu')
        print('ℹ️ 飞书未提供任何环境变量，保持插件禁用')

    dingtalk_accounts = get_dingtalk_accounts(ctx.channels.get('dingtalk'))
    if ctx.has_dingtalk_accounts_env:
        if dingtalk_accounts:
            ctx.enable_channel('dingtalk', install=True)
            print('✅ 已根据钉钉多机器人环境变量启用插件')
        else:
            ctx.disable_channel('dingtalk')
            print('ℹ️ 钉钉多机器人环境变量未生成有效账号，保持插件禁用')
    elif not ctx.has_dingtalk_any_env:
        ctx.disable_channel('dingtalk')
        print('ℹ️ 钉钉未提供任何环境变量，保持插件禁用')

    wecom_accounts = get_wecom_accounts(ctx.channels.get('wecom'))
    if ctx.has_wecom_accounts_env:
        if wecom_accounts:
            ctx.enable_channel('wecom', install=True)
            print('✅ 已根据企业微信多账号环境变量启用插件')
        else:
            ctx.disable_channel('wecom')
            print('ℹ️ 企业微信多账号环境变量未生成有效账号，保持插件禁用')
    elif not ctx.has_wecom_any_env:
        ctx.disable_channel('wecom')
        print('ℹ️ 企业微信未提供任何环境变量，保持插件禁用')

    qqbot_accounts = get_qqbot_accounts(ctx.channels.get('qqbot'))
    if ctx.has_qqbot_bots_env:
        if qqbot_accounts:
            ctx.enable_channel('openclaw-qqbot', install=True)
            print('✅ 已根据 QQ 机器人多 Bot 环境变量启用插件 openclaw-qqbot')
        else:
            ctx.disable_channel('openclaw-qqbot')
            print('ℹ️ QQ 机器人多 Bot 环境变量未生成有效 Bot，保持插件禁用')
    elif not ctx.has_qqbot_any_env:
        ctx.disable_channel('openclaw-qqbot')
        print('ℹ️ QQ 机器人未提供任何环境变量，保持插件禁用')


def migrate_qqbot_plugin_entry(ctx):
    legacy_plugin_id = 'qqbot'
    official_plugin_id = 'openclaw-qqbot'
    legacy_entry = ctx.entries.get(legacy_plugin_id)
    official_entry = ctx.entries.get(official_plugin_id)

    if isinstance(legacy_entry, dict):
        if not isinstance(official_entry, dict):
            ctx.entries[official_plugin_id] = deepcopy(legacy_entry)
        elif legacy_entry.get('enabled') and not official_entry.get('enabled'):
            official_entry['enabled'] = True

    ctx.entries.pop(legacy_plugin_id, None)

    legacy_install = ctx.installs.get(legacy_plugin_id)
    official_install = ctx.installs.get(official_plugin_id)
    if isinstance(legacy_install, dict):
        if not isinstance(official_install, dict):
            migrated_install = deepcopy(legacy_install)
            migrated_install['sourcePath'] = '/home/node/.openclaw/openclaw-qqbot'
            migrated_install['installPath'] = '/home/node/.openclaw/extensions/openclaw-qqbot'
            ctx.installs[official_plugin_id] = migrated_install

    ctx.installs.pop(legacy_plugin_id, None)


def apply_feishu_plugin_switch(ctx):
    feishu_accounts = get_feishu_accounts(ctx.channels.get('feishu'))
    has_credentials = bool(ctx.env.get('FEISHU_APP_ID') and ctx.env.get('FEISHU_APP_SECRET')) or bool(feishu_accounts)
    official_plugin_id = 'openclaw-lark'
    legacy_plugin_id = 'feishu-openclaw-plugin'
    if legacy_plugin_id in ctx.entries and official_plugin_id not in ctx.entries:
        legacy_entry = ctx.entries.get(legacy_plugin_id)
        if isinstance(legacy_entry, dict):
            ctx.entries[official_plugin_id] = deepcopy(legacy_entry)
        del ctx.entries[legacy_plugin_id]
        print('✅ 已将飞书官方插件 ID 从 feishu-openclaw-plugin 迁移为 openclaw-lark')
    if ctx.feishu_plugin_explicit:
        ctx.entries[official_plugin_id] = {'enabled': ctx.feishu_plugin_enabled}
        ctx.entries['feishu'] = {'enabled': not ctx.feishu_plugin_enabled}
        if ctx.feishu_plugin_enabled:
            print('✅ 已启用插件开关: 飞书官方插件 openclaw-lark')
            print('🚫 已自动禁用旧版渠道: 飞书')
        else:
            print('🚫 已禁用插件开关: 飞书官方插件 openclaw-lark')
            print('✅ 已自动启用旧版渠道: 飞书')
        return

    ctx.entries[official_plugin_id] = {'enabled': False}
    ctx.entries['feishu'] = {'enabled': has_credentials}
    if has_credentials:
        print('ℹ️ 飞书官方插件开关未配置，默认启用旧版飞书渠道并禁用官方插件')
    else:
        print('ℹ️ 未检测到飞书凭证且飞书官方插件开关未配置，已同时禁用官方插件和旧版飞书渠道')


def finalize_plugins(ctx):
    ctx.plugins['allow'] = [name for name, entry in ctx.entries.items() if entry.get('enabled')]
    print('📦 已配置插件集合: ' + ', '.join(ctx.plugins['allow']))


def sync_channels_and_plugins(ctx):
    if not is_openclaw_sync_enabled(ctx.env):
        print('ℹ️ 已关闭整体配置同步，跳过渠道与插件同步')
        return

    if ctx.env.get('OPENCLAW_PLUGINS_ENABLED'):
        ctx.plugins['enabled'] = ctx.env['OPENCLAW_PLUGINS_ENABLED'].lower() == 'true'

    apply_channel_rules(ctx)
    apply_wecom_legacy_v1_compat(ctx)
    merge_feishu_accounts_from_env(ctx.channels, ctx.env)
    # 环境同步后再次标准化飞书结构，确保冗余字段被移除
    normalize_feishu_config(ctx.channels)

    merge_dingtalk_accounts_from_env(ctx.channels, ctx.env)
    merge_wecom_accounts_from_env(ctx.channels, ctx.env)
    merge_qqbot_accounts_from_env(ctx.channels, ctx.env)
    migrate_qqbot_plugin_entry(ctx)
    apply_multi_account_plugin_state(ctx)
    apply_feishu_plugin_switch(ctx)
    finalize_plugins(ctx)
    validate_feishu_multi_accounts(ctx.channels)
    validate_dingtalk_multi_accounts(ctx.channels)
    validate_wecom_multi_accounts(ctx.channels)
    validate_qqbot_multi_accounts(ctx.channels)


def sync_gateway(ctx):
    if not is_openclaw_sync_enabled(ctx.env):
        print('ℹ️ 已关闭整体配置同步，跳过 Gateway 同步')
        return

    if not ctx.env.get('OPENCLAW_GATEWAY_TOKEN'):
        return

    gateway = ensure_path(ctx.config, ['gateway'])
    gateway['port'] = int(ctx.env.get('OPENCLAW_GATEWAY_PORT') or 18789)
    gateway['bind'] = ctx.env.get('OPENCLAW_GATEWAY_BIND') or '0.0.0.0'
    gateway['mode'] = ctx.env.get('OPENCLAW_GATEWAY_MODE') or 'local'

    control_ui = ensure_path(gateway, ['controlUi'])
    control_ui['allowInsecureAuth'] = parse_bool(ctx.env.get('OPENCLAW_GATEWAY_ALLOW_INSECURE_AUTH', 'true'), True)
    control_ui['dangerouslyDisableDeviceAuth'] = parse_bool(ctx.env.get('OPENCLAW_GATEWAY_DANGEROUSLY_DISABLE_DEVICE_AUTH', 'false'), False)
    if ctx.env.get('OPENCLAW_GATEWAY_ALLOWED_ORIGINS'):
        control_ui['allowedOrigins'] = parse_csv(ctx.env.get('OPENCLAW_GATEWAY_ALLOWED_ORIGINS'))

    auth = ensure_path(gateway, ['auth'])
    auth['token'] = ctx.env['OPENCLAW_GATEWAY_TOKEN']
    auth['mode'] = ctx.env.get('OPENCLAW_GATEWAY_AUTH_MODE') or 'token'
    print('✅ Gateway 同步完成')


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

        migrate_feishu_config(ctx.channels)
        normalize_dingtalk_config(ctx.channels)
        normalize_wecom_config(ctx.channels)
        normalize_qqbot_config(ctx.channels)

        sync_models(ctx)
        sync_agent_and_tools(ctx)
        sync_channels_and_plugins(ctx)
        sync_gateway(ctx)

        ensure_path(ctx.config, ['meta'])['lastTouchedAt'] = utc_now_iso()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ctx.config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f'❌ 同步失败: {exc}', file=sys.stderr)
        sys.exit(1)
