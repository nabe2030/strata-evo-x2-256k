#!/bin/bash
# 使い方: run_strata.sh NAME   （<STRATA_ROOT>/Strata/strata-NAME.json で serve を起動、フォアグラウンド）
. <STRATA_ROOT>/env_rocm.sh
mkdir -p <STRATA_ROOT>/logs
cd <STRATA_ROOT>/Strata
exec <STRATA_ROOT>/venv/bin/python -u -m serve.server --engine strata --config strata-$1.json 2>&1 | tee -a <STRATA_ROOT>/logs/serve-$1.out
