# NVIDIA NIM Setup for AgentForge (RTX 5090 / 32GB VRAM)

This guide covers deploying NVIDIA NIM locally so AgentForge uses your RTX 5090 as the
primary inference runtime instead of falling back to Ollama.

---

## 1. Get an NGC API Key

1. Go to <https://org.ngc.nvidia.com/setup/personal-keys>
2. Click **Generate Personal Key**
3. Under **Services**, check **NGC Catalog** (required for pulling NIM images)
4. Copy the key — you only see it once

Add it to `D:/agentvault/.env`:

```
NGC_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
```

---

## 2. Authenticate Docker with NGC

Run this once (per machine) before `docker compose up`:

```bash
echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
```

On Windows (PowerShell):
```powershell
$env:NGC_API_KEY | docker login nvcr.io --username '$oauthtoken' --password-stdin
```

---

## 3. Recommended Models for RTX 5090 (32GB VRAM)

All measurements are for the NIM-optimised container. VRAM figures are approximate at
inference time.

| Model | NIM Image Tag | VRAM | Precision | Best For |
|---|---|---|---|---|
| Llama 3.1 8B Instruct | `nvcr.io/nim/meta/llama-3.1-8b-instruct:latest` | ~16GB | BF16 | General / complex tasks |
| DeepSeek R1 Distill Llama 8B | `nvcr.io/nim/deepseek-ai/deepseek-r1-distill-llama-8b:latest` | ~10GB | INT4 AWQ | Reasoning / code |
| Llama 3.2 3B Instruct | `nvcr.io/nim/meta/llama-3.2-3b-instruct:latest` | ~8GB | BF16 | Fast / chit-chat |
| Bring-your-own (HuggingFace) | `nvcr.io/nim/nvidia/llm-nim:latest` | varies | configurable | Any HF model |

The RTX 5090's 32GB comfortably runs the 8B models. Running two simultaneously (e.g.
Llama 8B + Llama 3B) requires ~24GB — feasible but leave headroom for the OS.

---

## 4. Start NIM Locally (Without Docker Compose)

Quick test with Llama 3.1 8B:

```bash
# Set cache dir so weights survive container restarts
export LOCAL_NIM_CACHE=D:/nim-cache
mkdir -p $LOCAL_NIM_CACHE

docker run -it --rm \
  --name agentforge-nim \
  --runtime=nvidia \
  --gpus all \
  --shm-size=16gb \
  -e NGC_API_KEY=$NGC_API_KEY \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:latest
```

On first run, NIM downloads the model weights (~16GB) — allow 5–15 minutes depending
on your connection. Subsequent starts load from cache in ~30–60 seconds.

**Verify NIM is ready:**
```bash
curl http://localhost:8000/v1/health/ready
# → HTTP 200 when ready, HTTP 503 while loading

curl http://localhost:8000/v1/models
# → JSON list of served model IDs
```

**Test inference:**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta/llama-3.1-8b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 64
  }'
```

---

## 5. Bring-Your-Own Model (llm-nim Multi-LLM Container)

Use this to run any HuggingFace model or a local GGUF through NIM's OpenAI API:

```bash
docker run -it --rm \
  --name agentforge-nim-custom \
  --runtime=nvidia \
  --gpus all \
  --shm-size=16gb \
  -e NGC_API_KEY=$NGC_API_KEY \
  -e NIM_MODEL_NAME="hf://Qwen/Qwen2.5-7B-Instruct" \
  -e NIM_SERVED_MODEL_NAME="qwen2.5-7b" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -v "D:/ollama/models:/opt/models/local_model:ro" \
  -p 8000:8000 \
  nvcr.io/nim/nvidia/llm-nim:latest
```

Set `NIM_SERVED_MODEL_NAME` to match what you put in `nim_model_name` in `.env`.

For WSL2 on Windows (if you see memory constraint errors):
```
-e NIM_RELAX_MEM_CONSTRAINTS=1
```

---

## 6. Enable NIM in Docker Compose

Uncomment the `nim-llm` service block in `docker-compose.yml`:

```yaml
  nim-llm:
    image: nvcr.io/nim/meta/llama-3.1-8b-instruct:latest
    runtime: nvidia
    shm_size: "16gb"
    environment:
      NGC_API_KEY: ${NGC_API_KEY}
    ports:
      - "8000:8000"
    volumes:
      - nim-cache:/opt/nim/.cache
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Then start the full stack:
```bash
docker compose up -d
```

The `backend` service passes `NIM_BASE_URL=http://nim-llm:8000` automatically when
`nim-llm` is in the same Compose network.

---

## 7. Configure AgentForge to Use NIM

In `D:/agentvault/.env`:

```env
# NGC credentials
NGC_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx

# NIM endpoint (use localhost:8000 for standalone Docker; nim-llm:8000 for Compose)
NIM_BASE_URL=http://localhost:8000

# Model name must match what /v1/models returns
NIM_MODEL_NAME=meta/llama-3.1-8b-instruct
```

Set an agent's `preferred_runtime` to `"nim"` via the AgentForge API or database.
The runtime manager will health-check NIM before each call and fall back to Ollama
automatically if the container is not running.

You can also override per-agent routing in `routing_config`:
```json
{
  "preferred_runtime": "nim",
  "nim_large_model": "meta/llama-3.1-8b-instruct",
  "nim_code_model": "deepseek-ai/deepseek-r1-distill-llama-8b",
  "nim_small_model": "meta/llama-3.2-3b-instruct"
}
```

---

## 8. Optional: NVIDIA LLM Router

The LLM Router blueprint replaces the keyword-based intent classifier in
`runtime_manager.py` with a Qwen 1.7B model that recommends the optimal NIM model
per prompt. Setup:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/llm-router
cd llm-router
docker compose --profile intent up -d --build
```

Router endpoint: `POST http://localhost:8001/sfc_router/chat/completions`

Response: `choices[0].message.content` = recommended model name.

The `runtime_manager.py` classifier is documented with the upgrade path — see
the `_classify_intent` docstring.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConnectError` on NIM | Container not running | `docker ps` — is `agentforge-nim` listed? |
| `503 model still loading` | Startup in progress | Wait ~2 min; `nim_available()` will retry on next request |
| `401 Unauthorized` | NGC key not set or wrong | Check `.env` NGC_API_KEY value |
| `KeyError choices[0]` | NIM returned unexpected shape | Upgrade NIM image: `docker pull nvcr.io/nim/...` |
| Very slow first inference | Model cold (cache miss) | Normal — warm cache after first call |
| OOM / container crash | VRAM exceeded | Switch to smaller model or INT4 AWQ variant |
| `docker: unknown runtime: nvidia` | NVIDIA Container Runtime not installed | Install `nvidia-container-toolkit` |

---

## References

- NIM Getting Started: <https://docs.nvidia.com/nim/large-language-models/latest/getting-started.html>
- Supported Models + GPU profiles: <https://docs.nvidia.com/nim/large-language-models/latest/supported-models.html>
- Bring LLMs to NIM blueprint: <https://github.com/NVIDIA-AI-Blueprints/bring-llms-to-nim>
- LLM Router blueprint: <https://github.com/NVIDIA-AI-Blueprints/llm-router>
- NGC API Keys: <https://org.ngc.nvidia.com/setup/personal-keys>
