# strata-evo-x2-256k

Running **Strata v0.1.40.2** (HIP) with **Qwen3.8-Flash-Next UD-IQ4_XS** at **256K context (262,144 tokens)** on a Ryzen AI Max+ 395 mini PC (Radeon 8060S, gfx1151, 96 GiB of BIOS-fixed VRAM, about 30 GiB of system RAM left to the OS), on Linux, with ROCm in user space. Measured on 7–8 October 2026 (JST).

Everything here was **measured on one machine with Strata v0.1.40.2** (commit `e8ca9afd03d839d4f8dbbe82dffce7f8a3bafd7a`). Newer Strata versions behave differently in places (see [Notes on newer versions](#notes-on-newer-versions)); the numbers below are not updated for them.

This repository is an independent user report. It is not affiliated with the Strata project.

Japanese article (Qiita): https://qiita.com/nabe2030/items/2c29db3e0c69552e2d80 — it also links the earlier llama.cpp (Vulkan) article this one follows up on.

## TL;DR

1. Strata ran this model at **256K context with MTP** on this box **without any BIOS, kernel-parameter or reboot change**. The stock start (`--expert-cache auto`) did **not** work here (see [Gotchas](#gotchas)); `--mmap-experts --expert-cache 24576` did.
2. **Stability:** about **8.2 hours** of high GPU load (GPU use of 95 % or more) in 5 test runs, the longest single run about 97 minutes, the largest single request about **235K tokens**. **No reset, no hang, no server stop.** The earlier llama.cpp/Vulkan run reset the machine at 88K–104K tokens of generation; this one did not (the causes are not established, see [Limits](#limits)).
3. **OpenCode v1 (1.18.35) and v2 (2.0.24) both worked at 256K** (tool calls, thinking, compaction, two clients at once). Strata needs `"fit_max_tokens": true` for OpenCode v1 here; without it the conversation stalled at about 230K with an HTTP 400 (`prompt + max_tokens > n_ctx`).
4. **Speed (no thinking, one request at a time):** 43.6 tok/s decode with MTP, 28.5 tok/s without (see the caveats on what "without" means). Cold prefill of a 63K-token prompt: about 53 s (about 1,190 tok/s).
5. **Quality:** JamC-QA, first 300 questions, **66.0 % (198/300)**, identical with and without MTP.

## Hardware and software

| Item | Value |
|---|---|
| Machine | Ryzen AI Max+ 395 mini PC (Radeon 8060S, gfx1151), BIOS 1.09 (AMI, 2025-09-13) |
| Memory | BIOS-fixed 96 GiB VRAM, GTT about 15 GiB, about 30 GiB system RAM |
| OS | Ubuntu 26.04, kernel 7.0.0-38, linux-firmware 20260319 |
| ROCm | AMD TheRock 7.14.1 (gfx1151) in a user directory; the system ROCm 7.2.2 was not touched |
| Strata | v0.1.40.2, built from source with the official steps (`-j 8`, about 4 minutes) |
| Model | Unsloth `UD-IQ4_XS` (3 shards, 93.7 GB), pack made with `iq_pack.py --compat-bf16` (rounds the Q8_0 hyper-connection projections to BF16, so results can differ slightly from llama.cpp) |
| Clients | OpenCode v1 1.18.35 and v2 2.0.24 (isolated HOME/XDG directories), a streaming API driver, `vllm bench serve` |

### Server configuration

`configs/strata-fast256.example.json` (placeholders for paths and the key):

```
--pack <pack> --native <shard-1.gguf> --expert-profile data/expert-profile.bin
--expert-cache 24576 --mmap-experts --prefill 16384 --max-context 262144 --kv int8
--spec 4 --spec-min-p 0.5 --mtp <mtp> --lookup-chain 3 --mtp-q4 all
```

Environment (the developers' Strix Halo "fast" set, from `STRIX_HALO.md`): `STRATA_HIPBLASLT_TUNING=<...>/gfx1151-hipblaslt-100401.txt`, `STRATA_PF_FUSED=1`, `STRATA_PF_GEMM=1`, `STRATA_HC_UPMIX=1`, `STRATA_PA_FAST=1`, `STRATA_HIP_WMMA=1`, `STRATA_SELECT_WMMA=1`, `STRATA_HC_Q8=1`, `STRATA_PF_SWITCH_MIN_T=4096`, on top of the 18 gfx1151 defaults the engine switches on by itself. Server setting `"fit_max_tokens": true`. `parallel: 2` was used only in the two-client runs.

The "no MTP" configuration drops `--mtp --lookup-chain --mtp-q4` and uses `--spec 2 --spec-min-p 0.5`: a native pack requires `--spec` of 2 or more, so speculative decoding cannot be turned off completely; what remains is the lookup-based draft only.

A systemd unit is in `systemd/strata.service.example`.

## Gotchas

- **The default start does not work with a large BIOS carve-out and little RAM.** `--expert-cache auto` takes a path that copies all experts (59.5 GB for this model) into pinned system RAM. With about 30 GiB of RAM left, the engine exited without an error message; the last log line was `ArenaExpertSource: the arena could not be reserved (59523276800 B)` and the kernel logged `__vm_enough_memory: ... bytes: 59525373952 not enough memory for the allocation` (see `results/monitor/kmsg.log`). Using `--mmap-experts` (GGUF mapped in place) with `--expert-cache 24576` (all slots) fixes it: 24576/24576 slots are filled in about 29–34 s, "100 % VRAM resident", about 27.7 GiB of VRAM free after loading with 256K context, int8 KV and MTP.
- **OpenCode v1 and `max_tokens`.** OpenCode v1 sends `max_tokens` of about 32,000 on every request. Strata rejects `prompt + max_tokens > n_ctx` with HTTP 400, which stalled the conversation at about 230K, before OpenCode's own compaction threshold. `"fit_max_tokens": true` (shorten `max_tokens` to the room left) fixed it for all later runs. Setting OpenCode's `limit.context` to 262,144 − 32,768 or less would be another way (not tested).
- **OpenCode v2 picks a default model if you do not name one.** Without `-m` (or a `model` in the config) it can choose a hosted default instead of your local server. Set `model` in the config.
- **OpenCode v2 needs `--standalone` for a dedicated server** when another v2 service is already running on the machine.
- **Compaction is silent for minutes.** The summary request starts differently from a normal turn, so Strata re-reads the whole context cold (221 s at 235K tokens, about 2 minutes at 158K). The agent produces no output meanwhile; use a client timeout of 900 s or more.
- **`vllm bench serve` metrics are wrong against Strata.** TTFT is meaningless (Strata sends a first chunk with only `role` after about 9 ms, which vllm counts as the first token: median TTFT 4.9 ms). Without MTP, vllm under-counted output tokens (7 of 12 reproductions of requests that the server finished with 100–245 tokens were counted as 0). The cause is not identified. The speed figures below are therefore recomputed from the server log (`scripts/server_log_rate.py`).

## Results

### Stability (256K context)

Monitoring ran for the whole time and outside the machine: a 1 Hz hardware ring buffer written locally with `fdatasync` and mirrored to a second machine, the kernel log, and ping. A reset would have left a gap.

| # | Test | Duration | Largest context | Result |
|---|---|---|---|---|
| 1 | API conversation grown turn by turn, thinking high, `max_tokens` 6000 | 55 min, 31 turns, 139,282 tokens generated | 230,967 (final 236,967) | no anomaly |
| 2 | OpenCode v1, real agent work | about 1.5 h | about 235K (compaction down to 92K) | no server anomaly; one HTTP 400 (see Gotchas), one corrupted answer (see Limits) |
| 3 | OpenCode v2, same tasks | 84 min | about 190K (3 compactions) | no anomaly |
| 4 | `parallel 2`, OpenCode v1 and v2 at once | about 97 min | about 180K each | no anomaly; 15–21 tok/s per request (45–50 alone), total about the same as one |
| 5 | `parallel 2`, two API conversations to the maximum | 82 min, 13 and 14 turns | 217K and 232K | no anomaly; re-reads the full context every turn |

Over the elapsed 10.6 hours: GPU use of 95 % or more for 8.23 h, 50 % or more for 9.28 h; no gap longer than 5 s in the mirrored ring buffer, no ping loss; **0 resets**. Edge temperature maximum **94 °C**, package power maximum about **117 W**, shader clock about 2.3–2.8 GHz. Longest single run about 97 min; largest single prompt about 235K tokens (cold read in 221 s).

Raw data: `results/monitor/` (ring buffer, kernel log), `results/soak/` (per-turn / per-request records), `results/server-logs/`.

### Speed

ShareGPT, 200 prompts, seed 0, thinking off, one request at a time, three runs. Output tok/s is generated tokens divided by wall-clock time:

| Configuration | decode tok/s (server log) | output tok/s (wall clock, median) | runs |
|---|---:|---:|---|
| Strata, MTP on | 53.2 | **43.57** | 43.61 / 43.57 / 42.64 |
| Strata, lookup draft only (`--spec 2`) | 32.5 | **28.47** | 28.46 / 28.47 / 28.47 |

Draft acceptance: about 68 % with MTP (26,322/38,651), about 49 % for the lookup draft only (3,400/6,900). With MTP, the generated token count differed slightly between runs (44,614 / 44,614 / 43,660); without MTP it was identical (44,614) in all three.

Cold prefill (server restarted before each size, one run per size, so not a 3-run median), then the same prompt a second time:

| Prompt tokens | MTP: cold | MTP: second run | no MTP: cold | no MTP: second run |
|---:|---:|---:|---:|---:|
| 2,535 | 3,095.8 ms (819 tok/s) | 53.9 ms | 3,138.7 ms (808 tok/s) | 85.4 ms |
| 22,836 | 19,869.9 ms (1,149 tok/s) | 360.4 ms | 19,727.0 ms (1,158 tok/s) | 87.5 ms |
| 63,286 | 53,077.9 ms (1,192 tok/s) | 57.7 ms | 53,468.4 ms (1,184 tok/s) | 88.6 ms |

Comparisons with other setups (a llama.cpp Vulkan build, a DGX Spark with SGLang) differ in more than the engine: MTP on or off, the thinking setting, the pack's BF16 rounding, and the prompt sharing a prefix with the previous size in the other setup (so its larger sizes were not strictly cold). Treat them as context, not a ranking.

### Quality

JamC-QA v1.0 test, first 300 questions (the raw results keep only question ids, predictions and correctness; question and answer texts are not redistributed), dev 3-shot, `max_tokens` 8, temperature 0, no LLM judge, thinking off (the gold distribution {0:74, 1:79, 2:72, 3:75} matches the earlier article, i.e. the same 300 questions):

| Configuration | Accuracy | Parse failures |
|---|---:|---:|
| Strata, MTP on | **66.0 % (198/300)** | 0 |
| Strata, lookup draft only | **66.0 % (198/300)** | 0 |
| llama.cpp b11200 Vulkan, same GGUF (earlier article) | 66.67 % (200/300) | 0 |

The 2-question difference to llama.cpp is within what the BF16 pack rounding and the GPU expert-cache arithmetic order could explain; this was not isolated.

### OpenCode v1 and v2

| | v1 (1.18.35) | v2 (2.0.24) |
|---|---|---|
| Config | `opencode.json`: `provider`, `options`, `models[].limit`, `permission` object | `opencode.jsonc`: `providers`, `package`, `settings`, `permissions[]` array (different keys) |
| Non-interactive | `run --format json` (`-c` continues) | `run --standalone --auto -m ... --format json` |
| At 256K | works; compaction fired twice (about 235K and about 170–230K) | works; compaction fired three times (about 154–190K) |
| Tools | read/grep/glob/edit/write/bash all work | read/grep/glob/edit/write/shell/execute all work; no malformed calls or undefined tool names |
| `max_tokens` sent | 32,000 (from `limit.output` 32768) | 32,768 |
| Output anomaly | once, at 163.7K the answer degenerated into a short corrupted text and stopped (about 380 steps) | not observed (about 400 steps) |

Prefix-cache read share reported by OpenCode: v1 alone 92.2 %, v2 alone 96.3 %, v1 at `parallel 2` 92.1 %, v2 at `parallel 2` 94.7 %. An example config is in `configs/opencode-v2.example.jsonc` (an example rewritten in the OpenCode v2 2.0.24 format, not the exact file used during the measurements).

### Firmware

BIOS 1.09 (no newer BIOS is published by the vendor's support page that could be found). amdgpu firmware: SMC (PMFW) 100.2.0, MES 0x86, MES_KIQ 0x6f, PFP 0x31, ME 0x20, MEC 0x22, RLC 0x11530506, IMU 0x0b352300, SDMA0 0x12, VCN 0x09118010, DMCUB 0x09003f00. Public reports of GPU hangs on Strix Halo under sustained 100 % load exist for other systems with MES 0x86 as well; this run met that kind of load (sustained prefill, for example 235K tokens in 221 s) without a hang, which says nothing about other firmware or machines.

## Limits

- One machine, one model, one engine version. The longest single run was about 97 minutes and the total high-load time about 8.2 hours. **An overnight run was not done**, so "stable" here means "no problem in these 8 hours", not more.
- The earlier llama.cpp/Vulkan run reset the whole machine at 88K–104K tokens of generation. The cause is not established. A GPU compute-queue timeout in the Vulkan backend is one hypothesis; Strata (HIP) not resetting is consistent with it but does not prove it. Heat or power cannot be ruled out either (this run peaked at 94 °C and 117 W without a reset).
- One corrupted answer (OpenCode v1, 163.7K) in about 780 agent steps. Its cause (model, quantization, engine, MTP) was not isolated.
- The "no MTP" configuration is not "no speculation" (see above).
- `vllm bench serve` metrics are unreliable against Strata (see Gotchas); the speed figures come from server-log recomputation.
- Open WebUI and other clients were not tested.

## Reproduce

1. Build Strata v0.1.40.2 from source with the official steps, with ROCm 7.14.1 (TheRock) in a user directory: `scripts/env_rocm.sh`, `scripts/build_strata.sh`.
2. Make the pack (`--compat-bf16`) and write a config: `scripts/mkconfig.py NAME [--mtp on|off] [--ctx N] [--parallel N] [--fit]`. Edit the `<...>` placeholders first.
3. Start: `scripts/run_strata.sh NAME` or the systemd unit.
4. Speed: `scripts/speed_arm.sh`, `scripts/bench_c1.sh`, `scripts/prefix_test.py`; recompute rates with `scripts/server_log_rate.py` (Strata's own log lines).
5. Quality: `scripts/jamcqa_run.sh` (`scripts/jamcqa_bench_auth.py`).
6. Long context: `scripts/soak_api.py` (API conversation growth), `scripts/oc_session.py` (OpenCode driver).
7. Monitoring from a second machine: `scripts/stream_hwring.sh`, `scripts/stream_kmsg.sh`. The ring-buffer writer on the server (1 Hz GPU/RAM/power sample, `fdatasync` per line, 72 h retention) is `scripts/hw-ring.sh` with `systemd/hw-ring.service.example`.

Comments in some scripts are in Japanese.

## Notes on newer versions

Checked against the Strata sources and documentation on 2026-10-24. These are not part of the measurements above. In later Strata versions `fit_max_tokens` is on by default, so the OpenCode v1 HTTP 400 described above should not occur without the setting. A hipBLASLt tuning table is picked up automatically only when it sits next to the engine binary (`tuning/`) or comes from setup; a hand-built engine needs `STRATA_HIPBLASLT_TUNING`. Check the current Strata documentation before relying on any detail of this report.

## Contents

- `configs/` – example server config and OpenCode config
- `systemd/` – example units (Strata server, hardware ring log)
- `scripts/` – build, run, measurement, monitoring scripts
- `results/` – raw measurements: `speed/` (per-run JSON and logs, MTP on/off), `jamcqa/`, `soak/`, `monitor/`, `server-logs/`
- `LICENSE` – MIT
