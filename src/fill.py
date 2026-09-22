"""One-click 「填入」: put a candidate reply straight into WeChat's input box.

Mechanism — the Accessibility API, not synthetic keystrokes:
    find WeChat's input box in the accessibility tree (the AXTextArea inside the window
    titled 微信), write the text into it, then read it back and only report success if the
    text is verifiably there.

Why not the obvious pasteboard + synthesized Cmd+V, which is what this file used to do:
  * a paste only reaches the *frontmost* app, so WeChat has to be brought forward first —
    and a non-active accessory app cannot reliably do that on current macOS (measured:
    NSRunningApplication activation and AXFrontmost both report success while the app stays
    inactive). When that step fails, the keystroke lands in whatever app IS frontmost, i.e.
    the reply gets typed into someone else's window;
  * it overwrites the general pasteboard, destroying whatever the user had copied;
  * "the events were posted" is not "the text arrived", so the result could not be checked
    — the panel would claim 已填入 over an input box that was still empty, and the user,
    seeing nothing, would click again.
The accessibility write avoids all three: it needs no frontmost window, never touches the
clipboard, and can be read back to prove it worked.

macOS only lets a process touch another app's accessibility tree when that process holds
the Accessibility permission (System Settings -> Privacy & Security -> Accessibility).
Without it the AX calls fail, which is why fill_text() checks first and returns
(False, "未授予辅助功能权限") rather than pretending it worked. request_accessibility()
triggers the system dialog that grants it.

Standalone use (handy for granting the permission before the HUD ever needs it):
    uv run python src/fill.py             # report permission + WeChat process state only
    uv run python src/fill.py "好的，马上"  # actually fill (needs the grant)
"""

from __future__ import annotations

import threading
import time

import AppKit
import ApplicationServices

WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"
WECHAT_NAMES = ("微信", "WeChat")

# WeChat owns two windows: a small untitled one and the chat window. The input box lives in
# the latter, so it is searched first and the untitled window is only a fallback.
CHAT_WINDOW_TITLE = "微信"
INPUT_ROLE = "AXTextArea"
# The chat window holds TWO text areas, and picking the wrong one writes the reply into
# WeChat's sidebar search field (measured: search 127x23, message box 643x129). Size is the
# only thing that separates them reliably, so the largest wins and anything smaller than
# this floor is refused outright rather than guessed at — the two differ by ~24x, so the
# floor is not a close call. (Area is in points^2.)
MIN_INPUT_AREA = 10000.0
# One node per visible message means a busy chat window is a large tree; this ceiling keeps
# a miss cheap instead of walking thousands of nodes.
MAX_NODES = 2000

# Reason strings are shown by the HUD in its status line, so they read as sentences.
REASON_EMPTY = "没有可填入的内容"
REASON_NO_ACCESS = "未授予辅助功能权限"
REASON_NO_WECHAT = "没找到微信应用"
REASON_NO_INPUT = "当前微信未向辅助功能开放聊天输入框"
REASON_WRITE_FAILED = "写入输入框失败"
REASON_NOT_VERIFIED = "写入后没读到内容，可能没填进去"
REASON_BUSY = "上一次填入还没结束"
REASON_DUPLICATE = "刚填入过同样的内容，已忽略这次重复点击"


def has_accessibility() -> bool:
    """True when this process may read and drive other apps' accessibility trees."""
    try:
        return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility() -> bool:
    """Ask macOS to show the Accessibility grant dialog (no-op if already granted).

    Returns the permission state before the user answers — the dialog is asynchronous,
    so a False here means "the user still has to flip the switch".
    """
    try:
        opts = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
        return bool(ApplicationServices.AXIsProcessTrustedWithOptions(opts))
    except Exception:
        return has_accessibility()


def _wechat_app():
    """The running WeChat: bundle id first, window-owner name as the fallback."""
    try:
        apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
            WECHAT_BUNDLE_ID)
        if apps and len(apps) > 0:
            return apps[0]
    except Exception:
        pass
    try:
        for app in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            name = app.localizedName() or ""
            if name in WECHAT_NAMES or app.bundleIdentifier() == WECHAT_BUNDLE_ID:
                return app
    except Exception:
        pass
    return None


