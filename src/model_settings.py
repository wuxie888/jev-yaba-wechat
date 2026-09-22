"""Settings persistence and explicit, synthetic provider connection probes."""
from __future__ import annotations

import os
import re
import socket
import tempfile
import time
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit

import userconfig

KEYS = ('OPENAI_BASE_URL', 'OPENAI_MODEL', 'OPENAI_API_KEY', 'OPENAI_API_FORMAT',
        'TYPESAFE_BASE_URL', 'TYPESAFE_MODEL', 'TYPESAFE_API_KEY', 'JEV_READ_ONLY')
DEFAULTS = {'OPENAI_BASE_URL': 'https://api.openai.com/v1', 'OPENAI_MODEL': '',
            'OPENAI_API_FORMAT': 'responses', 'TYPESAFE_BASE_URL': 'https://api.typesafe.ai',
            'TYPESAFE_MODEL': 'jev-latest', 'JEV_READ_ONLY': '1'}


def current() -> dict[str, str]:
    values = {key: userconfig.get(key) or DEFAULTS.get(key, '') for key in KEYS}
    # Fresh installations open settings/preview before starting any model download.
    flag = userconfig.get('JEV_READ_ONLY')
    has_provider = any(userconfig.get(k) for k in ('OPENAI_API_KEY', 'TYPESAFE_API_KEY', 'ANTHROPIC_API_KEY'))
    values['JEV_READ_ONLY'] = '1' if flag == '1' or (not flag and not has_provider) else '0'
    return values


def validate(values: dict[str, str], provider: str | None = None) -> None:
    prefixes = [provider] if provider else ['OPENAI', 'TYPESAFE']
    for key, value in values.items():
        if any(c in value for c in ('\n', '\r', '\x00')) or "'" in value:
            raise ValueError('配置不能包含换行或单引号。')
    for prefix in prefixes:
        label = 'GPT' if prefix == 'OPENAI' else 'Jev'
        base = values.get(prefix + '_BASE_URL', '').strip()
        url = urlsplit(base)
        if base and (url.scheme not in ('http', 'https') or not url.hostname or url.username
                     or url.password or url.query or url.fragment):
            raise ValueError(f'{label} 基础地址需为 http(s) 地址，不包含账号、查询参数或片段。')
        if provider or values.get('JEV_READ_ONLY') != '1':
            for suffix, name in (('BASE_URL', '基础地址'), ('MODEL', '模型名称'), ('API_KEY', 'API Key')):
                if not values.get(prefix + '_' + suffix, '').strip():
                    raise ValueError(f'请填写 {label} 的{name}。')
    if values.get('OPENAI_API_FORMAT', 'responses') not in ('responses', 'openai'):
        raise ValueError('请选择 Responses 或 Chat Completions。')


def save(values: dict[str, str], path: Path | None = None) -> None:
    """Replace managed keys atomically, retaining unrelated settings and comments."""
    validate(values)
    path = path or userconfig.ENV_FILE
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = path.read_text() if path.exists() else ''
    kept = []
    for line in existing.splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=', line)
        if not match or match.group(1) not in KEYS:
            kept.append(line)
    for key in KEYS:
        value = values.get(key, '').strip()
        kept.append(f"export {key}='{value}'")
    fd, name = tempfile.mkstemp(prefix='.env-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            os.fchmod(out.fileno(), 0o600)
            out.write('\n'.join(kept) + '\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def probe(provider: str, values: dict[str, str]) -> str:
    """Use the form snapshot, never environment mutation or a fallback model."""
    validate(values, provider)
    start = time.monotonic()
    if provider == 'OPENAI':
        from generate import Generator
        creds = (values['OPENAI_BASE_URL'], values['OPENAI_API_KEY'], values['OPENAI_MODEL'],
                 'settings test', values['OPENAI_API_FORMAT'])
        text = Generator(credentials=creds)._call('这是连接测试。请只回复：连接成功。')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('接口返回了空内容，尚未验证成功。')
        label = 'GPT 已返回回复正文'
    else:
        from judge_jev import JevJudge
        j = JevJudge(base=values['TYPESAFE_BASE_URL'], key=values['TYPESAFE_API_KEY'],
                     model=values['TYPESAFE_MODEL'])
        data = j._post({'model': j.model, 'state': '这是连接测试，请选择连接成功。',
                        'questions': {'connection': {'type': 'choice',
                         'instructions': '请选择连接成功。', 'criteria': {'连接成功': None, '失败': None}}}})
        answer = (data.get('answers') or {}).get('connection') or {}
        if answer.get('choice') != '连接成功':
            raise ValueError('接口没有返回有效的 Jev 判断结果，请检查地址、模型和接口兼容性。')
        label = 'Jev 已返回判断结果'
    return f'测试通过 · {label} · {time.monotonic() - start:.1f} 秒'


def failure_message(error: Exception) -> str:
    # Never expose raw server bodies, URLs or exception strings: they may echo credentials.
    if isinstance(error, urllib.error.HTTPError):
        hints = {401: '认证失败，请检查 Key 是否有效、是否属于此服务。',
                 403: '没有调用权限，请检查模型权限。', 404: '接口或模型未找到，请检查地址和模型名。',
                 429: '额度不足或请求过多，请检查服务商账户。'}
        return f'HTTP {error.code} · ' + hints.get(error.code, '服务暂时无法完成请求。')
    if isinstance(error, (TimeoutError, socket.timeout)):
        return '连接超时，请稍后重试。'
    if isinstance(error, urllib.error.URLError):
        return '网络连接失败，请检查网络和基础地址。'
    return '返回内容无法验证，请检查模型、接口格式和服务兼容性。'
