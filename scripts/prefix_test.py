#!/usr/bin/env python3
"""長いプレフィックスの初回(コールド)・2回目(キャッシュヒット)の prompt_ms を測る（記事の prefix_cache_test.py の Strata 版）。
使い方: prefix_test.py LABEL  （inference host 上。LABEL = 2512 / 22813 / 63262）。サーバは直前に再起動して空にしておくこと。"""
import json, sys, time, urllib.request
URL = "http://127.0.0.1:8095/v1/chat/completions"
KEY = open("<STRATA_ROOT>/api_key").read().strip()
def send(text, max_tokens=20):
    payload = {"model": "qwen3.8-flash-next-ud-iq4_xs", "reasoning_effort": "none", "max_tokens": max_tokens, "temperature": 0.0,
               "messages": [{"role": "user", "content": text + "\n\n以上の内容を10字程度で要約してください。"}]}
    t0 = time.time()
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    d = json.load(urllib.request.urlopen(req, timeout=1800))
    t = d.get("timings", {})
    return {"prompt_ms": t.get("prompt_ms"), "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
            "predicted_ms": t.get("predicted_ms"), "predicted_n": t.get("predicted_n"), "wall_clock_s": round(time.time() - t0, 3),
            "usage": d.get("usage"), "content": d["choices"][0]["message"].get("content")}
if __name__ == "__main__":
    label = sys.argv[1]
    text = open(f"<BENCH_DIR>/prefix_prompts/prefix_{label}.txt").read()
    out = {"label": label}
    send("ウォームアップ")           # 起動直後の初回初期化を除く（短い別内容。プレフィックスとは共通部分なし）
    out["cold"] = send(text); print("cold", json.dumps(out["cold"], ensure_ascii=False))
    out["warm"] = send(text); print("warm", json.dumps(out["warm"], ensure_ascii=False))
    json.dump(out, open(f"<BENCH_DIR>/strata_prefix_{label}_{sys.argv[2] if len(sys.argv)>2 else 'run'}.json", "w"), ensure_ascii=False, indent=2)
