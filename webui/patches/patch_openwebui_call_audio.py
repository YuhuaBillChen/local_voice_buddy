"""Fix OWUI voice-call mode audio; safe to rerun after OWUI recreation.

1. Stream leak (open-webui #29969): CallOverlay.svelte caches one
   `new Audio(blobUrl)` per spoken chunk and never releases them. Android
   Chrome allows 10 open output audio streams per process, so after a few
   replies every later play() fails silently. playAudio() only reads `.src`
   and plays through the single #audioElement, so cache a plain {src}.

2. Chinese never streams: Chat.svelte's dispatchCallOverlayAudio() holds back
   any chunk with < 4 whitespace-separated words or < 50 chars until the reply
   is finished. CJK has no spaces, so every Chinese chunk was held and TTS got
   nothing until the whole answer was done. A CJK chunk is now held only
   while it is shorter than the splitter's smallest chunk (4 characters, see
   patch_openwebui_tts_split.py). The same 4-word / 50-character hold applied
   to English cancelled the splitter's short first English chunk, so English
   is now held only under 3 words or 15 characters.

3. AudioContext leak: every finished utterance restarts recording, and
   analyseAudio() builds a new AudioContext each time without ever closing it.
   They stay alive because the one mic stream they read never ends. Android
   Chrome allows 10 open output audio streams per process; once they are gone
   every play() in the process is silent - call replies, read aloud, all - until
   the PWA process is restarted. Reuse one context (disconnecting the previous
   turn's source) and close it when the call overlay closes.

4. Same leak in the message box's dictation button (VoiceRecording.svelte):
   each recording creates an AudioContext for the level meter and never closes
   it. Close it when the recording ends.

5. Empty recordings: a VAD barge-in can stop the recorder right after it was
   restarted, and the call overlay then uploads a header-only WAV (110 bytes,
   2026-10-06). Its own guard skips only blobs under 100 bytes, so STT got the
   file, ffmpeg failed to decode it and the user saw an error instead of the
   call simply listening again. Skip anything under 1 KB (the shortest real
   utterance seen was 17 KB).

6. Silence during tool calls: the model usually calls a tool without saying
   anything first, so a voice call went quiet until the tool finished. When a
   message gets a tool call before any text, the call overlay now speaks a
   short filler ("我查一下。" / "Let me check.", by the language of the user's
   message) through the normal TTS path, once per message. Prompting the model
   to say it worked for English but almost never for Chinese (2/6, 2026-10-07).

7. Muted read-aloud after a call: the overlay mutes the shared #audioElement
   before each play() and unmutes only once playback has started; its
   interrupt (also run when the call is closed) mutes and pauses without
   unmuting, and an aborted play() never unmutes either. Read-aloud uses the
   same element, so after leaving a call mid-speech it "played" in silence
   until the page was reloaded. The element is now unmuted after the
   interrupt's pause and whenever an overlay playback settles.

8. Speech recognition starts during the end-of-speech pause: the overlay stops
   recording only after 1.2 s of silence and only then uploads the utterance,
   so STT (~2.5 s on the NPU, almost all of it the Whisper encoder, which has
   to see the whole window and cannot be fed incrementally) ran strictly after
   that wait. After 0.5 s of silence the overlay now asks the recorder for the
   audio so far and starts transcribing it. If no sound follows before the
   recorder stops, that result is used instead of uploading the recording
   again (the rest is silence); any sound discards it. A pause the user talks
   through costs one wasted NPU run, which can delay the next transcription by
   up to its remaining ~2 s.
"""
from pathlib import Path
import re
import sys

CHUNKS = Path("/app/build/_app/immutable/chunks")

