#!/usr/bin/env python3
"""Strata サーバ設定(JSON)を生成する。使い方: mkconfig.py NAME [--mtp on|off] [--ctx N] [--parallel N] [--kvres N] [--port N]
inference host の <STRATA_ROOT>/Strata/strata-NAME.json に書く。API キーは <STRATA_ROOT>/api_key から読む(値は出力しない)。"""
import argparse, json, os
ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("--mtp", default="on"); ap.add_argument("--ctx", type=int, default=262144)
ap.add_argument("--parallel", type=int, default=0); ap.add_argument("--kvres", type=int, default=0)
ap.add_argument("--port", type=int, default=8080); ap.add_argument("--cache", default="auto"); ap.add_argument("--fit", action="store_true"); ap.add_argument("--extra", default="")
a = ap.parse_args()
R = "<STRATA_ROOT>"
key = open(f"{R}/api_key").read().strip()
args = ["--pack", f"{R}/packs/ud-iq4_xs",
        "--native", "<MODELS>/qwen38-flash-next-iq4xs/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf",
        "--expert-profile", "data/expert-profile.bin", "--expert-cache", a.cache,
        "--prefill", "16384", "--max-context", str(a.ctx), "--kv", "int8"]
if a.mtp == "on":
    args += ["--spec", "4", "--spec-min-p", "0.5", "--mtp", f"{R}/mtp/rt", "--lookup-chain", "3", "--mtp-q4", "all"]
if a.mtp != "on":
    args += ["--spec", "2", "--spec-min-p", "0.5"]   # native pack は --spec T>=2 が必須。--mtp なし=ルックアップ系ドラフトのみ
if a.kvres:
    args += ["--kv-resident", str(a.kvres)]
if a.extra:
    args += a.extra.split()
env = {  # 公式 STRIX_HALO.md §3, §5（開発者の fast 構成）
    "STRATA_HIPBLASLT_TUNING": f"{R}/Strata/tools/hip/gfx1151-hipblaslt-100401.txt",
    "STRATA_PF_FUSED": "1", "STRATA_PF_GEMM": "1", "STRATA_HC_UPMIX": "1", "STRATA_PA_FAST": "1",
    "STRATA_HIP_WMMA": "1", "STRATA_SELECT_WMMA": "1", "STRATA_HC_Q8": "1", "STRATA_PF_SWITCH_MIN_T": "4096"}
cfg = {"exe": f"{R}/Strata/build-halo/strata", "args": args, "cwd": f"{R}/Strata",
       "tokenizer": f"{R}/packs/ud-iq4_xs/tokenizer", "model_name": "qwen3.8-flash-next-ud-iq4_xs",
       "log": f"{R}/logs/strata-{a.name}.log", "host": "0.0.0.0", "port": a.port, "api_key": key, "env": env}
if a.fit:
    cfg["fit_max_tokens"] = True
if a.parallel > 1:
    cfg["parallel"] = a.parallel
out = f"{R}/Strata/strata-{a.name}.json"
json.dump(cfg, open(out, "w"), indent=2); os.chmod(out, 0o600)
print(out, "args:", " ".join(args))
