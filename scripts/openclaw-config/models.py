from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModelConfig:
    model_id: str
    base_url: str
    api_key: str
    protocol: str = "openai-completions"
    context_window: int = 200000
    max_tokens: int = 8192


@dataclass
class ChannelConfig:
    enabled: bool = True
    dm_policy: str = "open"
    group_policy: str = "open"
    allow_from: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class OpenClawConfig:
    model: Optional[ModelConfig] = None
    channels: dict = field(default_factory=dict)


import re
from typing import Any, Optional


WECOM_ACCOUNT_ID_RE = re.compile(r'^[a-z0-9_-]+$')

FEISHU_ACCOUNT_FIELDS = {
    'appId', 'appSecret', 'name'
}
FEISHU_GROUP_FIELDS = {
    'requireMention'
}
FEISHU_RESERVED_FIELDS = {
    'enabled', 'appId', 'appSecret', 'dmPolicy', 'allowFrom', 'groupPolicy',
    'groupAllowFrom', 'streaming', 'requireMention', 'defaultAccount',
    'accounts', 'groups'
}

DINGTALK_ACCOUNT_FIELDS = {
    'clientId', 'clientSecret', 'robotCode', 'corpId', 'agentId', 'dmPolicy',
    'allowFrom', 'groupPolicy', 'messageType', 'cardTemplateId', 'cardTemplateKey',
    'maxReconnectCycles', 'debug'
}
DINGTALK_RESERVED_FIELDS = {
    'enabled', 'clientId', 'clientSecret', 'robotCode', 'corpId', 'agentId',
    'dmPolicy', 'allowFrom', 'groupPolicy', 'messageType', 'cardTemplateId',
    'cardTemplateKey', 'maxReconnectCycles', 'debug', 'journalTTLDays',
    'showThinking', 'thinkingMessage', 'asyncMode', 'asyncAckText', 'accounts'
}

WECOM_ACCOUNT_FIELDS = {
    'botId', 'secret', 'dmPolicy', 'allowFrom', 'groupPolicy', 'groupAllowFrom',
    'welcomeMessage', 'sendThinkingMessage', 'agent', 'webhooks', 'network',
    'groupChat', 'dm', 'workspaceTemplate'
}
WECOM_RESERVED_FIELDS = {'enabled', 'defaultAccount', 'adminUsers', 'commands', 'dynamicAgents'}

QQBOT_ACCOUNT_FIELDS = {'appId', 'clientSecret', 'enabled'}
QQBOT_RESERVED_FIELDS = {'enabled', 'appId', 'clientSecret', 'dmPolicy', 'allowFrom', 'groupPolicy', 'accounts'}

CHANNEL_INSTALLS = {
    'feishu': {'source': 'npm', 'spec': '@openclaw/feishu', 'installPath': '/home/node/.openclaw/extensions/feishu'},
    'dingtalk': {'source': 'npm', 'spec': 'https://github.com/soimy/clawdbot-channel-dingtalk.git', 'installPath': '/home/node/.openclaw/extensions/dingtalk'},
    'openclaw-qqbot': {'source': 'path', 'sourcePath': '/home/node/.openclaw/openclaw-qqbot', 'installPath': '/home/node/.openclaw/extensions/openclaw-qqbot'},
    'napcat': {'source': 'path', 'sourcePath': '/home/node/.openclaw/extensions/napcat', 'installPath': '/home/node/.openclaw/extensions/napcat'},
    'wecom': {'source': 'npm', 'spec': '@sunnoy/wecom', 'installPath': '/home/node/.openclaw/extensions/wecom'},
}


def is_valid_account_id(account_id: str) -> bool:
    return WECOM_ACCOUNT_ID_RE.match(str(account_id)) is not None


def is_feishu_account_config(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in FEISHU_ACCOUNT_FIELDS)


def is_dingtalk_account_config(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in DINGTALK_ACCOUNT_FIELDS)


def is_wecom_account_config(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in WECOM_ACCOUNT_FIELDS)


def is_qqbot_account_config(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in QQBOT_ACCOUNT_FIELDS)


def get_feishu_accounts(feishu: dict) -> list:
    if not isinstance(feishu, dict):
        return []
    accounts = feishu.get('accounts')
    if not isinstance(accounts, dict):
        return []
    result = []
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_feishu_account_config(cfg):
            result.append((account_id, cfg))
    return result


def get_dingtalk_accounts(dingtalk: dict) -> list:
    if not isinstance(dingtalk, dict):
        return []
    accounts = dingtalk.get('accounts')
    if not isinstance(accounts, dict):
        return []
    result = []
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_dingtalk_account_config(cfg):
            result.append((account_id, cfg))
    return result


def get_wecom_accounts(wecom: dict) -> list:
    if not isinstance(wecom, dict):
        return []
    accounts = []
    for account_id, cfg in wecom.items():
        if account_id in WECOM_RESERVED_FIELDS:
            continue
        if is_wecom_account_config(cfg):
            accounts.append((account_id, cfg))
    return accounts


def get_qqbot_accounts(qqbot: dict) -> list:
    if not isinstance(qqbot, dict):
        return []
    accounts = qqbot.get('accounts')
    if not isinstance(accounts, dict):
        return []
    result = []
    for account_id, cfg in accounts.items():
        if is_valid_account_id(account_id) and is_qqbot_account_config(cfg):
            result.append((account_id, cfg))
    return result