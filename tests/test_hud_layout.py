"""Native layout regression checks, using synthetic text without model or WeChat calls."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import hud


class ScrollablePanel(unittest.TestCase):
    def setUp(self):
        self.flags = patch.multiple(hud, BRAND_PREVIEW=True, READ_ONLY=False)
        self.flags.start()
        self.app = hud.AppKit.NSApplication.sharedApplication()
        self.controller = hud.HudController.alloc().init()

    def tearDown(self):
        self.controller.panel.setDelegate_(None)
        hud.AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.controller.status_item)
        self.flags.stop()

    def populate(self):
        c = self.controller
        c.slot_tones = [next(iter(hud.styles.PRESETS))] * 3
        c._render('message', '长消息换行测试。' * 30)
        c._render_groups([(i, c.slot_tones[i], [{'text':'确保长回复最后一个字也能看到。' * 15, 'prob':.4}] * 2)
                          for i in range(3)])

    def test_overflow_scrolls_to_last_candidate_without_exceeding_screen(self):
        self.populate()
        c = self.controller
        self.assertLessEqual(c.panel.frame().size.height, hud.NSScreen.mainScreen().visibleFrame().size.height)
        bottom = c.document.frame().size.height - c.scroll.contentSize().height
        self.assertGreater(bottom, 0)
        c.scroll.contentView().scrollToPoint_((0, bottom))
        c.scroll.reflectScrolledClipView_(c.scroll.contentView())
        self.assertAlmostEqual(c.scroll.contentView().bounds().origin.y, bottom)
        last = c._rows[2][1]['fill_btn'].frame()
        self.assertLessEqual(last.origin.y + last.size.height, c.document.frame().size.height)

    def test_resize_reflows_text_and_retains_user_height_when_results_update(self):
        self.populate()
        c = self.controller
        old = c.document.frame().size.height
        c.panel.setContentSize_((580,400))
        c.windowDidResize_(None)
        self.assertLess(c.document.frame().size.height, old)
        self.populate()
        self.assertEqual(c.scroll.frame().size.height, 400)
        c._set_collapsed(True)
        c._set_collapsed(False)
        self.assertEqual(c.scroll.frame().size.height, 400)

    def test_missing_input_copies_candidate_and_never_claims_inserted(self):
        c = self.controller
        c.cand_texts[0] = '这是合成测试文字'
        button = Mock()
        button.tag.return_value = 0
        with patch.object(hud.fill, 'has_accessibility', return_value=True), \
             patch.object(hud.fill, 'fill_text', return_value=(False,hud.fill.REASON_NO_INPUT)), \
             patch.object(hud, 'NSPasteboard') as pb:
            c.fillCandidate_(button)
            pb.generalPasteboard.return_value.setString_forType_.assert_called_once_with(
                '这是合成测试文字', hud.NSPasteboardTypeString)
        status = str(c.rows['status'].stringValue())
        self.assertIn('⌘V', status)
        self.assertIn('已复制', status)
        self.assertNotIn('已填入', status)


if __name__ == '__main__':
    unittest.main()
