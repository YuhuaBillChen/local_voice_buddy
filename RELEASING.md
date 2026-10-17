# Releasing

What has to be published, in this order, for `./install.sh` to work for others. Nothing here is
automatic.

1. **npu-cosyvoice** (GitHub `YuhuaBillChen/npu-cosyvoice`): push `main` and the tag `v0.1.1`;
   compose.yml builds the speech images from that tag when they cannot be pulled.
   `git push origin main v0.1.1`
2. **Prebuilt speech files** (Hugging Face `billchen42/npu-cosyvoice`): int8 weights, LM GGUF, NPU
   overlay, `SHA256SUMS`. Without them `setup` builds them on the user's machine (~15 min).
   `hf upload billchen42/npu-cosyvoice <folder> .`
3. **Container images** (GitHub Container Registry, optional but saves users a 20-40 min build).
   Build on a Zen 4 machine (llama.cpp inside the speech image is built for the build host's CPU,
   and every Ryzen AI 7040/8040 is Zen 4), from clean checkouts, then push and make each package
   public (github.com > Packages > package settings > visibility):

   | image | built from |
   |---|---|
   | `ghcr.io/yuhuabillchen/npu-cosyvoice-voice:0.1.1` | npu-cosyvoice `v0.1.1`, `docker/Dockerfile` target `voice` |
   | `ghcr.io/yuhuabillchen/npu-cosyvoice-whisper:0.1.1` | npu-cosyvoice `v0.1.1`, target `whisper` |
   | `ghcr.io/yuhuabillchen/local-voice-buddy-webui:0.1.1` | this repo, `webui/` |

   ```sh
   echo $GHCR_TOKEN | docker login ghcr.io -u YuhuaBillChen --password-stdin   # classic PAT with write:packages
   docker compose --profile setup build && docker compose --profile setup push setup whisper webui
   ```
4. **This repository** (GitHub `YuhuaBillChen/local_voice_buddy`): push `main` and the tag `v0.1.1`.
5. **Websites**: in each repository, Settings > Pages > Deploy from branch `main`, folder `/docs`.

The chat model is downloaded straight from `unsloth/Qwen3.8-27B-GGUF` and is not republished.

When bumping a version, change the tag in compose.yml (`#v0.1.1` and the three image tags) together.
`install.sh` always rebuilds the web UI image from this checkout, so `git pull && ./install.sh`
updates the patches even when an older image is cached.
