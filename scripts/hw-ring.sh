#!/bin/bash
# 1 Hz hardware ring log -> /var/log/hw-ring/YYYYMMDD-HH.csv (hourly files, fdatasync each line, files older than KEEP_HOURS deleted).
# Purpose: capture the last seconds before a silent reset. Complements hw-telemetry (15s, 30d).
DIR=/var/log/hw-ring; KEEP_HOURS=${KEEP_HOURS:-72}
mkdir -p "$DIR"
rd() { local v; read -r v < "$1" 2>/dev/null && echo "$v" || echo NA; }
hw() { for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name 2>/dev/null)" = "$1" ] && echo $h && return; done; }
gpu() { for c in /sys/class/drm/card[0-9]; do [ -e $c/device/mem_info_vram_used ] && echo $c/device && return; done; }
HDR="ts,epoch,gpu_busy,vram_b,gtt_b,gpu_edge_mC,gpu_ppt_uW,gpu_sclk_Hz,gpu_vddgfx_mV,cpu_tctl_mC,mem_avail_kB,swap_free_kB,load1"
last_h=""; n=0
while :; do
  if [ $((n % 30)) -eq 0 ] || [ -z "$GPU" ]; then GPU=$(gpu); AMDH=$(hw amdgpu); CPUH=$(hw zenpower); fi
  printf -v ts '%(%Y-%m-%dT%H:%M:%S%z)T' -1; printf -v ep '%(%s)T' -1; printf -v hr '%(%Y%m%d-%H)T' -1
  F="$DIR/$hr.csv"; [ -s "$F" ] || echo "$HDR" > "$F"
  ma=NA; sf=NA
  while read -r k v _; do case $k in MemAvailable:) ma=$v;; SwapFree:) sf=$v;; esac; done < /proc/meminfo
  read -r l1 _ < /proc/loadavg
  echo "$ts,$ep,$(rd $GPU/gpu_busy_percent),$(rd $GPU/mem_info_vram_used),$(rd $GPU/mem_info_gtt_used),$(rd $AMDH/temp1_input),$(rd $AMDH/power1_average),$(rd $AMDH/freq1_input),$(rd $AMDH/in0_input),$(rd $CPUH/temp1_input),$ma,$sf,$l1" >> "$F"
  sync -d "$F"
  if [ "$hr" != "$last_h" ]; then find "$DIR" -name '*.csv' -mmin +$((KEEP_HOURS*60)) -delete; last_h=$hr; fi
  n=$((n+1)); sleep 1
done
