#!/usr/bin/env python3
"""Strata エンジンログ (strata serve: prompt ... generated ...) から、ShareGPT c=1 の各試行の実測出力速度を再計算する。
使い方: server_log_rate.py LOGFILE [N_PER_TRIAL=200] — 小プロンプト(<4000tok)のリクエストを時系列に 200 件ずつ区切る（先頭のウォームアップ等は除く）。
各試行の合計生成トークン、合計 decode 時間、decode tok/s、合計 prompt 読み時間、(生成/(decode+prompt読み)) を出す。"""
import re, sys, statistics as st
path = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
R = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms.*?, (\d+) generated in (\d+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)")
reqs = []
for l in open(path, errors="replace"):
    m = R.search(l)
    if m: reqs.append(tuple(float(x) for x in m.groups()))
small = [r for r in reqs if r[0] < 4000]
# 末尾から 200 件ずつ切る（試行は連続し、その後に別リクエストが来ない前提）。端数は先頭側の warm-up として捨てる
k = len(small) // N
print("small-prompt requests:", len(small), "-> full trials:", k, "(discarded head:", len(small) - k * N, ")")
off = len(small) - k * N
for t in range(k):
    seg = small[off + t * N: off + (t + 1) * N]
    gen = sum(r[4] for r in seg); dec_ms = sum(r[5] for r in seg); pr_ms = sum(r[3] for r in seg)
    acc = sum(r[7] for r in seg); drf = sum(r[8] for r in seg)
    print(f"trial {t+1}: requests {len(seg)} generated {int(gen)} tok  decode {dec_ms/1000:.1f}s ({gen/(dec_ms/1000):.1f} tok/s)  prompt-read {pr_ms/1000:.1f}s  "
          f"engine-side e2e {gen/((dec_ms+pr_ms)/1000):.2f} tok/s  drafts {int(acc)}/{int(drf)}")
