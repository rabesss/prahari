# Prahari Arm Neoverse-V2 benchmark

Run on 2026-11-23 on one rented cloud Arm Neoverse-V2 instance (8 vCPU), using the supplied detector and six demo items. The instance was terminated after the run.

## Machine and setup

- Debian 12, Linux 6.1.155, aarch64; ARM Neoverse-V2 r0p1, eight online vCPUs, one thread per core. `free -g` reported 15 GiB total and no swap. `lscpu` also listed 56 offline CPUs; they were not available to the benchmark.
- CPU feature flags included `asimddp`, `i8mm` and `bf16`. Neither `sve` nor `sve2` appeared in the exposed flags.
- Python 3.12.16, ExecuTorch 1.6.0, pytorch-tokenizers 1.6.0, Torch 2.15.0+cpu. All pinned requirement versions installed; Torch was replaced with the matching CPU wheel after the default wheel pulled CUDA packages. `torch.version.cuda` was `None`; unused NVIDIA dependency packages from the initial install remained present. Debian `libatomic1` was needed to load the runner. See [environment and versions](env.txt).
- The downloaded PTE SHA-256 was `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`; tokenizer SHA-256 was `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`. Both match the supplied prefixes. [Hash record](hashes.txt).
- Detector tests: **171 passed** in 10.40 seconds. [Pytest output](pytest.txt). The six-item [explain output](explain.jsonl) has six successful explanations: four malicious and two benign verdicts.

## KleidiAI dispatch

`perf record -F 99 -g` profiled one complete two-thread `bin/explain` invocation, including Python startup, imports, model loading and six inferences. `perf report --stdio --no-children` recorded approximately 2,222 samples with zero lost samples. Named `kai_*` leaf functions account for **54.17% of sampled CPU time**, calculated by summing the displayed self percentages. This is a whole-process, CPU-time-weighted estimate, not the fraction of inference wall time.

The two largest symbols were `kai_kernel_matmul_clamp_f32_qai8dxp4x8_qsi4c32p4x8_16x4x32_opt32_neon_i8mm` at 23.27% and `kai_kernel_matmul_clamp_f32_qai8dxp1x8_qsi4c32p4x8_1x4x32_neon_dotprod` at 20.57%. Call stacks connect them to `xnn_invoke_runtime`, the ExecuTorch XNNPACK delegate, and respectively prefill and token generation. This directly establishes dispatch, rather than merely the presence of symbols. [Profile excerpt and stacks](perf-report.txt); [flat symbol report](perf-flat.txt).

The installed Python sources and strings in the installed ExecuTorch shared libraries were searched for a KleidiAI disable switch; no supported runtime switch was found. No A/B was run, and the search does not prove that no undocumented switch exists. ExecuTorch was not rebuilt. [Search evidence](kleidi-config.txt).

## Threads

Before any model load, a `sitecustomize.py` hook called `executorch.extension.pybindings.portable_lib._unsafe_reset_threadpool(n)`; the runner logs confirm the reset. For each setting three separate processes each ran all six items. Below, each cell is the mean ± sample standard deviation of the **three per-run six-item means**. `first_token_ms` is the callback time in the shipped output; decode and prefill are the runner's reported rates. Item wall time is the output's `latency_ms`, including classification and generation, excluding process startup and model load. Cold batch wall time is whole process elapsed divided by six, including those startup costs. First items incur cold effects; occasional retries and unequal item lengths can affect latency.

| Threads | TTFT ms | Decode tok/s | Prefill tok/s | Item wall s | Cold batch s/item |
|---:|---:|---:|---:|---:|---:|
| 1 | 1465.5 ± 33.1 | 25.69 ± 0.16 | 109.26 ± 0.07 | 2.792 ± 0.031 | 3.437 ± 0.052 |
| 2 | 922.0 ± 3.1 | 46.69 ± 0.12 | 210.58 ± 0.22 | 1.728 ± 0.002 | 2.485 ± 0.210 |
| 4 | 907.7 ± 373.0 | 75.89 ± 0.43 | 378.79 ± 2.70 | 1.470 ± 0.377 | 2.098 ± 0.378 |
| 8 | 526.8 ± 15.0 | 104.58 ± 1.15 | 676.80 ± 2.29 | 0.980 ± 0.015 | 1.606 ± 0.020 |

[Per-item measurements](threads.csv) and individual `thread-*-*.jsonl` and `.log` files retain the runs. Three repetitions and one box are not enough to characterize broader performance variation. TTFT includes Python callback and first-run effects and is not identical to the runner's prompt evaluation time used for prefill rate.

The supplied Oracle Neoverse-N1 project baseline at two threads was approximately 82 prefill tok/s, 20 decode tok/s and 3.8 s/item end-to-end. The V2 two-thread run measured 210.58 prefill tok/s and 46.69 decode tok/s, around 2.57× and 2.33× those rates, respectively. V2 item latency was 1.728 s, or 2.485 s/item including amortized cold process startup; these are not strictly comparable to the 3.8 s baseline without knowing the baseline's exact timing boundaries, workload and run conditions.

## Offline proof

After downloading and verifying the model, `unshare -n` started a fresh network namespace. `ip -brief link` showed only `lo` (down); `curl -m 5 https://example.com` failed with exit 6, DNS resolution for `huggingface.co` failed with exit 2, and a raw TCP connection to `1.1.1.1:443` failed with `Network is unreachable`. In that same namespace, `bin/explain` exited 0 and produced all six verdicts, explanations and LLM stats. [Full transcript](offline-proof.txt), [offline JSONL](offline.jsonl).
