def migrate_config(config: dict) -> dict:
    return config


def migrate_tts_config(config: dict) -> None:
    """Migrate legacy TTS config to new format if needed.

    Matches init_org.sh logic: detects old format where 'edge' key exists
    directly under tts and 'providers' is missing.
    """
    messages = config.get('messages')
    if not isinstance(messages, dict):
        return

    tts = messages.get('tts')
    if not isinstance(tts, dict):
        return

    # 检测旧版格式：tts 下直接包含 edge 且没有 providers
    if 'edge' not in tts or 'providers' in tts:
        return

    print('检测到旧版 TTS 配置格式，正在执行自动迁移...')
    old_edge = tts.pop('edge')
    if not isinstance(old_edge, dict):
        old_edge = {}

    provider = tts.get('provider', 'edge')
    providers = {
        'edge': {
            'voice': old_edge.get('voice', 'zh-CN-XiaoxiaoNeural'),
            'lang': old_edge.get('lang', 'zh-CN'),
            'outputFormat': old_edge.get('outputFormat', 'ogg-24khz-16bit-mono-opus'),
            'pitch': old_edge.get('pitch', '+0Hz'),
            'rate': old_edge.get('rate', '+0%'),
            'volume': old_edge.get('volume', '+0%'),
            'timeoutMs': old_edge.get('timeoutMs', 30000),
        }
    }

    tts['auto'] = tts.get('auto', 'off')
    tts['mode'] = tts.get('mode', 'final')
    tts['provider'] = provider
    tts['providers'] = providers
    print('✅ TTS 配置已自动迁移')