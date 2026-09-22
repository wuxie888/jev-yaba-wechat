"""Native model settings window. No chat data is used by connection tests."""
from __future__ import annotations

import threading

import AppKit
import objc
from Foundation import NSObject, NSMakeRect

import model_settings


class ModelSettingsWindow(NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(ModelSettingsWindow, self).init()
        if self is None:
            return None
        self.owner = owner
        self.fields = {}
        self.status = {}
        self.tests = {}
        self.pending = set()
        self.results = {}
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 560, 640),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered, False)
        self.window.setTitle_('jev-哑巴微信 · 模型设置')
        self.window.setLevel_(AppKit.NSFloatingWindowLevel + 1)
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))
        self.window.setBackgroundColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(1, .985, .995, 1))
        self._label('模型设置', 24, 18, 440, 30, 22, True)
        self._label('GPT 写回复，Jev 判断意思和风险、筛选候选。', 24, 49, 512, 22, 12)
        self._label('工作模式', 24, 82, 100, 25, 13, True)
        self.mode = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(142, 640-82-27, 394, 27), False)
        self.mode.addItemsWithTitles_(['聊天识别预览 · 暂停模型调用', '正常回复 · Jev 判断 + GPT 生成'])
        self.mode.setTarget_(self)
        self.mode.setAction_('modeChanged:')
        self.window.contentView().addSubview_(self.mode)
        self.mode_hint = self._label('', 24, 114, 512, 30, 11)
        self._label('GPT · 写候选回复', 24, 151, 512, 25, 15, True)
        self._field('OPENAI_BASE_URL', 'API 基础地址', 184)
        self._field('OPENAI_MODEL', '模型名称', 216)
        self._field('OPENAI_API_KEY', 'API Key', 248, secure=True)
        self._label('接口格式', 24, 283, 110, 25, 12)
        self.api = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(142, 640-280-27, 240, 27), False)
        self.api.addItemsWithTitles_(['Responses', 'Chat Completions'])
        self.api.setTarget_(self)
        self.api.setAction_('apiChanged:')
        self.window.contentView().addSubview_(self.api)
        self.tests['OPENAI'] = self._button('测试 GPT', 415, 280, 121, 'testGPT:')
        self.status['OPENAI'] = self._label('', 142, 311, 394, 42, 11)
        self._label('Jev · 判断意图、评估风险、排序回复', 24, 353, 512, 25, 15, True)
        self._field('TYPESAFE_BASE_URL', 'API 基础地址', 387)
        self._field('TYPESAFE_MODEL', '模型名称', 419)
        self._field('TYPESAFE_API_KEY', 'API Key', 451, secure=True)
        self.tests['TYPESAFE'] = self._button('测试 Jev', 415, 483, 121, 'testJev:')
        self.status['TYPESAFE'] = self._label('', 142, 515, 394, 42, 11)
        self._label('测试仅发送固定测试句，不含微信聊天；可能产生少量 API 费用。\nKey 保存在这台 Mac 上。修改后保存并重启即可生效。',
                    24, 560, 512, 38, 11)
        self.diagnostic = self._button('检查微信输入框', 24, 602, 170, 'diagnoseInput:')
        self.cancel = self._button('取消', 288, 602, 80, 'cancel:')
        self.save_button = self._button('保存并重启', 384, 602, 152, 'saveSettings:')
        self._reload()
        return self

    @objc.python_method
    def _label(self, text, x, top, width, height, size, bold=False):
        label = AppKit.NSTextField.labelWithString_(text)
        label.setFrame_(NSMakeRect(x, 640-top-height, width, height))
        label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(size) if bold else AppKit.NSFont.systemFontOfSize_(size))
        label.setTextColor_(AppKit.NSColor.labelColor() if bold else AppKit.NSColor.secondaryLabelColor())
        label.cell().setWraps_(True)
        self.window.contentView().addSubview_(label)
        return label

    @objc.python_method
    def _field(self, key, title, top, secure=False):
        self._label(title, 24, top+3, 110, 24, 12)
        cls = AppKit.NSSecureTextField if secure else AppKit.NSTextField
        field = cls.alloc().initWithFrame_(NSMakeRect(142, 640-top-27, 394, 27))
        field.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        field.setBezeled_(True)
        field.setBezelStyle_(AppKit.NSTextFieldRoundedBezel)
        field.setDelegate_(self)
        field.setPlaceholderString_('填写 Key，内容将隐藏' if secure else title)
        self.fields[key] = field
        self.window.contentView().addSubview_(field)

    @objc.python_method
    def _button(self, title, x, top, width, action):
        button = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, 640-top-28, width, 28))
        button.setTitle_(title)
        button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(action)
        self.window.contentView().addSubview_(button)
        return button

    @objc.python_method
    def _reload(self):
        values = model_settings.current()
        for key, field in self.fields.items():
            field.setStringValue_(values.get(key, ''))
        self.mode.selectItemAtIndex_(0 if values['JEV_READ_ONLY'] == '1' else 1)
        self.api.selectItemAtIndex_(0 if values['OPENAI_API_FORMAT'] == 'responses' else 1)
        self.results.clear()
        for prefix in self.status:
            self._untested(prefix)
        self.modeChanged_(None)

    @objc.python_method
    def show(self):
        self._reload()
        self.window.center()
        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def values(self):
        values = {key: str(field.stringValue()).strip() for key, field in self.fields.items()}
        values['OPENAI_API_FORMAT'] = 'responses' if self.api.indexOfSelectedItem() == 0 else 'openai'
        values['JEV_READ_ONLY'] = '1' if self.mode.indexOfSelectedItem() == 0 else '0'
        return values

    @objc.python_method
    def _signature(self, prefix, values):
        return tuple((key, value) for key, value in sorted(values.items()) if key.startswith(prefix + '_'))

    @objc.python_method
    def _untested(self, prefix):
        self.status[prefix].setStringValue_('已填写 · 尚未测试当前配置' if self.fields[prefix + '_API_KEY'].stringValue() else '尚未填写 API Key')
        self.status[prefix].setTextColor_(AppKit.NSColor.secondaryLabelColor())

    def controlTextDidChange_(self, notification):
        for key, field in self.fields.items():
            if notification.object() == field:
                prefix = 'OPENAI' if key.startswith('OPENAI_') else 'TYPESAFE'
                self.results.pop(prefix, None)
                self._untested(prefix)

    def apiChanged_(self, sender):
        self.results.pop('OPENAI', None)
        self._untested('OPENAI')

    def modeChanged_(self, sender):
        preview = self.mode.indexOfSelectedItem() == 0
        self.mode_hint.setStringValue_('只识别聊天文字，不自动调用 GPT 或 Jev。' if preview else
                                      '保存后，读到微信新消息会自动分析并生成；选好的回复由你发送。')
        self.mode_hint.setTextColor_(AppKit.NSColor.secondaryLabelColor())

    @objc.python_method
    def _test(self, prefix):
        if prefix in self.pending:
            return
        snapshot = self.values()
        try:
            model_settings.validate(snapshot, prefix)
        except ValueError as error:
            self.status[prefix].setStringValue_(str(error))
            self.status[prefix].setTextColor_(AppKit.NSColor.systemRedColor())
            return
        self.pending.add(prefix)
        self.tests[prefix].setEnabled_(False)
        self.save_button.setEnabled_(False)
        self.status[prefix].setStringValue_('正在发送固定测试句…')
        self.status[prefix].setTextColor_(AppKit.NSColor.secondaryLabelColor())
        signature = self._signature(prefix, snapshot)

        def work():
            try:
                message, success = model_settings.probe(prefix, snapshot), True
            except Exception as error:
                message, success = model_settings.failure_message(error), False
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                'testFinished:', (prefix, signature, message, success), False)
        threading.Thread(target=work, daemon=True).start()

    def diagnoseInput_(self, sender):
        self.window.close()
        self.owner.diagnoseInput_(sender)

    def testGPT_(self, sender):
        self._test('OPENAI')

    def testJev_(self, sender):
        self._test('TYPESAFE')

    def testFinished_(self, payload):
        prefix, signature, message, success = payload
        self.pending.discard(prefix)
        self.tests[prefix].setEnabled_(True)
        self.save_button.setEnabled_(not self.pending)
        if tuple(tuple(pair) for pair in signature) != self._signature(prefix, self.values()):
            self._untested(prefix)
            return
        self.results[prefix] = success
        self.status[prefix].setStringValue_(message)
        self.status[prefix].setTextColor_(AppKit.NSColor.systemGreenColor() if success else AppKit.NSColor.systemRedColor())

    def saveSettings_(self, sender):
        if self.pending:
            return
        values = self.values()
        try:
            model_settings.validate(values)
            if values['JEV_READ_ONLY'] == '0' and not all(self.results.get(p) is True for p in self.tests):
                raise ValueError('正常回复需要 GPT 和 Jev 均测试通过；也可以先保存为聊天识别预览。')
            model_settings.save(values)
        except ValueError as error:
            self.mode_hint.setStringValue_(str(error))
            self.mode_hint.setTextColor_(AppKit.NSColor.systemRedColor())
            return
        except OSError:
            self.mode_hint.setStringValue_('保存失败，请检查本机配置目录的写入权限。')
            self.mode_hint.setTextColor_(AppKit.NSColor.systemRedColor())
            return
        self.owner.restartAfterSettings_(None)

    def cancel_(self, sender):
        self.window.performClose_(None)

    def windowWillClose_(self, notification):
        self.owner.settingsDidClose_(None)
