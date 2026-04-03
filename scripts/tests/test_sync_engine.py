"""
Tests for openclaw_config.sync_engine — the main sync pipeline.

Covers:
- sync_models (model providers, PRIMARY_MODEL, image model, memory, qmd)
- sync_agent_and_tools (sandbox, tools, dangerouslyAllowContainerNamespaceJoin auto-fix)
- sync_channels_and_plugins (channel rules, multi-account, plugin state)
- sync_gateway (port, bind, mode, auth)
- migrate_tts_config (old → new format)
- migrate_feishu_config (accounts.main → accounts.default)
- sync() end-to-end (full pipeline)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from openclaw_config.sync_engine import (
    sync_models, sync_agent_and_tools, sync_gateway,
    sync_channels_and_plugins, apply_channel_rules,
    apply_multi_account_plugin_state, apply_feishu_plugin_switch,
    finalize_plugins, migrate_qqbot_plugin_entry,
    SyncContext, is_openclaw_sync_enabled,
)
from openclaw_config.migrate import migrate_tts_config
from openclaw_config.channels import (
    migrate_feishu_config, normalize_feishu_config,
    merge_feishu_accounts_from_env, merge_dingtalk_accounts_from_env,
    merge_wecom_accounts_from_env, merge_qqbot_accounts_from_env,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_config(overrides=None):
    """Create a minimal valid openclaw.json config."""
    cfg = {
        "meta": {"lastTouchedVersion": "1.0.0"},
        "agents": {"defaults": {"model": {}, "sandbox": {}}},
        "channels": {},
        "plugins": {"entries": {}, "installs": {}},
        "memory": {"backend": "qmd"},
        "models": {"providers": {}},
        "tools": {},
    }
    if overrides:
        _deep_update(cfg, overrides)
    return cfg


def _deep_update(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v


def _make_ctx(config, env=None):
    """Create a SyncContext with optional env overrides."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return SyncContext(config, full_env)


# ── is_openclaw_sync_enabled ─────────────────────────────────────────────

class TestIsOpenclawSyncEnabled:
    def test_default_true(self):
        assert is_openclaw_sync_enabled({}) is True

    def test_explicit_true(self):
        assert is_openclaw_sync_enabled({"SYNC_OPENCLAW_CONFIG": "true"}) is True

    def test_explicit_false(self):
        assert is_openclaw_sync_enabled({"SYNC_OPENCLAW_CONFIG": "false"}) is False

    def test_zero_disables(self):
        assert is_openclaw_sync_enabled({"SYNC_OPENCLAW_CONFIG": "0"}) is False


# ── sync_models ──────────────────────────────────────────────────────────

class TestSyncModels:
    def test_sync_default_provider(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
        })
        sync_models(ctx)
        providers = config["models"]["providers"]
        assert "default" in providers
        assert providers["default"]["apiKey"] == "sk-test"
        assert providers["default"]["baseUrl"] == "https://api.example.com/v1"

    def test_sync_primary_model(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "PRIMARY_MODEL": "claude-3-5-sonnet",
        })
        sync_models(ctx)
        assert config["agents"]["defaults"]["model"]["primary"] == "default/claude-3-5-sonnet"

    def test_sync_image_model(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "IMAGE_MODEL_ID": "dall-e-3",
        })
        sync_models(ctx)
        assert config["agents"]["defaults"]["imageModel"]["primary"] == "default/dall-e-3"

    def test_sync_disabled(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {"SYNC_OPENCLAW_CONFIG": "false"})
        sync_models(ctx)
        assert config["models"]["providers"] == {}

    def test_memory_backend_setup(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
        })
        sync_models(ctx)
        memory = config["memory"]["qmd"]
        assert memory["includeDefaultMemory"] is True
        assert memory["sessions"]["enabled"] is True
        assert memory["limits"]["timeoutMs"] == 8000
        assert memory["update"]["onBoot"] is True

    def test_workspace_path(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "OPENCLAW_WORKSPACE_ROOT": "/data/openclaw",
        })
        sync_models(ctx)
        assert config["agents"]["defaults"]["workspace"] == "/data/openclaw/workspace"


# ── sync_agent_and_tools ─────────────────────────────────────────────────

