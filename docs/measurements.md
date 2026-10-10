# Measurements

Ryzen 7 8845HS (Radeon 780M, XDNA1 NPU), 32 GB RAM of which Linux sees 27.7 GB (the BIOS reserves 3 GB
for the GPU), Ubuntu 26.04, kernel 7.0, default settings (`CONTEXT=32768`, `THINKING=off`). 2026-10-10.

## Memory

| | |
|---|---|
| chat model (`llm`) | 14.1 GB GPU-mapped system memory (model + context) + 3 GB BIOS GPU reserve + 1.3 GB process |
| speech recognition (`whisper`) | 5.9 GB, of which 1.4 GB NPU buffers |
| text-to-speech (`voice`) | 2.3 GB |
| web interface (`webui`) | 0.7 GB |
| **all together** | **~24.3 GB of 27.7 GB**; ~3 GB left for the system |

Starting from nothing, the services load one after another (chat model, voice, recognizer); all were
ready after 83 s, and the peak was ~25 GB. After a reboot Docker starts them all at once, which is why
the installer asks for at least 4 GB of swap.

## Response time in a voice call

Headless Chrome with a recorded voice as the microphone, three turns (Chinese, Chinese, English).
"First sound" is from the end of the spoken question to the first audio of the reply, and includes
the 1.2 s of silence after which the call decides you have finished.

| turn | first sound |
|---|---|
| first message of a new chat | 19.6 s |
| later messages | 8.0 s, 9.5 s |

Where the time goes in a later turn: speech recognition 3.0 s (it starts 0.5 s into your pause, so
most of it overlaps the 1.2 s wait), the model's first sentence 2-3 s, synthesizing that sentence
3-4 s. The first message of a chat is slower because the model reads Open WebUI's ~700-token setup
first (~10 s at ~75 tokens/s); later turns reuse it from the cache.

## Chat model

| | |
|---|---|
| generation | 7-11 tokens/s (Qwen3.8's built-in multi-token prediction accepts 45-100% of drafted tokens) |
| reading the prompt | 70-80 tokens/s |
