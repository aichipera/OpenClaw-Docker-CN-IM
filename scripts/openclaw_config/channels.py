from openclaw_config.utils import (
    ensure_path, deep_merge, parse_bool, parse_csv, 
    parse_json_object, first_csv_item
)
from openclaw_config.models import (
    is_valid_account_id, is_feishu_account_config, 
    is_wecom_account_config, is_dingtalk_account_config, is_qqbot_account_config,
    DINGTALK_ACCOUNT_FIELDS, DINGTALK_RESERVED_FIELDS, 
    WECOM_ACCOUNT_FIELDS, WECOM_RESERVED_FIELDS,
    FEISHU_ACCOUNT_FIELDS, FEISHU_GROUP_FIELDS, FEISHU_RESERVED_FIELDS,
    QQBOT_ACCOUNT_FIELDS,
    get_feishu_accounts, get_dingtalk_accounts, get_wecom_accounts
)


def normalize_wecom_config(channels: dict) -> None:
    wecom = channels.get('wecom')
    if not isinstance(wecom, dict):
        return

    normalized = {}
    migrated = False
    accounts = wecom.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}

    has_structured_accounts = any(
        is_valid_account_id(account_id) and is_wecom_account_config(cfg)
        for account_id, cfg in accounts.items()
    )

    legacy_account = {key: wecom[key] for key in WECOM_ACCOUNT_FIELDS if key in wecom}
    if legacy_account and not has_structured_accounts:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in legacy_account.items():
            default_account.setdefault(key, value)
        accounts['default'] = default_account
        migrated = True

    normalized_accounts = {}
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_wecom_account_config(cfg):
            pruned_cfg = {k: v for k, v in cfg.items() if k in WECOM_ACCOUNT_FIELDS}
            normalized_accounts[account_id] = pruned_cfg

    if normalized_accounts:
        wecom['accounts'] = normalized_accounts
        default_account_id = str(wecom.get('defaultAccount') or 'default').strip() or 'default'
        if default_account_id not in normalized_accounts and 'default' in normalized_accounts:
            default_account_id = 'default'
        wecom['defaultAccount'] = default_account_id

        for key in list(wecom.keys()):
            if key not in WECOM_RESERVED_FIELDS:
                del wecom[key]

        migrated = True

    if migrated:
        print('✅ 企业微信配置已标准化为多账号结构')


def normalize_dingtalk_config(channels: dict) -> None:
    dingtalk = channels.get('dingtalk')
    if not isinstance(dingtalk, dict):
        return

    migrated = False
    accounts = dingtalk.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}

    has_structured_accounts = any(
        is_valid_account_id(account_id) and is_dingtalk_account_config(cfg)
        for account_id, cfg in accounts.items()
    )

    legacy_account = {key: dingtalk[key] for key in DINGTALK_ACCOUNT_FIELDS if key in dingtalk}
    if legacy_account and not has_structured_accounts:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in legacy_account.items():
            default_account.setdefault(key, value)
        accounts['default'] = default_account
        migrated = True

    main_account = accounts.pop('main', None) if 'main' in accounts else None
    if isinstance(main_account, dict):
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in main_account.items():
            default_account.setdefault(key, value)
        accounts['default'] = default_account
        migrated = True

    normalized_accounts = {}
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_dingtalk_account_config(cfg):
            pruned_cfg = {k: v for k, v in cfg.items() if k in DINGTALK_ACCOUNT_FIELDS}
            normalized_accounts[account_id] = pruned_cfg

    if normalized_accounts:
        dingtalk['accounts'] = normalized_accounts
        default_account_id = str(dingtalk.get('defaultAccount') or 'default').strip() or 'default'
        if default_account_id not in normalized_accounts and 'default' in normalized_accounts:
            default_account_id = 'default'
        dingtalk['defaultAccount'] = default_account_id

        for key in list(dingtalk.keys()):
            if key not in DINGTALK_RESERVED_FIELDS:
                del dingtalk[key]

        migrated = True

    if migrated:
        print('✅ 钉钉配置已标准化为多账号结构')