class TestSyncAgentAndTools:
    def test_sandbox_mode(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_SANDBOX_MODE": "non-main",
            "OPENCLAW_SANDBOX_SCOPE": "session",
            "OPENCLAW_SANDBOX_WORKSPACE_ACCESS": "ro",
        })
        sync_agent_and_tools(ctx)
        sandbox = config["agents"]["defaults"]["sandbox"]
        assert sandbox["mode"] == "non-main"
        assert sandbox["scope"] == "session"
        assert sandbox["workspaceAccess"] == "ro"

    def test_sandbox_docker_image(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_SANDBOX_MODE": "all",
            "OPENCLAW_SANDBOX_DOCKER_IMAGE": "my-sandbox:latest",
        })
        sync_agent_and_tools(ctx)
        docker = config["agents"]["defaults"]["sandbox"]["docker"]
        assert docker["image"] == "my-sandbox:latest"

    def test_sandbox_join_network_auto_fix(self, monkeypatch, capsys):
        """When sandbox network is container:HOSTNAME, auto-set dangerouslyAllowContainerNamespaceJoin."""
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_SANDBOX_MODE": "all",
            "OPENCLAW_SANDBOX_JOIN_NETWORK": "true",
            "HOSTNAME": "test-container-123",
        })
        sync_agent_and_tools(ctx)
        docker = config["agents"]["defaults"]["sandbox"]["docker"]
        assert docker["network"] == "container:test-container-123"
        assert docker["dangerouslyAllowContainerNamespaceJoin"] is True

    def test_sandbox_json_merge(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_SANDBOX_JSON": json.dumps({"docker": {"shmSize": "2g"}}),
        })
        sync_agent_and_tools(ctx)
        docker = config["agents"]["defaults"]["sandbox"]["docker"]
        assert docker["shmSize"] == "2g"

    def test_tools_defaults(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {})
        sync_agent_and_tools(ctx)
        tools = config["tools"]
        assert tools["profile"] == "full"
        assert tools["sessions"]["visibility"] == "all"
        assert tools["fs"]["workspaceOnly"] is True

    def test_tools_json_override(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_TOOLS_JSON": json.dumps({"fs": {"workspaceOnly": False}}),
        })
        sync_agent_and_tools(ctx)
        assert config["tools"]["fs"]["workspaceOnly"] is False


# ── sync_gateway ─────────────────────────────────────────────────────────

class TestSyncGateway:
    def test_gateway_with_token(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_GATEWAY_TOKEN": "gw-secret",
            "OPENCLAW_GATEWAY_PORT": "18790",
            "OPENCLAW_GATEWAY_BIND": "127.0.0.1",
            "OPENCLAW_GATEWAY_MODE": "remote",
        })
        sync_gateway(ctx)
        gw = config["gateway"]
        assert gw["port"] == 18790
        assert gw["bind"] == "127.0.0.1"
        assert gw["mode"] == "remote"
        assert gw["auth"]["token"] == "gw-secret"

    def test_gateway_no_token(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {})
        sync_gateway(ctx)
        assert "gateway" not in config

    def test_gateway_control_ui(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "OPENCLAW_GATEWAY_TOKEN": "gw-secret",
            "OPENCLAW_GATEWAY_ALLOWED_ORIGINS": "http://localhost,http://example.com",
        })
        sync_gateway(ctx)
        ctrl = config["gateway"]["controlUi"]
        assert ctrl["allowInsecureAuth"] is True
        assert ctrl["allowedOrigins"] == ["http://localhost", "http://example.com"]


# ── sync_channels_and_plugins ────────────────────────────────────────────

