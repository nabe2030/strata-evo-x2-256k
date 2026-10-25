# TheRock ROCm 7.14.1 (gfx1151) をユーザ領域で使うための環境。システムの ROCm 7.2.2 には触れない
export SDK=<STRATA_ROOT>/rocm/install
export ROCM_PATH=$SDK HIP_PATH=$SDK HIP_PLATFORM=amd
export PATH=$SDK/bin:$SDK/lib/llvm/bin:$PATH
export LD_LIBRARY_PATH=$SDK/lib:$SDK/lib/rocm_sysdeps/lib:$SDK/lib/llvm/lib:${LD_LIBRARY_PATH:-}