def normalize_qqbot_config(channels: dict) -> None:
    qqbot = channels.get('qqbot')
    if not isinstance(qqbot, dict):
        return

    migrated = False
    accounts = qqbot.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}

    has_structured_accounts = any(
        is_valid_account_id(account_id) and is_qqbot_account_config(cfg)
        for account_id, cfg in accounts.items()
    )

    legacy_account = {key: qqbot[key] for key in QQBOT_ACCOUNT_FIELDS if key in qqbot}
    if legacy_account and not has_structured_accounts:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in legacy_account.items():
            default_account.setdefault(key, value)
        accounts['default'] = default_account
        migrated = True

    normalized_accounts = {}
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_qqbot_account_config(cfg):
            pruned_cfg = {k: v for k, v in cfg.items() if k in QQBOT_ACCOUNT_FIELDS}
            normalized_accounts[account_id] = pruned_cfg

    if normalized_accounts:
        qqbot['accounts'] = normalized_accounts
        default_account_id = str(qqbot.get('defaultAccount') or 'default').strip() or 'default'
        if default_account_id not in normalized_accounts and 'default' in normalized_accounts:
            default_account_id = 'default'
        qqbot['defaultAccount'] = default_account_id

        migrated = True

    if migrated:
        print('✅ QQ 机器人配置已标准化为多账号结构')


def normalize_feishu_config(channels: dict) -> None:
    feishu = channels.get('feishu')
    if not isinstance(feishu, dict):
        return

    migrated = False
    accounts = feishu.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}

    has_structured_accounts = any(
        is_valid_account_id(account_id) and is_feishu_account_config(cfg)
        for account_id, cfg in accounts.items()
    )

    legacy_account = {key: feishu[key] for key in FEISHU_ACCOUNT_FIELDS if key in feishu}
    if legacy_account and not has_structured_accounts:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in legacy_account.items():
            default_account.setdefault(key, value)
        if 'name' not in default_account:
            default_account['name'] = feishu.get('name', 'OpenClaw Bot')
        accounts['default'] = default_account
        migrated = True

    main_account = accounts.pop('main', None) if 'main' in accounts else None
    if isinstance(main_account, dict):
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        for key, value in main_account.items():
            default_account.setdefault(key, value)
        accounts['default'] = default_account
        migrated = True

    normalized_accounts = {}
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_feishu_account_config(cfg):
            pruned_cfg = {k: v for k, v in cfg.items() if k in FEISHU_ACCOUNT_FIELDS}
            normalized_accounts[account_id] = pruned_cfg

    if normalized_accounts:
        feishu['accounts'] = normalized_accounts
        default_account_id = str(feishu.get('defaultAccount') or 'default').strip() or 'default'
        if default_account_id not in normalized_accounts and 'default' in normalized_accounts:
            default_account_id = 'default'
        feishu['defaultAccount'] = default_account_id
        default_account = normalized_accounts.get(default_account_id) or normalized_accounts.get('default')
        if isinstance(default_account, dict):
            if default_account.get('appId'):
                feishu['appId'] = default_account['appId']
            if default_account.get('appSecret'):
                feishu['appSecret'] = default_account['appSecret']
            if default_account.get('name'):
                feishu['name'] = default_account['name']

        for key in list(feishu.keys()):
            if key not in FEISHU_RESERVED_FIELDS:
                del feishu[key]

        groups = feishu.get('groups')
        if isinstance(groups, dict):
            for gid, gcfg in groups.items():
                if isinstance(gcfg, dict):
                    pruned_gcfg = {k: v for k, v in gcfg.items() if k in FEISHU_GROUP_FIELDS}
                    groups[gid] = pruned_gcfg

        migrated = migrated or feishu.get('accounts') != accounts

    if migrated:
        print('✅ 飞书配置已标准化为多账号结构')


