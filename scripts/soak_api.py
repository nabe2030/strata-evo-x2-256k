#!/usr/bin/env python3
"""長文コンテクスト負荷（実エージェントの会話の育ち方を模す）。client-host から Strata に接続する。
会話にコード片(Strata のソース)を毎ターン足し、長い回答(thinking あり)を生成させ、プロンプトが --target に達するまで育てる。
結果は 1 ターン 1 行の JSONL（~/inference-mon/soak-TAG-sN.jsonl）。サーバが落ちたら SERVER_DOWN を残して終了する（リセット疑い）。
使い方: soak_api.py TAG --stream-id 0 --target 245000 [--chunk 12000] [--max-tokens 6000] [--effort high] [--offset N]"""
import argparse, json, os, sys, time, urllib.request, urllib.error, socket
ap = argparse.ArgumentParser()
ap.add_argument("tag"); ap.add_argument("--stream-id", type=int, default=0); ap.add_argument("--target", type=int, default=245000)
ap.add_argument("--chunk", type=int, default=12000); ap.add_argument("--max-tokens", type=int, default=6000)
ap.add_argument("--effort", default="high"); ap.add_argument("--offset", type=int, default=0)
ap.add_argument("--url", default="http://<ip>:8095"); ap.add_argument("--hold-turns", type=int, default=2)
a = ap.parse_args()
KEY = open(os.path.expanduser("~/.strata_inference_key")).read().strip()
OUT = os.path.expanduser(f"~/inference-mon/soak-{a.tag}-s{a.stream_id}.jsonl")
ROOT = os.path.expanduser("~/oc/soakdata")
files = []
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp for x in ("third_party", "/ref", "benchmarks", "bench/results", "/media", "/.git")): continue
    for f in sorted(fn):
        if f.endswith((".cpp", ".cu", ".py", ".md", ".h", ".hpp", ".cuh", ".txt", ".sh")):
            files.append(os.path.join(dp, f))
files.sort(key=lambda p: (os.path.getsize(p) < 2000, p)); files = files[a.offset:] + files[:a.offset]
def jst(): return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 9 * 3600)) + " JST"
def log(rec):
    rec["jst"] = jst()
    with open(OUT, "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False)[:400], flush=True)
def chunks():
    """複数ファイルをまとめて 1 ターン分(約 a.chunk トークン相当の文字数)にする。小さいファイルが多く、1 ファイル 1 ターンだと育たないため"""
    buf = []; size = 0; limit = int(a.chunk * 3.0)
    for p in files:
        try: txt = open(p, errors="replace").read()
        except Exception: continue
        i = 0
        while i < len(txt):
            piece = txt[i:i + (limit - size)]; i += len(piece)
            if piece.strip(): buf.append((p, piece)); size += len(piece)
            if size >= limit:
                yield (", ".join(sorted({os.path.relpath(b[0], ROOT) for b in buf}))[:200]), "\n".join(f"// ---- {os.path.relpath(b[0], ROOT)} ----\n{b[1]}" for b in buf)
                buf = []; size = 0
cpt_state = {"v": 3.0}
def call(messages):
    body = {"model": "qwen3.8-flash-next-ud-iq4_xs", "messages": messages, "max_tokens": a.max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, "reasoning_effort": a.effort}
    req = urllib.request.Request(a.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    t0 = time.time(); tfirst = None; ntok = 0; text = []; usage = None; fin = None
    r = urllib.request.urlopen(req, timeout=3600)
    for raw in r:
        line = raw.decode(errors="replace").strip()
        if not line.startswith("data:"): continue
        d = line[5:].strip()
        if d == "[DONE]": break
        j = json.loads(d)
        if j.get("usage"): usage = j["usage"]
        for ch in j.get("choices", []):
            dl = ch.get("delta", {})
            if dl.get("content") or dl.get("reasoning_content"):
                if tfirst is None: tfirst = time.time() - t0
                ntok += 1
            if dl.get("content"): text.append(dl["content"])
            if ch.get("finish_reason"): fin = ch["finish_reason"]
    el = time.time() - t0
    return "".join(text), usage, fin, tfirst, el, ntok
msgs = [{"role": "system", "content": "あなたはコードレビューを行うシニアエンジニアです。日本語で、具体的に答えてください。"}]
gen = chunks(); turn = 0; hold = 0
log({"event": "start", "args": vars(a)})
while True:
    turn += 1
    cur = (usage_last if turn > 1 else 0) if "usage_last" in globals() else 0
    if cur < a.target - a.chunk - a.max_tokens:
        p, piece = next(gen)
        msgs.append({"role": "user", "content": f"次は次のファイル群の一部です: {p}。\n```\n{piece}\n```\nこのコードの役割と、設計上・性能上の問題点を、1500字以上で詳しく日本語で説明してください。"})
        kind = "grow"
    else:
        hold += 1
        msgs.append({"role": "user", "content": "ここまでに見たコード全体を踏まえ、最も危険な箇所を5つ挙げ、それぞれ理由と修正案を詳しく書いてください。"})
        kind = "hold"
    try:
        text, usage, fin, tf, el, ntok = call(msgs)
    except (urllib.error.URLError, ConnectionError, socket.timeout, OSError) as e:
        log({"event": "ERROR_OR_SERVER_DOWN", "turn": turn, "err": repr(e)[:300]}); sys.exit(3)
    pt = (usage or {}).get("prompt_tokens", 0); ct = (usage or {}).get("completion_tokens", 0)
    usage_last = pt + ct
    # 文字/トークン比は固定（旧版は自動補正が小さく振れてコード片が縮んだ。m1 は約 7K/ターン、p2 は約 6K/ターンに縮んだ）
    prev_pt, prev_ct = pt, ct
    msgs.append({"role": "assistant", "content": text})
    log({"event": "turn", "turn": turn, "kind": kind, "prompt_tokens": pt, "completion_tokens": ct, "finish": fin,
         "ttft_s": round(tf, 2) if tf else None, "elapsed_s": round(el, 1),
         "decode_tok_s": round(ntok / max(0.01, el - (tf or 0)), 1), "cached": ((usage or {}).get("prompt_tokens_details") or {}).get("cached_tokens")})
    if kind == "hold" and hold >= a.hold_turns: break
log({"event": "done", "turns": turn, "final_context": usage_last})
