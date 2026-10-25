#!/usr/bin/env python3
"""OpenCode(V1/V2) で同一セッションに依頼を重ね、コンテクストを育てる。サーバの /slots の n_prompt_tokens で量を測る。
使い方: oc_session.py V1|V2 TAG [--max-prompts 40] [--stop-ctx 240000] [--after 3]
結果: ~/inference-mon/oc-TAG.jsonl（1依頼1行）。サーバ停止/接続不能なら SERVER_DOWN を残して終了。"""
import argparse, json, os, subprocess, sys, time, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("ver"); ap.add_argument("tag")
ap.add_argument("--max-prompts", type=int, default=40); ap.add_argument("--stop-ctx", type=int, default=240000); ap.add_argument("--after", type=int, default=3)
ap.add_argument("--timeout", type=int, default=3000); ap.add_argument("--start", type=int, default=0); ap.add_argument("--cont", action="store_true")
a = ap.parse_args()
H = os.path.expanduser("~"); KEY = open(f"{H}/.strata_inference_key").read().strip()
wrapper = f"{H}/oc/oc1" if a.ver == "V1" else f"{H}/oc/oc2"
cwd = f"{H}/oc/target1" if a.ver == "V1" else f"{H}/oc/target2"
OUT = f"{H}/inference-mon/oc-{a.tag}.jsonl"; RAW = f"{H}/inference-mon/oc-{a.tag}-raw"; os.makedirs(RAW, exist_ok=True)
def jst(): return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 9 * 3600)) + " JST"
def log(r):
    r["jst"] = jst()
    open(OUT, "a").write(json.dumps(r, ensure_ascii=False) + "\n"); print(json.dumps(r, ensure_ascii=False)[:300], flush=True)
def ctx():
    try:
        req = urllib.request.Request("http://<ip>:8095/slots", headers={"Authorization": "Bearer " + KEY})
        d = json.load(urllib.request.urlopen(req, timeout=10)); d = d if isinstance(d, list) else d.get("slots", [d])
        return max(int(x.get("n_prompt_tokens", 0)) for x in d)
    except Exception as e:
        return None
FIXED = [
 "このリポジトリ(Strata)の src/ と serve/ を実際にファイルを開いて読み、主要モジュールの構成と責務を日本語でまとめて REPORT_1.md に書いてください。各節で根拠にしたファイル名と関数名を最低5つ挙げること。",
 "HIP / Strix Halo(gfx1151) に関わる実装箇所を src/ から探して全文読み、何を gfx1151 向けに切り替えているかを REPORT_2.md に日本語で書いてください。根拠のファイルと行を示すこと。",
 "メモリ配置(expert cache、arena、mmap、KV の置き場、--kv-resident)がどう決まるかを、ソースを読んで REPORT_3.md に日本語で詳しくまとめてください。serve/server.py の設定処理も読むこと。",
 "serve/server.py を最初から最後まで通読し、設計上・信頼性上の問題点を10個、具体的な行番号付きで ISSUES.md に書いてください。",
 "tests/ を読み、不足しているテストを3つ設計して tests/NEW_TEST_PLAN.md に書いてください。",
 "REPORT_1.md、REPORT_2.md、REPORT_3.md、ISSUES.md を読み返し、矛盾や不足があれば直して、全体の要約 SUMMARY.md を作ってください。",
]
GENERIC = "まだ読んでいない src/ 配下のファイルを大きいものから3つ選び、全文を読んで(head 等で切らない)、役割と問題点を NOTES.md の末尾に追記してください。"
n = a.start; after = 0; first = not a.cont
log({"event": "start", "ver": a.ver, "wrapper": wrapper, "cwd": cwd})
while n < a.max_prompts:
    prompt = FIXED[n] if n < len(FIXED) else GENERIC
    n += 1
    cmd = [wrapper, "run", "--format", "json"] + ([] if first else ["-c"]) + [prompt]
    if a.ver == "V2": cmd = [wrapper, "run", "--standalone", "--auto", "-m", "strata/qwen3.8-flash-next-ud-iq4_xs", "--format", "json"] + ([] if first else ["-c"]) + [prompt]
    t0 = time.time(); c0 = ctx()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=a.timeout); rc = p.returncode; out = p.stdout; err = p.stderr[-500:]
    except subprocess.TimeoutExpired as e:
        rc = "TIMEOUT"; out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""); err = ""
    open(f"{RAW}/{n:02d}.json", "w").write(out)
    first = False
    c1 = ctx()
    nev = len(out.splitlines()); toolcalls = out.count('"type":"tool')
    log({"event": "prompt", "n": n, "rc": rc, "elapsed_s": round(time.time() - t0, 1), "ctx_before": c0, "ctx_after": c1, "json_lines": nev, "tool_events": toolcalls, "err": err[-200:]})
    if c1 is None:
        log({"event": "SERVER_DOWN_OR_UNREACHABLE"}); sys.exit(3)
    if c1 >= a.stop_ctx or after:
        after += 1
        if after > a.after: break
log({"event": "done", "prompts": n})
