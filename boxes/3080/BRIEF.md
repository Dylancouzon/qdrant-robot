# Task B1: qualify this machine (2026-10-08)

Goal: confirm this WSL2 box can (1) fine-tune Qwen3-VL-2B-Instruct with LoRA on the RTX 3080, (2) convert a merged model to GGUF and quantize it with llama.cpp, and (3) reach the robot over SSH. Do not train anything yet: the next brief brings the dataset and training recipe.

Steps:
1. Environment: report Windows driver and WSL2 versions, `nvidia-smi` inside WSL (GPU name, VRAM 10 or 12 GB, CUDA version), CPU, RAM visible to WSL, free disk in the WSL filesystem. If WSL caps memory below 24 GB, say how to raise it (`.wslconfig`), but do not change Windows settings without asking Dylan.
2. Python: install `uv` if missing. In a scratch environment outside the repo, install a CUDA build of PyTorch, transformers, peft, accelerate. Verify: `torch.cuda.is_available()`, the GPU name, and a bf16 matmul on the GPU.
3. Model check: download `Qwen/Qwen3-VL-2B-Instruct` (pin the revision you got) and load it in bf16 on the GPU with `Qwen3VLForConditionalGeneration` (or the class transformers names for it); report peak VRAM for loading and for one forward pass on a short text prompt. Then attach a LoRA (rank 16, all linear layers of the language model only, vision tower frozen) and run 10 training steps on one dummy text example with gradient checkpointing; report peak VRAM and seconds per step. This proves training fits.
4. Conversion: clone llama.cpp, build only the tools needed (`llama-quantize`, CPU build is enough), and install the converter's Python requirements. Convert the unmodified base model with `convert_hf_to_gguf.py` to bf16 GGUF, then `llama-quantize` to Q4_K_M. Report the file sizes and the llama.cpp commit. Delete the GGUFs afterwards (they are only a test).
5. Robot access: create an SSH key in WSL (`ssh-keygen -t ed25519`) and ask Dylan to run `ssh-copy-id qdrant@qdrant-robot.local` once (he types the robot password; never store it). Verify with `ssh qdrant@qdrant-robot.local 'hostname; nvpmodel -q 2>/dev/null | head -1'` and a test `scp` of a small file to `/home/qdrant/qdrant-robot/shared/box-test.txt` (then delete it). If `.local` names do not resolve in WSL, report it and try the robot's IP from Dylan.
6. Write REPORT.md (summary first: ready or blocked, and why), commit it and any small logs on `box/3080`, push.

Stop and report instead of working around it if: the GPU is not visible in WSL, loading the model needs more than the card's VRAM, or the converter rejects Qwen3-VL.