def _ax_attr(element, name):
    """One accessibility attribute, or None. Never raises — AX reads fail routinely."""
    try:
        err, value = ApplicationServices.AXUIElementCopyAttributeValue(element, name, None)
        return value if err == 0 else None
    except Exception:
        return None


def _ax_size(element) -> tuple[float, float] | None:
    """(width, height) of an element, or None when it cannot be read."""
    try:
        raw = _ax_attr(element, ApplicationServices.kAXSizeAttribute)
        if raw is None:
            return None
        ok, size = ApplicationServices.AXValueGetValue(
            raw, ApplicationServices.kAXValueCGSizeType, None)
        return (float(size.width), float(size.height)) if ok else None
    except Exception:
        return None


def _find_input_box(pid: int):
    """WeChat's message input box, or None.

    Returns the LARGEST text area in the chat window, not the first one found: WeChat's
    accessibility tree contains both the sidebar search field and the message box, and the
    search field sits shallower. A first-match walk therefore finds the search field and
    writes the reply into it — a bug that a naive read-back check cannot catch, because
    writing and reading both go through the same wrong element and agree with each other.

    The walk is breadth-first and bounded: a busy chat window carries a node per visible
    message.
    """
    app_el = ApplicationServices.AXUIElementCreateApplication(pid)
    windows = _ax_attr(app_el, ApplicationServices.kAXWindowsAttribute) or []
    if not windows:
        return None
    # the chat window first; sorted() is stable, so the fallback keeps its own order
    ordered = sorted(
        windows,
        key=lambda w: _ax_attr(w, ApplicationServices.kAXTitleAttribute)
        != CHAT_WINDOW_TITLE)

    best, best_area = None, 0.0
    for window in ordered:
        queue, seen = [window], 0
        while queue and seen < MAX_NODES:
            el = queue.pop(0)
            seen += 1
            if _ax_attr(el, ApplicationServices.kAXRoleAttribute) == INPUT_ROLE:
                size = _ax_size(el)
                area = size[0] * size[1] if size else 0.0
                if area > best_area:
                    best, best_area = el, area
            queue.extend(_ax_attr(el, ApplicationServices.kAXChildrenAttribute) or [])

    if best is None or best_area < MIN_INPUT_AREA:
        return None
    return best


def _ax_value(box) -> str | None:
    """The input box's current text, or None when it cannot be read as a string."""
    value = _ax_attr(box, ApplicationServices.kAXValueAttribute)
    return value if isinstance(value, str) else None


def _ax_set_value(box, text: str) -> bool:
    """Write text into the box. False means the AX call refused or raised."""
    try:
        err = ApplicationServices.AXUIElementSetAttributeValue(
            box, ApplicationServices.kAXValueAttribute, text)
        return err == 0
    except Exception:
        return False


_FILL_LOCK = threading.Lock()
_LAST_FILL: tuple[str, str, float] | None = None   # (text, box content after fill, ts)
# Short on purpose: it only has to swallow a double click. The content check below is what
# decides, so a deliberate retry a moment later always goes through.
DUPLICATE_WINDOW_S = 0.4


def _duplicate_blocked(text: str, current: str,
                       last: tuple[str, str, float] | None, now: float) -> bool:
    """True when this call is the second half of one double click.

    Keyed on the input box's *content* rather than the clock alone: the same text is
    refused only while the box still holds exactly what our last fill left in it (so nobody
    removed the text in between) and only inside DUPLICATE_WINDOW_S. Filling appends, so
    without this a double click would put the reply in the box twice.

    Comparing `current` — not the text we are about to write — is what makes this work:
    every successful fill grows the box, so a comparison against the new value could never
    match, and the guard would silently never fire.
    Taking every input as an argument keeps the rule testable without a live WeChat.
    """
    if last is None:
        return False
    last_text, last_content, last_ts = last
    return (text == last_text
            and current == last_content
            and (now - last_ts) < DUPLICATE_WINDOW_S)


