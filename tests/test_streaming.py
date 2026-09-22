"""Offline Chat Completions SSE regressions, with no real credentials/network."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import generate

class Streaming(unittest.TestCase):
    def response(self, events, ctype='text/event-stream'):
        body = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events) + 'data: [DONE]\n'
        response = io.BytesIO(body.encode())
        response.headers = {'content-type': ctype}
        return response

    def test_only_answer_deltas_reach_callback(self):
        events = [{'choices':[{'delta':d}]} for d in [
            {'reasoning_content':'private reasoning'}, {'content':'收到，'}, {'content':'我看看。\n'}]]
        seen = []
        with patch.object(generate.urllib.request, 'urlopen', return_value=self.response(events)):
            result = generate.Generator(credentials=('https://example.com','test','gpt','test','openai'))._call('test', seen.append)
        self.assertEqual(result, '收到，我看看。\n')
        self.assertEqual(seen, ['收到，', '我看看。\n'])

    def test_reasoning_only_is_not_a_reply(self):
        events = [{'choices':[{'delta':{'reasoning':'private reasoning'}}]}]
        with patch.object(generate.urllib.request, 'urlopen', return_value=self.response(events)):
            with self.assertRaises(generate.ThinkingOnlyError):
                generate.Generator(credentials=('https://example.com','test','gpt','test','openai'))._call('test', lambda _: None)

    def test_gateway_json_response_to_stream_request(self):
        response = io.BytesIO(json.dumps({'choices':[{'message':{'content':'收到'}}]}).encode())
        response.headers = {'content-type':'application/json'}
        with patch.object(generate.urllib.request, 'urlopen', return_value=response):
            result = generate.Generator(credentials=('https://example.com','test','gpt','test','openai'))._call('test', lambda _: None)
        self.assertEqual(result, '收到')