class TestSyncChannelsAndPlugins:
    def test_feishu_channel_enabled(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "FEISHU_APP_ID": "cli_test123",
            "FEISHU_APP_SECRET": "secret_test123",
        })
        sync_channels_and_plugins(ctx)
        feishu = config["channels"].get("feishu", {})
        assert feishu.get("enabled") is True
        assert feishu.get("appId") == "cli_test123"
        assert "feishu" in config["plugins"]["allow"]

    def test_dingtalk_channel_enabled(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "DINGTALK_CLIENT_ID": "ding-test",
            "DINGTALK_CLIENT_SECRET": "ding-secret",
            "DINGTALK_ROBOT_CODE": "robot-1",
        })
        sync_channels_and_plugins(ctx)
        dingtalk = config["channels"].get("dingtalk", {})
        assert dingtalk.get("enabled") is True
        assert dingtalk.get("clientId") == "ding-test"

    def test_qqbot_channel_enabled(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "QQBOT_APP_ID": "qq-app",
            "QQBOT_CLIENT_SECRET": "qq-secret",
        })
        sync_channels_and_plugins(ctx)
        qqbot = config["channels"].get("qqbot", {})
        assert qqbot.get("enabled") is True
        assert qqbot.get("appId") == "qq-app"

    def test_wecom_channel_enabled(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "WECOM_BOT_ID": "wecom-bot",
            "WECOM_SECRET": "wecom-secret",
        })
        sync_channels_and_plugins(ctx)
        wecom = config["channels"].get("wecom", {})
        assert wecom.get("enabled") is True

    def test_channels_disabled_without_env(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {})
        sync_channels_and_plugins(ctx)
        # No channels should be in the allow list
        assert config["plugins"]["allow"] == []

    def test_finalize_plugins_allow(self, monkeypatch, capsys):
        config = _make_config()
        ctx = _make_ctx(config, {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret_test",
        })
        sync_channels_and_plugins(ctx)
        assert "feishu" in config["plugins"]["allow"]


# ── migrate_tts_config ───────────────────────────────────────────────────

class TestMigrateTtsConfig:
    def test_migrate_old_edge_format(self):
        config = {"messages": {"tts": {"edge": {"voice": "zh-CN-Yunxi"}}}}
        migrate_tts_config(config)
        tts = config["messages"]["tts"]
        assert "edge" not in tts
        assert "providers" in tts
        assert "edge" in tts["providers"]
        assert tts["providers"]["edge"]["voice"] == "zh-CN-Yunxi"
        assert tts["mode"] == "final"
        assert tts["auto"] == "off"

    def test_skip_new_format(self):
        config = {"messages": {"tts": {
            "auto": "off", "mode": "final", "provider": "edge",
            "providers": {"edge": {"voice": "zh-CN-Xiaoxiao"}},
        }}}
        migrate_tts_config(config)
        # Should remain unchanged
        assert "providers" in config["messages"]["tts"]

    def test_skip_no_messages(self):
        config = {}
        migrate_tts_config(config)  # should not raise
        assert "messages" not in config

    def test_skip_no_tts(self):
        config = {"messages": {"ackReactionScope": "group-mentions"}}
        migrate_tts_config(config)  # should not raise


# ── migrate_feishu_config ────────────────────────────────────────────────

class TestMigrateFeishuConfig:
    def test_migrate_main_to_default(self):
        channels = {"feishu": {
            "appId": "cli_123",
            "appSecret": "secret_123",
            "name": "Test Bot",
            "accounts": {"main": {"appId": "cli_main", "appSecret": "s1"}},
        }}
        migrate_feishu_config(channels)
        feishu = channels["feishu"]
        assert "main" not in feishu.get("accounts", {})
        assert "default" in feishu.get("accounts", {})

    def test_migrate_old_format_to_accounts(self):
        channels = {"feishu": {
            "appId": "cli_123",
            "appSecret": "secret_123",
        }}
        migrate_feishu_config(channels)
        feishu = channels["feishu"]
        assert "accounts" in feishu
        assert feishu["accounts"]["default"]["appId"] == "cli_123"


# ── migrate_qqbot_plugin_entry ───────────────────────────────────────────

class TestMigrateQqbotPluginEntry:
    def test_migrate_legacy_to_official(self):
        config = _make_config()
        config["plugins"]["entries"]["qqbot"] = {"enabled": True}
        config["plugins"]["installs"]["qqbot"] = {
            "source": "path",
            "sourcePath": "/old/path",
            "installPath": "/old/install",
        }
        ctx = _make_ctx(config, {})
        migrate_qqbot_plugin_entry(ctx)
        assert "qqbot" not in config["plugins"]["entries"]
        assert "openclaw-qqbot" in config["plugins"]["entries"]
        assert config["plugins"]["entries"]["openclaw-qqbot"]["enabled"] is True
        assert config["plugins"]["installs"]["openclaw-qqbot"]["sourcePath"] == "/home/node/.openclaw/openclaw-qqbot"


# ── merge_*_accounts_from_env ────────────────────────────────────────────

