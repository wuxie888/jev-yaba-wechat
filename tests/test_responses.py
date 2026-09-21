"""Offline transport contract checks. No keychain, real credentials, or network."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import generate

class ResponsesContract(unittest.TestCase):
    def call(self, data):
        creds=('https://easyai.autos', 'synthetic-test-key', 'gpt5.6', 'test', 'responses')
        with patch.object(generate, 'load_credentials', return_value=creds), patch.object(generate.Generator, '_post', return_value=data) as post:
            result=generate.Generator()._call('这是虚构的测试消息')
            return result, post.call_args.args

    def test_response_message_and_endpoint(self):
        result, (url, headers, body)=self.call({'status':'completed','output':[
            {'type':'reasoning','summary':[{'type':'summary_text','text':'不要作为候选'}]},
            {'type':'message','content':[{'type':'output_text','text':'收到，我看一下。\n好，我确认后回复你。'}]}]})
        self.assertEqual(url, 'https://easyai.autos/responses')
        self.assertEqual(generate.Generator._parse(result), ['收到，我看一下。','好，我确认后回复你。'])
        self.assertFalse(body['store'])
        self.assertNotIn('temperature',body)
        self.assertNotIn('max_tokens',body)

    def test_endpoint_variants(self):
        for base, expected in [('https://api.openai.com/v1','https://api.openai.com/v1/responses'),
                               ('https://example.com/responses/','https://example.com/responses')]:
            with self.subTest(base=base):
                self.assertEqual(generate._endpoint(base,'responses'),expected)

    def test_incomplete_or_reasoning_only_fails(self):
        for data in [{'status':'incomplete','output':[]}, {'status':'completed','output':[{'type':'reasoning'}]},
                     {'error':{'message':'synthetic failure'}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.call(data)

    def test_http_failure_is_not_replaced_by_sample(self):
        creds=('https://example.com','synthetic-test-key','gpt-test','test','responses')
        with patch.object(generate,'load_credentials',return_value=creds), patch.object(generate.Generator,'_post',side_effect=TimeoutError('synthetic timeout')):
            with self.assertRaises(TimeoutError):
                generate.Generator()._call('synthetic')

    def test_legacy_chat_endpoint_preserved(self):
        self.assertEqual(generate._endpoint('https://example.com/v1','openai'),'https://example.com/v1/chat/completions')

    def test_reasoning_only_errors_reach_panel_for_all_transports(self):
        fixtures = {
            'responses': {'status': 'incomplete', 'output': [{'type': 'reasoning'}]},
            'openai': {'choices': [{'message': {'content': '', 'reasoning_content': 'private reasoning'}}]},
            'anthropic': {'content': [{'type': 'thinking', 'thinking': 'private reasoning'}]},
        }
        for api, data in fixtures.items():
            with self.subTest(api=api):
                creds = ('https://example.com/v1', 'synthetic-test-key', 'gpt-test', 'test', api)
                with patch.object(generate, 'load_credentials', return_value=creds), patch.object(generate.Generator, '_post', return_value=data):
                    result = generate.Generator().generate('虚构消息', slot_tones=list(generate.styles.BUILTIN)[:2])
                self.assertTrue(all(not group['texts'] for group in result['groups']))
                self.assertIn('gpt-test', result['error'])
                self.assertIn('未生成回复正文', result['error'])
                self.assertNotIn('private reasoning', result['error'])
                self.assertNotIn('deepseek', result['error'].lower())
                self.assertEqual(result['error'].count('gpt-test'), 1)

    def test_incomplete_response_never_becomes_sendable_candidate(self):
        with self.assertRaises(ValueError):
            self.call({'status': 'incomplete', 'output': [
                {'type': 'message', 'content': [{'type': 'output_text', 'text': '尚未完成的回复'}]}]})

    def test_chat_answer_excludes_reasoning_and_keeps_text(self):
        creds = ('https://example.com/v1', 'synthetic-test-key', 'gpt-test', 'test', 'openai')
        data = {'choices': [{'message': {'content': '收到，我确认一下。', 'reasoning': 'private reasoning'}}]}
        with patch.object(generate, 'load_credentials', return_value=creds), patch.object(generate.Generator, '_post', return_value=data):
            self.assertEqual(generate.Generator()._call('虚构消息'), '收到，我确认一下。')

if __name__ == '__main__':
    unittest.main()
