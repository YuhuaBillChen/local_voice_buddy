# Releasing

What has to be published, in this order, for `./install.sh` to work for others. Nothing here is
automatic.

1. **npu-cosyvoice** (GitHub `YuhuaBillChen/npu-cosyvoice`): push `main` and the tag `v0.1.0`;
   compose.yml builds the speech images from that tag when they cannot be pulled.
   `git push origin main v0.1.0`
2. **Prebuilt speech files** (Hugging Face `billchen42/npu-cosyvoice`): int8 weights, LM GGUF, NPU
   overlay, `SHA256SUMS`. Without them `setup` builds them on the user's machine (~15 min).
   `hf upload billchen42/npu-cosyvoice ~/npu-cosyvoice-hf .`
3. **Container images** (GitHub Container Registry, optional but saves users a 20-40 min build).
   Build on an x86-64 machine from a clean checkout of each repo, then push and make each package
   public (github.com > Packages > package settings > visibility):

   | image | built from |
   |---|---|
   | `ghcr.io/yuhuabillchen/npu-cosyvoice-voice:0.1.0` | npu-cosyvoice `v0.1.0`, `docker/Dockerfile` target `voice` |
   | `ghcr.io/yuhuabillchen/npu-cosyvoice-whisper:0.1.0` | npu-cosyvoice `v0.1.0`, target `whisper` |
   | `ghcr.io/yuhuabillchen/local-voice-buddy-webui:0.1.0` | this repo, `webui/` |

   ```sh
   echo $GHCR_TOKEN | docker login ghcr.io -u YuhuaBillChen --password-stdin   # classic PAT with write:packages
   docker compose --profile setup build && docker compose --profile setup push setup whisper webui
   ```
4. **This repository** (GitHub `YuhuaBillChen/local_voice_buddy`): push `main` (and a `v0.1.0` tag).
5. **Website**: repository Settings > Pages > Deploy from branch `main`, folder `/docs`. It embeds
   the demo videos from npu-cosyvoice's Pages site, so enable Pages there too.

The chat model is downloaded straight from `unsloth/Qwen3.8-27B-GGUF` and is not republished.

When bumping a version, change the tag in compose.yml (`#v0.1.0` and the three image tags) together.
