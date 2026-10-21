# Measurements

Ryzen 7 8845HS (Radeon 780M, XDNA1 NPU), 32 GB RAM of which Linux sees 27.7 GB (the BIOS reserves 3 GB
for the GPU), Ubuntu 26.04, kernel 7.0, default settings. Version 0.1.2 (Open WebUI v0.12.3), 2026-10-20.

## Installing

A clean install from a fresh clone, with the images built on the machine rather than pulled: about 7
minutes to download the chat model (at 40 MB/s), about 10 minutes to build the speech images and
prepare the speech models when the prebuilt files are not used, and 2 minutes on the first start for
the speech recognizer to compile its NPU programs. The CosyVoice3 checkpoint comes from ModelScope,
whose speed varies a lot: 3 GB took a few minutes one day and was heading for 40 minutes the next.

## Memory

| | |
|---|---|
| chat model (`llm`) | 14.1 GB GPU-mapped system memory (model + context) + 3 GB BIOS GPU reserve + 0.7 GB process |
| speech recognition (`whisper`) | 5.9 GB, of which 1.4 GB NPU buffers |
| text-to-speech (`voice`) | 3.0 GB |
| web interface (`webui`) | 1.0 GB |
| **all together** | **~25 GB of 27.7 GB** |

The services load one after another (chat model, voice, recognizer). After a reboot Docker starts them
all at once, which briefly needs more; that is why the installer asks for at least 4 GB of swap.

## Response time in a voice call

Headless Chrome with recorded speech as the microphone (the website recordings, see [demos.md](demos.md)),
two turns in Chinese and two in English, plus the earlier run on Open WebUI v0.12.0 with the same speech
and chat services. "First sound" is from the end of the spoken question to the first audio of the reply,
and includes the 1.2 s of silence after which the call decides you have finished.

| turn | first sound |
|---|---|
| very first message after the services start | 20.5 s |
| first message of another new chat | 7.8, 9.2, 16.9 s |
| later messages | 8.3, 10.2, 10.3, 10.9, 11.8, 12.5 s |

Where the time goes in a later turn: speech recognition about 3.3 s (it starts 0.85 s into your pause,
so part of it overlaps the 1.2 s wait), the model's first sentence 2-3 s, synthesizing that sentence
4-5 s while the model keeps writing. The very first message is slower because the model reads Open
WebUI's ~700-token setup first (~10 s at ~70 tokens/s); after that it is cached, also for new chats.

## Visual answers (0.1.2)

From pressing Enter to the finished drawing, including typing the question: a pie chart from five
monthly expenses took 38 s (English) and 45-64 s (Chinese, four runs); a comparison table with a
recommendation card took 87-98 s. The tool descriptions make a new typed chat's opening 921 tokens
instead of 698. Voice calls do not carry them, so the first message of a voice call right after typed
chats has to read its own opening once (20.7 s to first sound in that run instead of 8-9 s); later
turns were unaffected (11.3 s).

## Voice quality settings

Sentences are synthesized with 4 to 10 flow steps, more when there is time: the first sentence of a
reply uses 4, later ones up to 10 as the queue of audio waiting to be played grows. While the chat
model is still writing, the machine is busy and most sentences use 4-6. Over the six recordings: 33
sentences with 4 steps, 11 with 5-9, 25 with 10 (mostly read-aloud, where nothing else is running).

Speech recognition decodes greedily (`STT_BEAM_SIZE=1`). Beam search (5) fixed one short Mandarin
clip in our tests but broke an English one ("cloned" became "clone") and added 0.2-0.8 s.

## Chat model

| | |
|---|---|
| generation | 7-11 tokens/s (Qwen3.8's built-in multi-token prediction accepts 45-100% of drafted tokens) |
| reading the prompt | 70-80 tokens/s |
