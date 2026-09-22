"""Built-in 话术 presets — one label + one instruction per tone.

These are what the generation prompt asks the model to write in; the user picks up to
MAX_SLOTS of them from the HUD. Keeping them here (rather than inline in the prompt) means
one place to add a tone, and lets the parser strip any label the model echoes back.

Each `prompt` is written as a direct instruction to the model: say what the tone IS, and
what it must not become. Vague one-word tones ("幽默") produce generic replies — the
useful part is the constraint.
"""

from __future__ import annotations

import re

import userconfig

# How many candidates one generation call can produce. The HUD shows exactly this many
# dropdowns; the panel's candidate area is built for this many rows.
MAX_SLOTS = 3

# Candidates per tone. Each tone gets its own request (they run concurrently), and the 2
# replies in one response are the same voice at two different levels of nerve: the first
# stays sendable as-is, the second leans into the persona (see PROMPT_ONE in generate.py).
# A tone asked for twice in one prompt tends to bleed into itself, which is why one tone
# equals one request.
PER_TONE = 2

# label -> instruction. Order here is the order shown in the dropdowns.
#
# Each entry is written as a *persona plus its verbal tics*, not as a description of a mood.
# "语气放松、带一点幽默" gives the model nothing to hold on to and every tone drifts toward
# the same bland helpfulness; naming who is talking and which words they reach for is what
# actually separates the voices. The trailing constraint matters as much as the rest: a tone
# with no ceiling slides back into generic politeness by the second line.
BUILTIN: dict[str, str] = {
    "高情商话术": (
        "像公司里那个谁都说好的老同事：先接住对方情绪（「我理解」「确实」），再说事实和下一步，"
        "拒绝也带替代方案加一个具体时间点。不说教、不绕圈子、句尾不堆「呢/哦/啦」。"
    ),
    "贴吧老哥 v1.0": (
        "贴吧老哥：一口网感口语，「有一说一」「绷不住了」「搁这」「这就去整」随手就来，"
        "自称我、管对方叫「哥/兄弟」，可以自嘲玩梗甚至摆烂，但不骂人。"
        "禁止「您好」「感谢」这类书面客套。"
    ),
    "拒绝加班": (
        "只在对方明确要求加班或催工作交付时，平和而坚定地表达边界，不含糊答应。"
        "不编造截止时间、工作任务或自己的安排；替代时间只能来自聊天原文。"
        "如果聊天与加班无关，保持简短直接的语气回应原话，不提加班和交付。"
    ),
    "卑微乙方": (
        "极度卑微的乙方：「好的好的」「收到收到」「实在抱歉」「麻烦您了」张口就来，全程称「您」，"
        "任何问题先认在自己头上，随叫随到。夸张到一眼看出是梗，但整句仍然能直接发出去。"
    ),
    "稳如老狗": (
        "十年老工程师那种稳：不解释、不铺垫、不道歉，只给结论加一个时间点，句子短、"
        "主语是事不是情绪（「三点前给你」「已确认，没问题」），让对方觉得事情已经稳了。"
    ),
    "已读乱回": (
        "敷衍但不失礼：一到六个字把对方接住（「在忙，你说」「嗯嗯」「好」），"
        "不承诺、不展开、不给时间点，让对方觉得回了又没法接着追问。"
    ),
    "职场黑话": (
        "把简单的事说得很专业：对齐、抓手、闭环、颗粒度、拉通、复盘、赋能、沉淀、打法轮着用，"
        "一句话里至少两个；但整句要能看懂，不要堆到不知所云。"
    ),
    "阴阳怪气": (
        "表面客气、话里带刺：多用「哦」「呢」「那就」「辛苦你了」配反问或夸张的客气，"
        "让对方不好发作又不能说你没礼貌。不要升级成直接骂人或人身攻击。"
    ),
    "理科直男": (
        "只回答被问到的：零寒暄、零情绪、零修饰、零表情，能两个字说清就不用五个字，"
        "像一个不太会说话但很靠谱的工程师。不做任何延伸，也不表示关心。"
    ),
}

# What the panel starts with: two tones, not three — a third slot defaults to 不用.
DEFAULT_SLOTS: list[str] = ["高情商话术", "贴吧老哥 v1.0"]
NONE_LABEL = "不用"          # the third dropdown's way of saying "only two candidates"

CUSTOM_VAR = "JEV_TONES"     # env var holding user-defined tones


def _custom_tones() -> dict[str, str]:
    """Tones the user defined in their env file, as `名字=说明` entries separated by `|`.

        export JEV_TONES="摸鱼大师=像个资深摸鱼选手，把活推得很得体|孙子兵法=用兵法比喻说话"

    A same-named entry overrides the built-in one, so the shipped wording can be tuned
    without touching this file. A tone called 不用 is dropped: that label is the panel's
    sentinel for "this slot is switched off", and letting a tone shadow it would make a
    slot impossible to switch off.
    """
    raw = userconfig.get(CUSTOM_VAR)
    out: dict[str, str] = {}
    for part in (raw or "").split("|"):
        name, sep, desc = part.partition("=")
        name, desc = name.strip(), desc.strip()
        if sep and name and desc and name != NONE_LABEL:
            out[name] = desc
    return out


CUSTOM: dict[str, str] = _custom_tones()
PRESETS: dict[str, str] = {**BUILTIN, **CUSTOM}

def _label_alternation() -> str:
    """The labels as one regex alternative, with spaces made optional.

    "贴吧老哥 v1.0" is written with a space in the dropdown but the model may echo it
    without one ("贴吧老哥v1.0：") — matching the space loosely costs nothing and avoids a
    label that leaks through only sometimes.
    """
    escaped = (re.escape(k).replace(r"\ ", r"\s*") for k in sorted(PRESETS, key=len, reverse=True))
    return "|".join(escaped)


_LABEL_RE = re.compile(
    rf"^[*_#\s]*(?:{_label_alternation()})[^，。！？；、,.!?;：:]{{0,4}}[*_#\s]*[:：]\s*")


def labels() -> list[str]:
    """All preset labels, in dropdown order."""
    return list(PRESETS)


def strip_label(line: str) -> str:
    """Remove a leading preset label the model echoed back, e.g. "贴吧老哥 v1.0：好的哥".

    The model is told not to label its lines, and usually complies — but the prompt itself
    shows it these labels, so now and then it echoes one. Because the labels are data, they
    are stripped from the same place they are defined: adding a tone here cannot silently
    break the parser the way a hardcoded list would.
    """
    return _LABEL_RE.sub("", line)
