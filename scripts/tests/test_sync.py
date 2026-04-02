import pytest
import json
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from openclaw_config.sync import load_config, save_config, sync_config


def test_load_config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"test": "value"}, f)
        f.flush()
        
        config = load_config(f.name)
        assert config["test"] == "value"
        
        os.unlink(f.name)


def test_save_config():
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        path = f.name
    
    config = {"test": "save"}
    save_config(path, config)
    
    with open(path) as f:
        loaded = json.load(f)
    
    assert loaded["test"] == "save"
    os.unlink(path)


def test_sync_config_dry_run(monkeypatch):
    monkeypatch.setenv("MODEL_ID", "gpt-4")
    monkeypatch.setenv("BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("API_KEY", "test-key")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"agents": {"defaults": {"model": {}}}}, f)
        f.flush()
        
        sync_config(f.name, dry_run=True)
        
        with open(f.name) as f2:
            result = json.load(f2)
        
        assert result["agents"]["defaults"]["model"].get("model") is None
        
        os.unlink(f.name)