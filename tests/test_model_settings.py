"""Configuration round trips and truthful provider probes; no real credentials/network."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import generate
import judge_jev
import model_settings as settings
import userconfig


def form():
    return dict(settings.DEFAULTS, OPENAI_MODEL='gpt-test', OPENAI_API_KEY='synthetic-gpt',
                TYPESAFE_API_KEY='synthetic-jev', JEV_READ_ONLY='1')


class SettingsContracts(unittest.TestCase):
    def test_fresh_install_starts_preview_without_model_credentials(self):
        with patch.object(userconfig, 'get', return_value=''):
            self.assertEqual(settings.current()['JEV_READ_ONLY'], '1')
        with patch.object(userconfig, 'get', side_effect=lambda key: 'synthetic' if key == 'OPENAI_API_KEY' else ''):
            self.assertEqual(settings.current()['JEV_READ_ONLY'], '0')

    def test_save_keeps_unrelated_values_and_masks_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'env'
            path.write_text('# keep comment\nexport JEV_TONES="自定义风格"\nOPENAI_API_KEY=old\n')
            values = form()
            # These shell metacharacters must be stored as literal text, never executed.
            values['OPENAI_API_KEY'] = 'synthetic-$HOME-`echo bad`-$(echo bad)#abc'
            settings.save(values, path)
            loaded = userconfig.parse_env_file(path)
            for key in settings.KEYS:
                self.assertEqual(loaded[key], values.get(key, ''))
            self.assertEqual(loaded['JEV_TONES'], '自定义风格')
            self.assertIn('# keep comment', path.read_text())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(path.read_text().count('OPENAI_API_KEY='), 1)

    def test_failed_replace_keeps_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'env'
            path.write_text('original\n')
            with patch.object(settings.os, 'replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError):
                    settings.save(form(), path)
            self.assertEqual(path.read_text(), 'original\n')
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_missing_keys_allowed_in_preview_but_not_normal_or_probe(self):
        values = form()
        values['TYPESAFE_API_KEY'] = ''
        settings.validate(values)
        with self.assertRaises(ValueError):
            settings.validate(values, 'TYPESAFE')
        values['JEV_READ_ONLY'] = '0'
        with self.assertRaises(ValueError):
            settings.validate(values)

    def test_rejects_unsafe_config_and_credential_bearing_urls(self):
        for key, value in [('OPENAI_API_KEY', "a'\nb"),
                           ('OPENAI_BASE_URL', 'https://user:secret@example.com'),
                           ('OPENAI_BASE_URL', 'file:///tmp/private'),
                           ('OPENAI_BASE_URL', 'https://example.com?key=secret')]:
            values = dict(form(), **{key:value})
            with self.assertRaises(ValueError):
                settings.validate(values)

    def test_gpt_uses_unsaved_form_without_changing_environment(self):
        values = form()
        before = dict(os.environ)
        data = {'output':[{'type':'message', 'content':[{'type':'output_text','text':'连接成功。'}]}]}
        with patch.object(generate, 'load_credentials', side_effect=AssertionError('must use form')):
            with patch.object(generate.Generator, '_post', return_value=data) as post:
                self.assertIn('测试通过', settings.probe('OPENAI', values))
                url, headers, body = post.call_args.args
                self.assertEqual(headers['authorization'], 'Bearer synthetic-gpt')
                self.assertEqual(body['model'], 'gpt-test')
                self.assertNotIn('微信聊天', body['input'][0]['content'])
        self.assertEqual(dict(os.environ), before)

    def test_gpt_empty_or_incomplete_is_not_success(self):
        for data in ({}, {'status':'incomplete', 'output':[]}):
            with patch.object(generate.Generator, '_post', return_value=data):
                with self.assertRaises(ValueError):
                    settings.probe('OPENAI', form())

    def test_jev_must_return_real_structured_answer(self):
        with patch.object(judge_jev.JevJudge, '_post', return_value={'answers':{'connection':{'choice':'连接成功'}}}):
            self.assertIn('Jev 已返回判断结果', settings.probe('TYPESAFE', form()))
        for response in ({}, {'answers':{}}, {'answers':{'connection':{'choice':'失败'}}}):
            with patch.object(judge_jev.JevJudge, '_post', return_value=response):
                with self.assertRaises(ValueError):
                    settings.probe('TYPESAFE', form())

    def test_failure_message_never_echoes_server_secrets(self):
        error = HTTPError('https://secret.example', 401, 'synthetic-private-key', {}, None)
        message = settings.failure_message(error)
        self.assertIn('401', message)
        self.assertNotIn('secret', message)
        self.assertNotIn('synthetic-private-key', message)
        self.assertNotIn('private-key', settings.failure_message(ValueError('private-key')))


if __name__ == '__main__':
    unittest.main()
