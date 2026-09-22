"""Chinese intent-judgment test: can a local Jev-shaped model read a boss message?

Zero-shot, no training — this measures how much labeling work the app will need.
Cases are real messages pulled from the live WeChat window plus realistic variants.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

# 直接 import 判断层的 INTENTS：回归测的必须是线上真正发出的那份 prompt。
# 此前这里是一份手工同步的副本，judge.py 改了描述这里不会跟着变，回归就在
# 测一个没人用的配置（与 dtype 那条注释是同一个原则）。
from judge import INTENTS

# (message text, gold intent) — includes the live-captured ones
CASES: list[tuple[str, str]] = [
    ("这个需求你今天跟一下", "派活"),
    ("顺手把这个需求文档补一下", "派活"),
    ("明天把这个方案给客户发过去吧", "派活"),
    ("那个东西做完了吗", "催进度"),
    ("那个东西什么时候能好？", "催进度"),
    ("这块还没动呢？抓紧点", "催进度"),
    ("现在进度怎么样了", "问进度"),
    ("上线了吗", "问进度"),
    ("客户那边反馈如何", "问进度"),
    ("这个逻辑不对啊，你再看下", "批评"),
    ("怎么又出问题了", "批评"),
    ("这做的什么玩意", "批评"),
    ("为什么用这个方案？", "要解释"),
    ("你当时怎么想的", "要解释"),
    ("这个数据从哪来的", "要解释"),
    ("哈哈哈太搞笑了", "闲聊"),
    ("我周末去爬山了", "闲聊"),
    ("牛啊这也能写出来", "闲聊"),
    ("下午三点开个会同步一下", "约会议"),
    ("方便的话我们语音聊十分钟", "约会议"),
    ("这个做得不错，继续", "夸奖"),
    ("牛逼，这个思路好", "夸奖"),
]


def run_decider() -> dict:
    """Mapika/decider-2b via the documented letter-logit readout."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    repo = "Mapika/decider-2b"
    tok = AutoTokenizer.from_pretrained(repo)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    # must match src/judge.py — a regression test measuring a different dtype is measuring
    # a configuration nobody ships
    dtype = torch.float16 if dev == "mps" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(repo, dtype=dtype).to(dev).eval()
    letters = "ABCDEFGH"
    lids = [tok.encode(c, add_special_tokens=False)[0] for c in letters]
    temp = 1.3

    def judge(text: str) -> tuple[str, float, np.ndarray]:
        names = list(INTENTS)
        prompt = f"Context:\n{text}\n\nQuestion: 这句话的真实意图是什么？\nOptions:\n"
        for i, n in enumerate(names):
            prompt += f"({letters[i]}) {n} - {INTENTS[n]}\n"
        prompt += "Answer: ("
        ids = tok(prompt, return_tensors="pt").to(dev)
        with torch.no_grad():
            logits = model(**ids).logits[0, -1]
        probs = torch.softmax(logits[lids[: len(names)]].float() / temp, -1).cpu().numpy()
        return names[int(np.argmax(probs))], float(probs.max()), probs

    t0 = time.perf_counter()
    results = []
    for text, gold in CASES:
        pred, conf, _ = judge(text)
        results.append({"text": text, "gold": gold, "pred": pred, "conf": conf})
    return {"model": "decider-2b", "elapsed_s": time.perf_counter() - t0, "results": results}


def run_laya_multilingual() -> dict:
    """convaiinnovations/laya multilingual checkpoint (Chinese-capable per its card)."""
    import laya

    agent = laya.load("convaiinnovations/laya", subfolder="multilingual")
    names = list(INTENTS)
    question = {
        "intent": {"type": "choice",
                   "instructions": "这句话的真实意图是什么？",
                   "criteria": INTENTS},
    }

    t0 = time.perf_counter()
    results = []
    for text, gold in CASES:
        try:
            out = agent.predict(text, question)
            ans = out["answers"]["intent"]
            probs = ans.get("probabilities") or ans.get("probs") or {}
            pred = ans.get("choice")
            conf = float(ans.get("confidence", 0.0))
        except Exception as e:
            pred, conf = f"ERR:{type(e).__name__}", 0.0
        results.append({"text": text, "gold": gold, "pred": pred, "conf": conf})
    return {"model": "laya-multilingual", "elapsed_s": time.perf_counter() - t0,
            "results": results}


def summarize(run: dict) -> dict:
    res = run["results"]
    n = len(res)
    correct = sum(1 for r in res if r["pred"] == r["gold"])
    by_gold: dict[str, list[bool]] = {}
    for r in res:
        by_gold.setdefault(r["gold"], []).append(r["pred"] == r["gold"])
    return {
        "model": run["model"],
        "acc": correct / n,
        "n": n,
        "elapsed_s": round(run["elapsed_s"], 1),
        "per_intent": {k: round(sum(v) / len(v), 2) for k, v in by_gold.items()},
        "majority_baseline": round(max(
            sum(1 for r in res if r["gold"] == g) for g in set(r["gold"] for r in res)) / n, 3),
    }


def main() -> None:
    out_path = Path("results/judge_zh.json")
    out_path.parent.mkdir(exist_ok=True)
    report = {}

    for name, fn in (("decider", run_decider), ("laya_ml", run_laya_multilingual)):
        print(f"\n===== {name} =====", flush=True)
        try:
            run = fn()
            s = summarize(run)
            report[name] = {"summary": s, "results": run["results"]}
            print(f"acc={s['acc']:.3f}  n={s['n']}  elapsed={s['elapsed_s']}s  "
                  f"majority_baseline={s['majority_baseline']}")
            print("per-intent:", s["per_intent"])
            for r in run["results"]:
                flag = "OK " if r["pred"] == r["gold"] else "XX "
                print(f"  {flag}{r['text'][:22]:24s} gold={r['gold']:5s} "
                      f"pred={str(r['pred']):6s} conf={r['conf']:.2f}")
        except Exception as e:
            import traceback
            report[name] = {"error": f"{type(e).__name__}: {e}"}
            print("FAILED:", e)
            traceback.print_exc()

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nsaved {out_path}")


if __name__ == "__main__":
    main()
