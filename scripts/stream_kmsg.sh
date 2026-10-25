#!/bin/bash
# inference host の kernel ログ(journalctl -k -f) と ping 死活を client-host 側に複製する
OUT=~/inference-mon
( while :; do ping -i 1 -W 1 <ip> | while read -r l; do echo "$(TZ=Asia/Tokyo date '+%F %T JST') $l"; done >> $OUT/ping.log; sleep 1; done ) &
while :; do
  ssh -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=2 -o ServerAliveCountMax=3 inference-host 'journalctl -k -f -n 0 -o short-iso' >> $OUT/kmsg.log 2>>$OUT/stream_err.log
  echo "$(TZ=Asia/Tokyo date '+%F %T JST') kmsg stream disconnected" >> $OUT/stream_err.log; sleep 2
done
