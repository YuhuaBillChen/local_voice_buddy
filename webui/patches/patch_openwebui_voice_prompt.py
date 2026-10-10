"""Attach the voice-mode prompt once per voice session, not to the system prompt.

Stock OWUI (v0.11.4 middleware) inserts the voice-mode template at the very
beginning of the system message whenever a request comes from a voice call,
and not otherwise. The prefix of the whole conversation therefore differs
between call and typed turns, so every switch between the two invalidates the
prefix cache in llama.cpp and re-prefills the entire
conversation (2026-10-01: a 3.8K-token chat went from 3.6K cached tokens to
0 after leaving the call).

The first fix appended it to the latest user message instead. That kept the
prefix stable across switches, but the template then moved to the new message
on every voice turn: ~190 tokens removed from the previous turn and prefilled
again on the new one (~3 s per turn on a Ryzen 7 8845HS, 2026-10-06).

Now it is attached to the user message that started the current voice
session and stays there for every following voice turn, so the history is
byte-identical from turn to turn. A typed turn ends the session; the next
voice turn starts a new one. The anchor is the index of that user message,
kept in process memory per chat (single uvicorn worker): after an OWUI restart
the next voice turn simply becomes the anchor. Unsaved (temporary) chats keep
the latest-message behaviour. If the last message is not a user turn the
prompt is skipped. Safe to rerun; needs an OWUI restart.
"""
from pathlib import Path
import sys

PATH = Path("/app/backend/open_webui/utils/middleware.py")
MARKER = "localllm: voice prompt stays on the user turn that started the call"
STOCK = """                form_data['messages'] = add_or_update_system_message(
                    template,
                    form_data['messages'],
                )
"""
V1 = """                # localllm: voice prompt rides on the latest user turn so the
                # cached conversation prefix is the same in and out of a call.
                if form_data['messages'] and form_data['messages'][-1].get('role') == 'user':
                    form_data['messages'] = add_or_update_user_message(
                        '\\n\\n' + template,
                        form_data['messages'],
                    )
"""
NEW = f"""                # {MARKER}, so the
                # cached conversation prefix is the same in and out of a call and
                # identical from one voice turn to the next.
                messages = form_data['messages']
                user_turns = [i for i, m in enumerate(messages) if m.get('role') == 'user']
                if user_turns and messages[-1].get('role') == 'user':
                    chat_id = metadata.get('chat_id')
                    anchor = _VOICE_SESSION_ANCHORS.get(chat_id) if is_saved_chat_id(chat_id) else None
                    if anchor is None or anchor >= len(user_turns):
                        anchor = len(user_turns) - 1
                        if is_saved_chat_id(chat_id):
                            _VOICE_SESSION_ANCHORS[chat_id] = anchor
                    at = user_turns[anchor]
                    messages[at] = update_message_content(dict(messages[at]), '\\n\\n' + template, True)
"""
SESSION_END_ANCHOR = """    features = form_data.pop('features', None) or {}
"""
SESSION_END = """    features = form_data.pop('features', None) or {}
    if not features.get('voice'):
        # a typed turn ends the voice session (see the voice prompt below)
        _VOICE_SESSION_ANCHORS.pop(metadata.get('chat_id'), None)
"""
STATE_ANCHOR = "log = logging.getLogger(__name__)\n"
STATE = (
    STATE_ANCHOR
    + "\n# localllm: chat_id -> index (among user turns) of the message that started the\n"
    + "# current voice session; the voice prompt stays attached there.\n"
    + "_VOICE_SESSION_ANCHORS: dict = {}\n"
)
ANCHOR = "if await Config.get('task.voice.prompt.enable'):"

text = PATH.read_text()
if MARKER in text:
    print("voice prompt patch already applied")
    sys.exit(0)
start = text.find(ANCHOR)
old = next((o for o in (V1, STOCK) if 0 <= text.find(o, max(start, 0)) and start >= 0), None)
if old is None or text.find(old, start) - start > 400:
    sys.exit("unexpected voice-prompt injection; not patched")
if text.count(SESSION_END_ANCHOR) != 1 or text.count(STATE_ANCHOR) != 1:
    sys.exit("unexpected middleware layout; not patched")
at = text.find(old, start)
new = text[:at] + NEW + text[at + len(old):]
new = new.replace(SESSION_END_ANCHOR, SESSION_END, 1).replace(STATE_ANCHOR, STATE, 1)
if "update_message_content" not in new.split("\nlog = ", 1)[0]:
    if "    add_or_update_system_message,\n" not in new:
        sys.exit("cannot find the helper import to extend; not patched")
    new = new.replace(
        "    add_or_update_system_message,\n",
        "    add_or_update_system_message,\n    update_message_content,\n",
        1,
    )
if "is_saved_chat_id" not in new.split("\nlog = ", 1)[0]:
    sys.exit("is_saved_chat_id is not imported; not patched")
compile(new, str(PATH), "exec")
PATH.write_text(new)
print("voice prompt patch applied; restart open-webui")