class TestMergeAccountsFromEnv:
    def test_merge_feishu_single(self):
        channels = {"feishu": {}}
        merge_feishu_accounts_from_env(channels, {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret",
        })
        assert channels["feishu"]["accounts"]["default"]["appId"] == "cli_test"

    def test_merge_dingtalk_single(self):
        channels = {"dingtalk": {}}
        merge_dingtalk_accounts_from_env(channels, {
            "DINGTALK_CLIENT_ID": "ding",
            "DINGTALK_CLIENT_SECRET": "sec",
            "DINGTALK_ROBOT_CODE": "robot",
        })
        assert channels["dingtalk"]["accounts"]["default"]["clientId"] == "ding"

    def test_merge_wecom_single(self):
        channels = {"wecom": {}}
        merge_wecom_accounts_from_env(channels, {
            "WECOM_BOT_ID": "bot1",
            "WECOM_SECRET": "sec1",
        })
        assert channels["wecom"]["accounts"]["default"]["botId"] == "bot1"

    def test_merge_qqbot_single(self):
        channels = {"qqbot": {}}
        merge_qqbot_accounts_from_env(channels, {
            "QQBOT_APP_ID": "qq1",
            "QQBOT_CLIENT_SECRET": "sec1",
        })
        assert channels["qqbot"]["accounts"]["default"]["appId"] == "qq1"


# ── End-to-end: sync() via subprocess ────────────────────────────────────

class TestSyncEndToEnd:
    """Full pipeline test matching init-config.sh call pattern."""

    def _run_sync(self, config, env_overrides=None):
        """Write config, run sync via subprocess, return written config."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, f)
        f.close()

        env = os.environ.copy()
        env["CONFIG_FILE"] = f.name
        env["PYTHONPATH"] = str(SCRIPTS_DIR)
        if env_overrides:
            env.update(env_overrides)

        result = subprocess.run(
            [sys.executable, "-m", "openclaw_config", "sync"],
            capture_output=True, text=True, env=env, cwd=str(SCRIPTS_DIR),
        )

        with open(f.name) as cf:
            written = json.load(cf)
        os.unlink(f.name)
        return result.returncode, written, result.stdout, result.stderr

    def test_full_sync_with_feishu(self):
        rc, cfg, stdout, stderr = self._run_sync(_make_config(), {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret_test",
        })
        assert rc == 0
        assert "default" in cfg["models"]["providers"]
        assert cfg["channels"]["feishu"]["enabled"] is True
        assert "feishu" in cfg["plugins"]["allow"]
        assert "lastTouchedAt" in cfg["meta"]

    def test_full_sync_with_gateway(self):
        rc, cfg, stdout, stderr = self._run_sync(_make_config(), {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "OPENCLAW_GATEWAY_TOKEN": "gw-secret",
            "OPENCLAW_GATEWAY_PORT": "19999",
            "OPENCLAW_GATEWAY_MODE": "remote",
        })
        assert rc == 0
        assert cfg["gateway"]["port"] == 19999
        assert cfg["gateway"]["mode"] == "remote"
        assert cfg["gateway"]["auth"]["token"] == "gw-secret"

    def test_full_sync_with_tts_migration(self):
        cfg = _make_config()
        cfg["messages"] = {"tts": {"edge": {"voice": "zh-CN-Yunxi"}}}
        rc, written, stdout, stderr = self._run_sync(cfg, {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
        })
        assert rc == 0
        tts = written["messages"]["tts"]
        assert "providers" in tts
        assert "edge" not in tts
        assert tts["providers"]["edge"]["voice"] == "zh-CN-Yunxi"

    def test_full_sync_disabled(self):
        rc, cfg, stdout, stderr = self._run_sync(_make_config(), {
            "SYNC_OPENCLAW_CONFIG": "false",
        })
        assert rc == 0
        # No models should be synced
        assert cfg["models"]["providers"] == {}

    def test_full_sync_with_sandbox(self):
        rc, cfg, stdout, stderr = self._run_sync(_make_config(), {
            "MODEL_ID": "gpt-4o",
            "BASE_URL": "https://api.example.com/v1",
            "API_KEY": "sk-test",
            "OPENCLAW_SANDBOX_MODE": "all",
            "OPENCLAW_SANDBOX_JOIN_NETWORK": "true",
            "HOSTNAME": "test-host",
        })
        assert rc == 0
        sandbox = cfg["agents"]["defaults"]["sandbox"]
        assert sandbox["mode"] == "all"
        assert sandbox["docker"]["network"] == "container:test-host"
        assert sandbox["docker"]["dangerouslyAllowContainerNamespaceJoin"] is True
