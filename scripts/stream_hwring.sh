#!/bin/bash
# inference host の hw-ring(1Hz) を client-host 側に複製する。inference host がリセットしても記録が残る。
# 出力: ~/inference-mon/hwring-YYYYMMDD.csv （epoch 重複は除去）、接続断はログに残す
OUT=~/inference-mon
while :; do
  ssh -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=2 -o ServerAliveCountMax=3 inference-host \
   'while :; do f=$(ls -t /var/log/hw-ring/*.csv | head -1); tail -n 1 "$f"; sleep 1; done' 2>>$OUT/stream_err.log \
  | awk -F, -v out="$OUT" 'NF>5 && $2!=last && $1!="ts" {last=$2; "date +%Y%m%d" | getline d; close("date +%Y%m%d"); f=out"/hwring-"d".csv"; print >> f; fflush(f)}'
  echo "$(TZ=Asia/Tokyo date '+%F %T JST') stream disconnected, retry in 2s" >> $OUT/stream_err.log
  sleep 2
done