# minified: Ue.set(ue,new Audio(Ct))  (TTS engine and browser-kokoro branches)
LEAK = re.compile(r"\.set\((\w+),new Audio\((\w+)\)\)")
LEAK_MARKER = "/*localllm-call-audio*/"
# minified: (He.split(/\s+/).length<4||He.length<50)
HOLD = re.compile(r"\((\w+)\.split\(/\\s\+/\)\.length<4\|\|\1\.length<50\)")
HOLD_MARKER = "/*localllm-call-cjk*/"
CJK_HOLD_CHARS = 4
# same as the splitter's smallest English chunk
EN_HOLD_WORDS = 3
EN_HOLD_CHARS = 15
# an earlier version of this patch held CJK chunks under 6 characters
HOLD_V1 = re.compile(r"(" + re.escape(HOLD_MARKER) + r"/\[\\u3400-\\u9fff\]/\.test\((\w+)\)\?\2\.length<)6:")
# earlier versions kept the stock English hold (4 words, 50 characters)
HOLD_EN_V1 = re.compile(r"(" + re.escape(HOLD_MARKER) + r"/\[\\u3400-\\u9fff\]/\.test\((\w+)\)\?\2\.length<\d+:\2)\.split\(/\\s\+/\)\.length<4\|\|\2\.length<50\)")
# minified: const me=new AudioContext,Ne=me.createMediaStreamSource(ue),Ye=me.createAnalyser();
AC_NEW = re.compile(
    r"const (\w+)=new AudioContext,(\w+)=\1\.createMediaStreamSource\((\w+)\),(\w+)=\1\.createAnalyser\(\);"
)
# minified: catch(ue){}r(S)&&(r(S).getAudioTracks().forEach(function(ue){ue.stop()}),c(S,null))
AC_STOP = re.compile(r"(catch\(\w+\)\{\})(\w+\(\w+\)&&\(\w+\(\w+\)\.getAudioTracks\(\)\.forEach)")
AC_MARKER = "/*localllm-call-ac*/"
# minified (dictation level meter): Re=e=>{const t=new AudioContext,r=t.createMediaStreamSource(e),...
#   (()=>{const y=()=>{if(!(!m()||o(l))){...window.requestAnimationFrame(y)}};window.requestAnimationFrame(y)})()
DICT_CTX = re.compile(r"const (\w+)=new AudioContext,\w+=\1\.createMediaStreamSource\(\w+\),")
DICT_LOOP = re.compile(r"=\(\)=>\{(if\(!\(!(\w+)\(\)\|\|)")
DICT_MARKER = "/*localllm-dict-ac*/"
# minified: if(!ue||ue.size<100)return;
EMPTY = re.compile(r"if\(!(\w+)\|\|\1\.size<100\)return;")
EMPTY_MARKER = "/*localllm-call-empty*/"
# minified: Bt=(w,C=!1)=>{var fe,Ae,at;if(!W())return;...Fo(w==null?void 0:w.output)...De.dispatchEvent(new CustomEvent("chat"
FILLER_FN = re.compile(r"=\((\w+),\w+=!1\)=>\{var [\w,]+;if\(!\w+\(\)\)return;")
FILLER_MARKER = "/*localllm-call-filler*/"
# minified: const w=r(je)?Ys(r(je),r(je).currentId):[]
HISTORY = re.compile(r"=(\w+)\((\w+)\)\?\w+\(\1\(\2\),\1\(\2\)\.currentId\)")
# minified: ue&&(ue.muted=!0,ue.pause(),ue.currentTime=0)   (interrupt)
INTERRUPT_MUTE = re.compile(r"(\w+)&&\(\1\.muted=!0,\1\.pause\(\),\1\.currentTime=0\)")
# minified: const ye=async(It=null)=>{Ye||(Ye=!0,Ne.onended=null,Ne.onerror=null,Ne.onpause=null,
SETTLE = re.compile(r"(\w+)\|\|\(\1=!0,(\w+)\.onended=null,\2\.onerror=null,\2\.onpause=null,")
UNMUTE_MARKER = "/*localllm-call-unmute*/"
# minified: ,It=Date.now()),$&&Date.now()-It>1200&&(j=!0,x)){x.stop();return}
SILENCE_STOP = re.compile(r",([\w$]+)=Date\.now\(\)\),([\w$]+)&&Date\.now\(\)-\1>1200&&\(([\w$]+)=!0,([\w$]+)\)\)\{\4\.stop\(\);return\}")
# minified: x.ondataavailable=ue=>{$&&P.push(ue.data)}
CHUNKS_PUSH = re.compile(r"([\w$]+)\.ondataavailable=([\w$]+)=>\{[\w$]+&&([\w$]+)\.push\(\2\.data\)\}")
# minified: me=Hm(ue,"recording.wav"),Ne=await _0(localStorage.token,me,(ct=(ye=(Ye=i())==null?void 0:Ye.audio)...).catch(
UPLOAD = re.compile(r"([\w$]+)=([\w$]+)\([\w$]+,\"recording\.wav\"\),([\w$]+)=await ([\w$]+)\((localStorage\.token,\1,\([\w$]+=\([\w$]+=\([\w$]+=([\w$]+)\(\)\)[^;]{0,120}?\.language)\)\.catch\(")
SPEC_MARKER = "/*localllm-call-spec*/"
SPEC_AFTER_MS = 500
CLOSE_AC = 'window.__llAC&&(window.__llAC.close().catch(()=>{}),window.__llAC=null,window.__llSrc=null);'


def cjk_hold(m: re.Match) -> str:
    v = m.group(1)
    return (
        f"({HOLD_MARKER}/[\\u3400-\\u9fff]/.test({v})?{v}.length<{CJK_HOLD_CHARS}:"
        f"{v}.split(/\\s+/).length<{EN_HOLD_WORDS}||{v}.length<{EN_HOLD_CHARS})"
    )


