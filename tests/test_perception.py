"""Synthetic OCR geometry regressions; never capture the screen or call a model."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from perception import TextBlock, extract_messages


class ChatGeometry(unittest.TestCase):
    def test_short_message_survives_window_resize_with_sender(self):
        for height in (585, 915, 1200):
            with self.subTest(height=height):
                blocks = [
                    TextBlock('测试同事', 1, .36, .6, .12, 12.6 / height),
                    TextBlock('收到', 1, .36, .6 - 34 / height, .08, 15 / height),
                ]
                positions = [(b.y, b.h) for b in blocks]
                messages = extract_messages(blocks, window_height=height)
                self.assertEqual([m.text for m in messages], ['收到'])
                self.assertEqual(messages[0].sender, '测试同事')
                self.assertEqual([(b.y, b.h) for b in blocks], positions)

    def test_single_chat_short_message_is_not_discarded_as_nickname(self):
        blocks = [TextBlock('好', 1, .36, .5, .02, 15 / 585)]
        self.assertEqual(extract_messages(blocks, window_height=585)[0].text, '好')

    def test_notification_badge_and_orphan_sender_do_not_become_messages(self):
        blocks = [TextBlock('343条新消息', 1, .88, .75, .1, 15 / 585),
                  TextBlock('测试昵称', 1, .36, .5, .1, 12 / 585)]
        self.assertEqual(extract_messages(blocks, window_height=585), [])


if __name__ == '__main__':
    unittest.main()
