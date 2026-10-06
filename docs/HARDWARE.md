# Hardware and models

litecode runs on any machine, from a 4 GB laptop to a workstation with a large GPU. It measures the machine and picks models that fit. On a small PC it picks small, fast models. On a big machine it picks bigger, stronger models.

## How litecode chooses

1. `litecode setup` reads total RAM, CPU cores, disk type, and GPU.
2. It plans with about 60% of total RAM, so your browser and editor keep working.
3. It picks a model for each role: `code`, `chat`, `fim` (autocomplete), `security`, and `quality` (hard tasks).
4. With a GPU build, it moves model layers to the GPU (`gpu_layers = 99`).

## Tiers

| Machine | What litecode loads | Expected use |
|---|---|---|
| 4 GB RAM, no GPU | Qwen2.5-Coder-1.5B + 0.5B autocomplete | code help, explanations, small fixes |
| 8 GB RAM, no GPU | MiniCPM5-2B + 1.5B autocomplete | daily coding, security review, writing |
| 16 GB RAM, no GPU | LFM2.5-8B-A1B (fast MoE) + security model on demand | full agent work on real projects |
| 32 GB RAM | adds Qwen3.5-9B as the quality model | harder multi-file tasks |
| GPU, 12 GB+ VRAM | Qwen3.6-35B-A3B and other 30B-class models | large refactors, deep reviews, long context |

These are defaults. Any GGUF model works. Set it with `litecode config roles.code MyModel.gguf`.

## GPUs

| GPU | Engine build | How to get it |
|---|---|---|
| NVIDIA | CUDA | setup offers it when it finds `nvidia-smi` |
| AMD, Intel, NVIDIA | Vulkan | setup offers it when it finds `vulkaninfo` |
| Apple Silicon | Metal (in the macOS build) | automatic |
| Old GPUs (2 GB, Kepler era) | CPU | litecode ignores the GPU |

Set how many layers go to the GPU: `litecode config gpu_layers 99` (all) or a smaller number to share VRAM.

## What makes it fast

- Generation speed depends mostly on memory bandwidth. Two RAM sticks (dual channel) give about 2x the speed of one.
- Models on an SSD load in about 5 seconds. On a hard drive they take about 30 seconds. litecode keeps the model loaded between tasks.
- The prompt cache is saved per project. The next session skips reprocessing the long system prompt.
- N-gram speculative decoding speeds up edits that repeat existing code.
- `litecode tune` measures all of this on your machine and keeps the fastest settings.

## Reference machine

All published litecode numbers come from this low-end PC, so you can compare:

| Part | Value |
|---|---|
| CPU | AMD Ryzen 3 3200G, 4 cores, 4 threads (2019) |
| RAM | 16 GB DDR4-2133, dual channel |
| GPU | GeForce GT 710 2 GB (too old, not used) |
| Disk | 7200 rpm hard drive for models |

If litecode runs well on this machine, it runs better on yours. See [Benchmarks](BENCHMARKS.md).
