#!/bin/bash
# 使い方: jamcqa_run.sh TAG   inference host 上。JamC-QA 300問サブセット（記事と同じハーネス・3-shot・max_tokens 8・nothink）を Strata に対して実行
TAG=$1; cd <STRATA_ROOT>/jamcqa
export STRATA_KEY=$(cat <STRATA_ROOT>/api_key)
<VENV>/bin/python jamcqa_bench_auth.py --api-url http://127.0.0.1:8095/v1/chat/completions \
  --model qwen3.8-flash-next-ud-iq4_xs --max-tokens 8 --num-shots 3 --limit 300 --reasoning-effort none \
  --output <STRATA_ROOT>/jamcqa/jamcqa_$TAG.json > <STRATA_ROOT>/jamcqa/jamcqa_$TAG.log 2>&1
touch <STRATA_ROOT>/jamcqa/jamcqa_$TAG.done