def migrate_feishu_config(channels: dict) -> None:
    feishu = channels.get('feishu', {})
    if 'appId' in feishu and 'accounts' not in feishu:
        print('检测到飞书旧版格式，执行迁移...')
        feishu['accounts'] = {
            'default': {
                'appId': feishu.get('appId', ''),
                'appSecret': feishu.get('appSecret', ''),
                'name': feishu.get('name', 'OpenClaw Bot'),
            }
        }

    accounts = feishu.get('accounts')
    if isinstance(accounts, dict) and 'main' in accounts:
        print('检测到飞书 accounts.main，迁移为 accounts.default...')
        main_account = accounts.pop('main')
        default_account = accounts.get('default')
        if not isinstance(default_account, dict):
            accounts['default'] = main_account if isinstance(main_account, dict) else {}
        elif isinstance(main_account, dict):
            for key, value in main_account.items():
                default_account.setdefault(key, value)

    default_account = accounts.get('default') if isinstance(accounts, dict) else None
    if isinstance(default_account, dict):
        if default_account.get('appId'):
            feishu['appId'] = default_account['appId']
        if default_account.get('appSecret'):
            feishu['appSecret'] = default_account['appSecret']

    normalize_feishu_config(channels)

def merge_wecom_accounts_from_env(channels: dict, env: dict) -> None:
    wecom = channels.get('wecom')
    if not isinstance(wecom, dict):
        return

    accounts = wecom.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}
        wecom['accounts'] = accounts

    bot_id = env.get('WECOM_BOT_ID')
    secret = env.get('WECOM_SECRET')
    if bot_id and secret:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        default_account.setdefault('botId', bot_id)
        default_account.setdefault('secret', secret)
        accounts['default'] = default_account
        print(f'✅ 已合并 WECOM_BOT_ID/WECOM_SECRET 到 default 账号')

    admin_users = env.get('WECOM_ADMIN_USERS')
    if admin_users:
        wecom['adminUsers'] = parse_csv(admin_users)

    welcome_message = env.get('WECOM_WELCOME_MESSAGE')
    if welcome_message:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        default_account.setdefault('welcomeMessage', welcome_message)
        accounts['default'] = default_account

    send_thinking = parse_bool(env.get('WECOM_SEND_THINKING_MESSAGE'))
    default_account = accounts.get('default', {})
    if not isinstance(default_account, dict):
        default_account = {}
    default_account.setdefault('sendThinkingMessage', send_thinking)
    accounts['default'] = default_account


def merge_dingtalk_accounts_from_env(channels: dict, env: dict) -> None:
    dingtalk = channels.get('dingtalk')
    if not isinstance(dingtalk, dict):
        return

    accounts = dingtalk.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}
        dingtalk['accounts'] = accounts

    client_id = env.get('DINGTALK_CLIENT_ID')
    client_secret = env.get('DINGTALK_CLIENT_SECRET')
    robot_code = env.get('DINGTALK_ROBOT_CODE')
    corp_id = env.get('DINGTALK_CORP_ID')
    agent_id = env.get('DINGTALK_AGENT_ID')

    if client_id and client_secret and robot_code:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        default_account.setdefault('clientId', client_id)
        default_account.setdefault('clientSecret', client_secret)
        default_account.setdefault('robotCode', robot_code)
        if corp_id:
            default_account.setdefault('corpId', corp_id)
        if agent_id:
            default_account.setdefault('agentId', agent_id)
        accounts['default'] = default_account
        print(f'✅ 已合并钉钉快捷配置到 default 账号')


def merge_qqbot_accounts_from_env(channels: dict, env: dict) -> None:
    qqbot = channels.get('qqbot')
    if not isinstance(qqbot, dict):
        return

    accounts = qqbot.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}
        qqbot['accounts'] = accounts

    app_id = env.get('QQBOT_APP_ID')
    client_secret = env.get('QQBOT_CLIENT_SECRET')

    if app_id and client_secret:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        default_account.setdefault('appId', app_id)
        default_account.setdefault('clientSecret', client_secret)
        default_account.setdefault('enabled', True)
        accounts['default'] = default_account
        print(f'✅ 已合并 QQ 机器人快捷配置到 default 账号')


