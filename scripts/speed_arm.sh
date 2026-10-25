#!/bin/bash
# 使い方: speed_arm.sh CONFIGNAME TAG   inference host 上。長いプロンプト3規模（毎回再起動で空）→ ShareGPT c=1 ×3
CFG=$1; TAG=$2
for s in 2512 22813 63262; do
  <STRATA_ROOT>/restart_strata.sh $CFG || exit 1
  python3 <STRATA_ROOT>/prefix_test.py $s $TAG
done
<STRATA_ROOT>/restart_strata.sh $CFG || exit 1
<STRATA_ROOT>/bench_c1.sh $TAG 3
touch <STRATA_ROOT>/speed_$TAG.done