def fill_text(text: str) -> tuple[bool, str]:
    """Write `text` into WeChat's input box, appended to whatever is already typed there.

    Returns (ok, reason). Appending keeps this equivalent to the paste it replaces: a paste
    lands at the caret, which is the end of the box once the user has been typing. Success
    is never reported without reading the text back.
    """
    global _LAST_FILL
    text = (text or "").strip()
    if not text:
        return False, REASON_EMPTY
    if not _FILL_LOCK.acquire(blocking=False):
        # a fill is still running; a second write now would double the text
        return False, REASON_BUSY
    try:
        if not has_accessibility():
            return False, REASON_NO_ACCESS

        app = _wechat_app()
        if app is None:
            return False, REASON_NO_WECHAT

        box = _find_input_box(app.processIdentifier())
        if box is None:
            return False, REASON_NO_INPUT

        current = _ax_value(box)
        if current is None:
            return False, REASON_NO_INPUT

        # checked before the write, so a refused repeat leaves the box untouched
        if _duplicate_blocked(text, current, _LAST_FILL, time.monotonic()):
            return False, REASON_DUPLICATE

        if not _ax_set_value(box, current + text):
            return False, REASON_WRITE_FAILED

        # read it back: a write that reports success but never appears is exactly the silent
        # failure this mechanism replaced, so it is never assumed away
        landed = _ax_value(box)
        if landed is None or not landed.endswith(text):
            return False, REASON_NOT_VERIFIED
        _LAST_FILL = (text, landed, time.monotonic())
        return True, "已填入"
    finally:
        _FILL_LOCK.release()


if __name__ == "__main__":
    import sys

    print(f"辅助功能权限: {'已授予' if has_accessibility() else '未授予'}")
    _app = _wechat_app()
    if _app is None:
        print("微信进程: 未找到")
    else:
        print(f"微信进程: {_app.localizedName()} ({_app.bundleIdentifier()})")
        if has_accessibility():
            _box = _find_input_box(_app.processIdentifier())
            print(f"输入框: {'已找到（可以填入）' if _box is not None else '没找到'}")
    if len(sys.argv) > 1:
        print(f"填入结果: {fill_text(sys.argv[1])}")


def input_diagnostic() -> str:
    """Report permission, version and AX structure only; never read or log chat text."""
    from collections import Counter, deque
    app = _wechat_app()
    if app is None:
        return REASON_NO_WECHAT
    bundle = AppKit.NSBundle.bundleWithURL_(app.bundleURL())
    info = bundle.infoDictionary() if bundle else {}
    version = str(info.get('CFBundleShortVersionString', '?'))
    build = str(info.get('CFBundleVersion', '?'))
    if not has_accessibility():
        return f'微信 {version}（{build}） · 未授予本应用辅助功能权限。'
    root = ApplicationServices.AXUIElementCreateApplication(app.processIdentifier())
    windows = _ax_attr(root, ApplicationServices.kAXWindowsAttribute) or []
    queue, roles, errors, visited = deque(windows), Counter(), Counter(), 0
    while queue and visited < MAX_NODES:
        element = queue.popleft()
        visited += 1
        roles[str(_ax_attr(element, ApplicationServices.kAXRoleAttribute) or 'unknown')] += 1
        try:
            err, children = ApplicationServices.AXUIElementCopyAttributeValue(
                element, ApplicationServices.kAXChildrenAttribute, None)
            if err:
                errors[int(err)] += 1
            else:
                queue.extend(children or [])
        except Exception:
            errors['exception'] += 1
    fields = roles['AXTextArea'] + roles['AXTextField']
    found = _find_input_box(app.processIdentifier()) is not None
    detail = '；'.join(f'{role} × {count}' for role, count in sorted(roles.items()))
    return (f'微信 {version}（{build}） · 辅助功能已授权\n'
            f'窗口 {len(windows)} 个，读取控件 {visited} 个，文本输入控件 {fields} 个。\n'
            f'{detail}\n'
            + ('原版定位逻辑已找到输入框。' if found else '原版定位逻辑未找到输入框。')
            + (f'\n子节点读取错误：{dict(errors)}' if errors else ''))
