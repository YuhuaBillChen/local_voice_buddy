# How the website recordings were made

Eight screen recordings (Chinese and English versions of four), made on 2026-10-17 (the first three) and 2026-10-21 (visual answers) on a Ryzen 7 8845HS
with a fresh install of this repository (Open WebUI v0.12.3 with the patches in `webui/`, the bundled
27B, recognition and speech), in desktop Chrome, with a separate demo account:

- `voice-mode`: start a voice call, ask why it rains, listen to the whole answer, then ask what to
  bring outside. Speech starts while the rest of the answer is still being written.
- `voice-input`: dictate "tell my friend I'll be 10 minutes late", check the recognized text, add an
  instruction by typing, send.
- `read-aloud`: press Read Aloud on that reply.
- `visual`: type five monthly expenses and ask for a pie chart; the 27B draws it in the chat
  (version 0.1.2). The recording ends by scrolling back to the chart.

Recognition, the 27B's replies and the speech are generated live; nothing is pre-rendered and the
waiting time is not cut. The questions are synthetic speech fed in as the microphone, so the demos
can be repeated.

Chrome was captured at about 10 frames per second with its audio (microphone input and playback);
only idle time after the last playback is trimmed. Hashes, versions and per-video checks:
[demos-validation-20261017.json](demos-validation-20261017.json).
