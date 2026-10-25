#!/bin/bash
# 使い方: restart_strata.sh NAME   Strata を NAME 設定で（再）起動し、/v1/models が答えるまで待つ。inference host 上で実行
NAME=$1; KEY=$(cat <STRATA_ROOT>/api_key)
tmux kill-session -t strata 2>/dev/null
for i in $(seq 1 60); do pgrep -f "build-halo/strata --serve" >/dev/null || break; sleep 1; done
pgrep -f "build-halo/strata --serve" && { echo "ENGINE STILL RUNNING"; exit 1; }
rm -f <STRATA_ROOT>/logs/strata-$NAME.log
T0=$(date +%s)
tmux new-session -d -s strata "bash <STRATA_ROOT>/run_strata.sh $NAME"
for i in $(seq 1 300); do
  curl -s -m 3 -H "Authorization: Bearer $KEY" http://127.0.0.1:8095/v1/models 2>/dev/null | grep -q n_ctx && { echo "READY $NAME in $(( $(date +%s)-T0 )) s"; exit 0; }
  sleep 2
done
echo "NOT READY after 600 s"; exit 2