def shared_ac(m: re.Match) -> str:
    ctx, src, stream, analyser = m.groups()
    return (
        f"const {ctx}=(window.__llAC&&window.__llAC.state!==\"closed\"?window.__llAC:(window.__llAC=new AudioContext)),"
        f"{src}=({ctx}.state===\"suspended\"&&{ctx}.resume(),window.__llSrc&&window.__llSrc.disconnect(),"
        f"window.__llSrc={ctx}.createMediaStreamSource({stream})),{analyser}={ctx}.createAnalyser();{AC_MARKER}"
    )


def tool_filler(text: str) -> str | None:
    """Speak a filler when a message calls a tool before saying anything."""
    anchor = text.find(".ttsSentContentPartCount??0")
    if anchor < 0:
        return None
    fns = [m for m in FILLER_FN.finditer(text, 0, anchor) if anchor - m.end() < 900]
    if len(fns) != 1:
        sys.exit("unexpected call-overlay chunk dispatcher; not patched")
    fn = fns[0]
    msg = fn.group(1)
    body = text[fn.end():anchor]
    out = re.search(r"(\w+)\(" + msg + r"==null\?void 0:" + msg + r"\.output\)", body)
    target = re.search(r"(\w+)\.dispatchEvent\(new CustomEvent\(\"chat\"", text[fn.end():fn.end() + 1500])
    hist = HISTORY.search(text)
    if not (out and target and hist):
        sys.exit("unexpected call-overlay names; tool filler not patched")
    get, history = hist.group(1), hist.group(2)
    user = f"(({get}({history})||{{}}).messages||{{}})[{msg}.parentId]"
    filler = (
        f"{FILLER_MARKER}if(!{msg}.__llFiller&&Array.isArray({msg}.output)"
        f"&&{msg}.output.some(o=>o&&o.type===\"function_call\")&&!({out.group(1)}({msg}.output)||\"\").trim())"
        f"{{{msg}.__llFiller=1;const u=({user}||{{}}).content;"
        f"{target.group(1)}.dispatchEvent(new CustomEvent(\"chat\",{{detail:{{id:{msg}.id,"
        f"content:/[\\u3400-\\u9fff]/.test(typeof u==\"string\"?u:\"\")?\"我查一下。\":\"Let me check.\"}}}}))}}"
    )
    return text[:fn.end()] + filler + text[fn.end():]


def early_stt(text: str) -> str | None:
    """Start STT at 0.5 s of silence; None if this chunk is not the call overlay."""
    stop = SILENCE_STOP.search(text)
    if not stop:
        return None
    push, upload = CHUNKS_PUSH.search(text), UPLOAD.search(text)
    if len(SILENCE_STOP.findall(text)) != 1 or not push or not upload or "__ll=" not in text:
        sys.exit("unexpected call-overlay recorder code; early STT not patched")
    last, speaking, done_flag, rec = stop.groups()
    chunks = push.group(3)
    wav, transcribe, args, settings = upload.group(2), upload.group(4), upload.group(5), upload.group(6)
    lang = f"((({settings}()||{{}}).audio||{{}}).stt||{{}}).language"
    start = (
        f"{SPEC_MARKER}({speaking}&&Date.now()-{last}>{SPEC_AFTER_MS}&&{rec}&&{rec}.state===\"recording\""
        f"&&window.__llSpecAt!=={last}&&(s=>{{window.__llSpecAt=s;{rec}.addEventListener(\"dataavailable\",()=>{{"
        f"window.__llSpecAt===s&&(window.__llSpec={{at:s,p:{transcribe}(localStorage.token,"
        f"{wav}(new Blob({chunks}.slice(0),{{type:\"audio/wav\"}}),\"recording.wav\"),{lang}).catch(()=>null)}},"
        f"__ll(\"stt:early\"))}},{{once:!0}});{rec}.requestData()}})({last}))"
    )
    text = (text[:stop.start()]
            + f",{last}=Date.now(),window.__llSpecAt=null,window.__llSpec=null),{start},"
            + f"{speaking}&&Date.now()-{last}>1200&&({done_flag}=!0,{rec})){{{rec}.stop();return}}"
            + text[stop.end():])
    upload = UPLOAD.search(text)
    use = (
        f"{upload.group(1)}={upload.group(2)}(ue,\"recording.wav\"),{upload.group(3)}=await (async()=>{{"
        f"const s=window.__llSpec,a=window.__llSpecAt;window.__llSpec=null;window.__llSpecAt=null;"
        f"if(s&&s.at===a){{const r=await s.p;if(r){{__ll(\"stt:early-hit\");return r}}}}"
        f"return {transcribe}({args})}})().catch("
    )
    # the blob parameter name is whatever the upload line used
    blob = re.match(r"\w+=\w+\((\w+),", upload.group(0)).group(1)
    use = use.replace("(ue,", f"({blob},", 1)
    return text[:upload.start()] + use + text[upload.end():]


