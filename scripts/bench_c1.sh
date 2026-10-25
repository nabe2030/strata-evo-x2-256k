#!/bin/bash
# 使い方: bench_c1.sh TAG [TRIALS]  ShareGPT c=1 を記事と同条件で測る（vllm bench serve、200件、seed 0、reasoning_effort=none）。inference host 上で実行
TAG=$1; N=${2:-3}
OUT=<BENCH_DIR>/strata_$TAG; mkdir -p $OUT
for t in $(seq 1 $N); do
  docker run --rm --network host -e OPENAI_API_KEY=$(cat <STRATA_ROOT>/api_key) \
    -v <DATA>/datasets:/datasets -v <MODELS>/qwen38-flash-next-tokenizer:/tokenizer -v $OUT:/results \
    --entrypoint vllm vllm-rocm-strix:latest bench serve --backend openai-chat --base-url http://localhost:8095 \
    --endpoint /v1/chat/completions --model qwen3.8-flash-next-ud-iq4_xs --tokenizer /tokenizer \
    --dataset-name sharegpt --dataset-path /datasets/sharegpt/ShareGPT_V3_unfiltered_cleaned_split.json \
    --num-prompts 200 --max-concurrency 1 --seed 0 --extra-body '{"reasoning_effort":"none"}' \
    --save-result --result-dir /results --result-filename c1_trial$t.json > $OUT/c1_trial$t.log 2>&1
  echo "trial $t done $(date -u +%FT%TZ)"; grep -E "Output token throughput|Median TTFT|Median TPOT|Successful|Failed" $OUT/c1_trial$t.log
done
touch $OUT/DONE
