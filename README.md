# Local Voice Buddy

A voice assistant that runs entirely on one Ryzen AI mini PC. You talk, it answers out loud, and
nothing leaves the machine: no account, no cloud, no subscription.

- **Chat**: Open WebUI in the browser, on the PC itself, a laptop or a phone at home
- **Brain**: Qwen3.8-27B, a 27-billion-parameter open model, on the Radeon iGPU
- **Ears and mouth**: speech recognition (Whisper large-v3-turbo) and a natural voice
  (CosyVoice3) on the Ryzen AI NPU, which otherwise sits idle; it can also speak in a voice you record
- Chinese and English, mixed freely

Website: <https://yuhuabillchen.github.io/local_voice_buddy/>

## What you need

| | |
|---|---|
| computer | a mini PC or laptop with a **Ryzen AI 7040 or 8040** CPU (for example Ryzen 7 7840HS / 8845HS, Ryzen 9 8945HS) |
| memory | **32 GB** |
| disk | 60 GB free |
| system | Linux with kernel 6.14 or newer (tested on Ubuntu 26.04 LTS) and [Docker](https://docs.docker.com/engine/install/) |

Ryzen AI 300 ("Strix") and machines with less memory are not supported yet.

## Install

```sh
git clone https://github.com/YuhuaBillChen/local_voice_buddy.git
cd local_voice_buddy
./install.sh
```

The installer checks the machine and asks for your password (sudo) for up to three system changes,
each explained before it asks:

1. keep the NPU from power-saving, which can otherwise crash the speech services when memory is tight;
2. let the GPU use 24 GB of system memory (the model needs more than Linux allows by default). This
   one needs a reboot; run `./install.sh` again afterwards;
3. add 8 GB of swap if there is less than 4 GB, for the moment after a reboot when all three models
   load at once.

Then it downloads the chat model (16.5 GB), the speech models (~5 GB) and the programs (~10 GB), and
starts everything. When it says **Ready**, open <http://localhost:3000>, create your account (the
first one is the admin), and press the round voice button at the right end of the message box to
start talking.

It starts by itself after every reboot. On the very first start the speech recognizer spends a few
minutes preparing itself for the NPU. In a conversation, the reply starts speaking about 8 to 10
seconds after you stop talking (the first message of a new chat takes about 20).

## Use it from your phone

Open `http://<the PC's address>:3000` on any device at home. Typing works right away. Accounts
other people create wait for your approval under Admin Settings > Users, unless you set the default
role there to "user". Browsers only allow the microphone on secure (https) pages, though, so for
talking from another device the simplest route is [Tailscale](https://tailscale.com) (free for personal use), which also works away
from home:

```sh
# on the PC, after installing Tailscale and turning on HTTPS in its admin console
sudo tailscale serve --bg 3000
```

Then open `https://<pc-name>.<your-tailnet>.ts.net` on the phone (with Tailscale on). In Chrome or
Edge, "Install app" puts it on the home screen like a normal app.

## Your own voice

Record 5 to 15 seconds of clear speech (yourself, or someone who agreed to it), save it as
`myvoice.wav`, and write exactly what is said into `myvoice.txt`. Then:

```sh
docker compose cp myvoice.wav voice:/data/voices/myvoice.wav
docker compose cp myvoice.txt voice:/data/voices/myvoice.txt
docker compose restart voice
```

and choose `myvoice` in Open WebUI under Settings > Audio > Voice. A voice keeps the accent of its
recording, so an English recording reads English best.

## Settings

Edit `.env` and run `docker compose up -d`:

| setting | default | |
|---|---|---|
| `CONTEXT` | 32768 | how much of the conversation the model keeps in view, in tokens |
| `THINKING` | off | `on` lets the model think before answering: better at hard questions, too slow for talking |
| `SPEECH_SPEED` | 1.1 | speaking speed |
| `VOICE` | default | voice Open WebUI starts with; read on its first start only, afterwards Admin Settings > Audio |
| `WEBUI_PORT` | 3000 | |

## Everyday commands

```sh
docker compose ps              # what is running
docker compose logs -f voice   # what the voice is doing (also: llm, whisper, webui)
docker compose stop            # stop everything (start again: docker compose up -d)
git pull && ./install.sh      # update
```

Chats and accounts live in the `webui-data` Docker volume; `docker compose down` keeps them,
`docker compose down -v` deletes them together with the speech models.

## How it fits together

```
 browser ──► webui (Open WebUI, port 3000)
               ├─► llm      llama.cpp, Qwen3.8-27B on the iGPU (Vulkan)
               └─► voice    CosyVoice3 text-to-speech on the NPU ──► whisper  speech-to-text on the NPU
```

The speech side is [npu-cosyvoice](https://github.com/YuhuaBillChen/npu-cosyvoice), which has its
own README and a technical report; this repository combines it with a chat model and a
ready-to-use interface. `webui/patches/` are small fixes to Open WebUI's voice mode, each explained
at the top of its file: Chinese replies start speaking sentence by sentence instead of after the
whole answer, recognition starts while you pause rather than after, read-aloud fetches the next
sentence while one plays, sentences are not cut mid-word, and phones no longer go silent after a
few replies.

Memory use and response times, measured on a 32 GB Ryzen 7 8845HS: [docs/measurements.md](docs/measurements.md).

## Licenses

This repository: Apache-2.0. It downloads and runs, without modifying them except as noted:
Open WebUI (its own license: BSD-3-Clause plus keeping the Open WebUI branding, which stays as is;
patched at build time by `webui/patches/`), llama.cpp (MIT), Qwen3.8-27B (Apache-2.0, GGUF by Unsloth), npu-cosyvoice
(Apache-2.0) with CosyVoice3 (Apache-2.0) and whisper-xdna (MIT). See NOTICE.