def close_dictation_ctx(text: str) -> str | None:
    """Patch the dictation meter; None if this chunk is not that component."""
    ctx = DICT_CTX.search(text)
    if not ctx or "getDisplayMedia" not in text:
        return None
    loop = DICT_LOOP.search(text, ctx.end())
    if not loop or loop.start() - ctx.end() > 600:
        sys.exit("unexpected dictation level-meter code; not patched")
    recording = loop.group(2)
    stop = f"{DICT_MARKER}if(!{recording}()){{{ctx.group(1)}.close().catch(()=>{{}});return}}"
    return text[:loop.start()] + "=()=>{" + stop + loop.group(1) + text[loop.end():]


done = {"leak": 0, "hold": 0, "ac": 0, "dict": 0, "empty": 0, "filler": 0, "unmute": 0, "spec": 0}
for path in CHUNKS.glob("*.js"):
    text = path.read_text()
    new = text
    if LEAK_MARKER in new:
        done["leak"] += 1
    elif "audioElement" in new and "new Audio(" in new and LEAK.search(new):
        if len(LEAK.findall(new)) != 2:
            sys.exit(f"{path.name}: unexpected call-audio cache sites; not patched")
        new = LEAK_MARKER + LEAK.sub(r".set(\1,{src:\2})", new)
        done["leak"] += 1
    if HOLD_MARKER in new:
        new = HOLD_V1.sub(lambda m: f"{m.group(1)}{CJK_HOLD_CHARS}:", new)
        new = HOLD_EN_V1.sub(
            lambda m: f"{m.group(1)}.split(/\\s+/).length<{EN_HOLD_WORDS}||{m.group(2)}.length<{EN_HOLD_CHARS})",
            new,
        )
        done["hold"] += 1
    elif "ttsSentContentPartCount" in new:
        if len(HOLD.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected call-audio hold-back check; not patched")
        new = HOLD.sub(cjk_hold, new)
        done["hold"] += 1
    if AC_MARKER in new:
        done["ac"] += 1
    elif AC_NEW.search(new) and AC_STOP.search(new):
        if len(AC_NEW.findall(new)) != 1 or len(AC_STOP.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected audio-context code; not patched")
        new = AC_STOP.sub(lambda m: m.group(1) + CLOSE_AC + m.group(2), AC_NEW.sub(shared_ac, new))
        done["ac"] += 1
    if DICT_MARKER in new:
        done["dict"] += 1
    else:
        patched_dict = close_dictation_ctx(new)
        if patched_dict is not None:
            new = patched_dict
            done["dict"] += 1
    if UNMUTE_MARKER in new:
        done["unmute"] += 1
    elif INTERRUPT_MUTE.search(new) and SETTLE.search(new):
        if len(INTERRUPT_MUTE.findall(new)) != 1 or len(SETTLE.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected call-overlay audio mute sites; not patched")
        new = INTERRUPT_MUTE.sub(
            lambda m: f"{m.group(1)}&&({m.group(1)}.muted=!0,{m.group(1)}.pause(),{m.group(1)}.currentTime=0,{m.group(1)}.muted=!1{UNMUTE_MARKER})",
            new,
        )
        new = SETTLE.sub(
            lambda m: f"{m.group(1)}||({m.group(1)}=!0,{m.group(2)}.muted=!1,{m.group(2)}.onended=null,{m.group(2)}.onerror=null,{m.group(2)}.onpause=null,",
            new,
        )
        done["unmute"] += 1
    if FILLER_MARKER in new:
        done["filler"] += 1
    else:
        patched_filler = tool_filler(new)
        if patched_filler is not None:
            new = patched_filler
            done["filler"] += 1
    if SPEC_MARKER in new:
        done["spec"] += 1
    else:
        patched_spec = early_stt(new)
        if patched_spec is not None:
            new = patched_spec
            done["spec"] += 1
    if EMPTY_MARKER in new:
        done["empty"] += 1
    elif "recording.wav" in new and EMPTY.search(new):
        if len(EMPTY.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected empty-recording guard; not patched")
        new = EMPTY.sub(lambda m: f"if(!{m.group(1)}||{m.group(1)}.size<1000)return;{EMPTY_MARKER}", new)
        done["empty"] += 1
    if new != text:
        path.write_text(new)
        print(f"{path.name}: patched")

if done != {"leak": 1, "hold": 1, "ac": 1, "dict": 1, "empty": 1, "filler": 1, "unmute": 1, "spec": 1}:
    sys.exit(f"expected one of each call-audio / dictation patch site, found {done}")
print("call audio patches in place")
