#!/bin/bash
set -e
. <STRATA_ROOT>/env_rocm.sh
cd <STRATA_ROOT>/Strata
git log -1 --format="%H %cd" > <STRATA_ROOT>/build_commit.txt
cmake -S . -B build-halo -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DSTRATA_PREFILL_MMQ=ON \
  -DCMAKE_HIP_ARCHITECTURES=gfx1151 \
  -DCMAKE_HIP_COMPILER=$SDK/lib/llvm/bin/clang++ -DCMAKE_HIP_COMPILER_ROCM_ROOT=$SDK \
  "-DCMAKE_PREFIX_PATH=$SDK;$SDK/lib/rocm_sysdeps;$SDK/lib/llvm" \
  "-DCMAKE_HIP_FLAGS=--rocm-path=$SDK --rocm-device-lib-path=$SDK/lib/llvm/amdgcn/bitcode"
cmake --build build-halo --target strata -j 8
touch <STRATA_ROOT>/build_done.marker