def merge_feishu_accounts_from_env(channels: dict, env: dict) -> None:
    feishu = channels.get('feishu')
    if not isinstance(feishu, dict):
        return

    accounts = feishu.get('accounts')
    if not isinstance(accounts, dict):
        accounts = {}
        feishu['accounts'] = accounts

    app_id = env.get('FEISHU_APP_ID')
    app_secret = env.get('FEISHU_APP_SECRET')
    name = env.get('FEISHU_NAME', 'OpenClaw Bot')

    if app_id and app_secret:
        default_account = accounts.get('default', {})
        if not isinstance(default_account, dict):
            default_account = {}
        default_account.setdefault('appId', app_id)
        default_account.setdefault('appSecret', app_secret)
        default_account.setdefault('name', name)
        accounts['default'] = default_account
        print(f'✅ 已合并飞书快捷配置到 default 账号')


def validate_wecom_multi_accounts(channels: dict) -> list:
    errors = []
    wecom = channels.get('wecom')
    if not isinstance(wecom, dict):
        return errors

    accounts = wecom.get('accounts')
    if not isinstance(accounts, dict):
        return errors

    for account_id, cfg in accounts.items():
        if not is_valid_account_id(account_id):
            errors.append(f'企业微信账号 ID 格式非法: {account_id}')
        if not is_wecom_account_config(cfg):
            errors.append(f'企业微信账号 {account_id} 配置缺少必要字段')

    return errors


def validate_dingtalk_multi_accounts(channels: dict) -> list:
    errors = []
    dingtalk = channels.get('dingtalk')
    if not isinstance(dingtalk, dict):
        return errors

    accounts = dingtalk.get('accounts')
    if not isinstance(accounts, dict):
        return errors

    for account_id, cfg in accounts.items():
        if not is_valid_account_id(account_id):
            errors.append(f'钉钉账号 ID 格式非法: {account_id}')
        if not is_dingtalk_account_config(cfg):
            errors.append(f'钉钉账号 {account_id} 配置缺少必要字段')

    return errors


def validate_qqbot_multi_accounts(channels: dict) -> list:
    errors = []
    qqbot = channels.get('qqbot')
    if not isinstance(qqbot, dict):
        return errors

    accounts = qqbot.get('accounts')
    if not isinstance(accounts, dict):
        return errors

    for account_id, cfg in accounts.items():
        if not is_valid_account_id(account_id):
            errors.append(f'QQ 机器人账号 ID 格式非法: {account_id}')
        if not is_qqbot_account_config(cfg):
            errors.append(f'QQ 机器人账号 {account_id} 配置缺少必要字段')

    return errors


def validate_feishu_multi_accounts(channels: dict) -> list:
    errors = []
    feishu = channels.get('feishu')
    if not isinstance(feishu, dict):
        return errors

    accounts = feishu.get('accounts')
    if not isinstance(accounts, dict):
        return errors

    for account_id, cfg in accounts.items():
        if not is_valid_account_id(account_id):
            errors.append(f'飞书账号 ID 格式非法: {account_id}')
        if not is_feishu_account_config(cfg):
            errors.append(f'飞书账号 {account_id} 配置缺少必要字段')

    return errors


def sync_wecom_channel(config: dict, env: dict) -> None:
    channels = config.setdefault('channels', {})
    wecom = channels.get('wecom')
    if not isinstance(wecom, dict):
        wecom = {}
        channels['wecom'] = wecom

    wecom.setdefault('enabled', True)
    wecom.setdefault('defaultAccount', 'open')

    default_account = wecom.get('accounts', {}).get('default', {})
    if not isinstance(default_account, dict):
        default_account = {}
        wecom.setdefault('accounts', {}).setdefault('default', default_account)

    default_account.setdefault('dmPolicy', env.get('WECOM_DM_POLICY', 'open'))
    default_account.setdefault('groupPolicy', env.get('WECOM_GROUP_POLICY', 'open'))
    default_account.setdefault('groupAllowFrom', parse_csv(env.get('WECOM_GROUP_ALLOW_FROM')))

    admin_users = env.get('WECOM_ADMIN_USERS')
    if admin_users:
        wecom['adminUsers'] = parse_csv(admin_users)

    commands_enabled = parse_bool(env.get('WECOM_COMMANDS_ENABLED'), True)
    if commands_enabled:
        commands = wecom.get('commands', {})
        commands.setdefault('enabled', True)
        allowlist_str = env.get('WECOM_COMMANDS_ALLOWLIST', '/new,/compact,/help,/status')
        commands.setdefault('allowlist', parse_csv(allowlist_str))
        wecom['commands'] = commands


def sync_feishu_channel(config: dict, env: dict) -> None:
    channels = config.setdefault('channels', {})
    feishu = channels.get('feishu')
    if not isinstance(feishu, dict):
        feishu = {}
        channels['feishu'] = feishu

    feishu.setdefault('enabled', True)
    feishu.setdefault('defaultAccount', env.get('FEISHU_DEFAULT_ACCOUNT', 'default'))

    default_account = feishu.get('accounts', {}).get('default', {})
    if not isinstance(default_account, dict):
        default_account = {}
        feishu.setdefault('accounts', {}).setdefault('default', default_account)

    default_account.setdefault('dmPolicy', env.get('FEISHU_DM_POLICY', 'open'))
    default_account.setdefault('groupPolicy', env.get('FEISHU_GROUP_POLICY', 'open'))

    streaming = parse_bool(env.get('FEISHU_STREAMING'), True)
    default_account.setdefault('streaming', streaming)

    require_mention = parse_bool(env.get('FEISHU_REQUIRE_MENTION'), True)
    default_account.setdefault('requireMention', require_mention)

    if parse_bool(env.get('FEISHU_OFFICIAL_PLUGIN_ENABLED')):
        feishu['officialPlugin'] = {'enabled': True}


def sync_dingtalk_channel(config: dict, env: dict) -> None:
    channels = config.setdefault('channels', {})
    dingtalk = channels.get('dingtalk')
    if not isinstance(dingtalk, dict):
        dingtalk = {}
        channels['dingtalk'] = dingtalk

    dingtalk.setdefault('enabled', True)
    dingtalk.setdefault('defaultAccount', 'default')

    default_account = dingtalk.get('accounts', {}).get('default', {})
    if not isinstance(default_account, dict):
        default_account = {}
        dingtalk.setdefault('accounts', {}).setdefault('default', default_account)

    default_account.setdefault('dmPolicy', env.get('DINGTALK_DM_POLICY', 'open'))
    default_account.setdefault('groupPolicy', env.get('DINGTALK_GROUP_POLICY', 'open'))
    default_account.setdefault('messageType', env.get('DINGTALK_MESSAGE_TYPE', 'markdown'))


def sync_qqbot_channel(config: dict, env: dict) -> None:
    channels = config.setdefault('channels', {})
    qqbot = channels.get('qqbot')
    if not isinstance(qqbot, dict):
        qqbot = {}
        channels['qqbot'] = qqbot

    qqbot.setdefault('enabled', True)
    qqbot.setdefault('defaultAccount', 'default')

    default_account = qqbot.get('accounts', {}).get('default', {})
    if not isinstance(default_account, dict):
        default_account = {}
        qqbot.setdefault('accounts', {}).setdefault('default', default_account)

    default_account.setdefault('enabled', True)
    default_account.setdefault('dmPolicy', env.get('QQBOT_DM_POLICY', 'open'))
    default_account.setdefault('groupPolicy', env.get('QQBOT_GROUP_POLICY', 'open'))


def normalize_all_channels(channels: dict) -> None:
    normalize_wecom_config(channels)
    normalize_dingtalk_config(channels)
    normalize_qqbot_config(channels)
    normalize_feishu_config(channels)


def merge_all_accounts_from_env(channels: dict, env: dict) -> None:
    merge_wecom_accounts_from_env(channels, env)
    merge_dingtalk_accounts_from_env(channels, env)
    merge_qqbot_accounts_from_env(channels, env)
    merge_feishu_accounts_from_env(channels, env)


def validate_all_channels(channels: dict) -> list:
    errors = []
    errors.extend(validate_wecom_multi_accounts(channels))
    errors.extend(validate_dingtalk_multi_accounts(channels))
    errors.extend(validate_qqbot_multi_accounts(channels))
    errors.extend(validate_feishu_multi_accounts(channels))
    return errors