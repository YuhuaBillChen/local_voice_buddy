"""Keep OWUI read-aloud going when TTS falls behind playback; safe to rerun.

Read-aloud also fetched one sentence at a time: the request for sentence N+1
went out only after sentence N's audio had arrived, so synthesis never
overlapped and each sentence cost LM + flow back to back (~6.5 s for ~5 s of
speech at 1.1x). It now keeps one request ahead, so the TTS server runs the LM
of sentence N+1 while the flow of sentence N runs; audio is still enqueued in
order. (Voice calls already request every chunk as soon as its text arrives.)

ResponseMessage.svelte enqueues each synthesized chunk only `if (res && speaking)`.
When the queue runs dry before the next chunk arrives, AudioQueue.next() fires
onStopped('empty-queue'), the handler sets speaking = false, and every later
chunk is fetched and then dropped. Enqueue while the read is not aborted (the
stop button aborts it) and mark it speaking again; enqueue() restarts playback.
"""
from pathlib import Path
import re
import sys

CHUNKS = Path("/app/build/_app/immutable/chunks")
# minified: if(be.aborted)return;if(lt&&e(w)){const Mt=await lt.blob(),Kt=URL.createObjectURL(Mt);I().enqueue(Kt),p(C,!1)}
STOCK = re.compile(
    r"if\((?P<sig>\w+)\.aborted\)return;"
    r"if\((?P<res>\w+)&&(?P<get>\w+)\((?P<speaking>\w+)\)\)\{"
    r"const (?P<blob>\w+)=await (?P=res)\.blob\(\),(?P<url>\w+)=URL\.createObjectURL\((?P=blob)\);"
    r"(?P<queue>\w+)\(\)\.enqueue\((?P=url)\),(?P<set>\w+)\((?P<loading>\w+),!1\)\}"
)
MARKER = "/*localllm-tts-playback*/"
# minified: for(const[,Yt]of Wt.entries()){if(be.aborted)return;const lt=await Us(localStorage.token,sr,Yt).catch(Mt=>{...});
FETCH = re.compile(
    r"for\(const\[,(?P<item>[\w$]+)\]of (?P<list>[\w$]+)\.entries\(\)\)\{if\((?P<sig>[\w$]+)\.aborted\)return;"
    r"const (?P<res>[\w$]+)=await (?P<tts>[\w$]+)\(localStorage\.token,(?P<voice>[\w$]+),(?P=item)\)"
    r"\.catch\((?P<handler>[\w$]+=>\{.{0,200}?\})\);(?=if\()"
)
AHEAD_MARKER = "/*localllm-tts-ahead*/"


def ahead(m: re.Match) -> str:
    g = m.groupdict()
    fetch = f"__i=>__i<{g['list']}.length?{g['tts']}(localStorage.token,{g['voice']},{g['list']}[__i]).catch({g['handler']}):null"
    return (
        f"for(let __i=0,__f=({fetch}),__n=__f(0);__i<{g['list']}.length;__i++){{{AHEAD_MARKER}"
        f"if({g['sig']}.aborted)return;const {g['item']}={g['list']}[__i],__c=__n;__n=__f(__i+1);"
        f"const {g['res']}=await __c;"
    )


def fixed(m: re.Match) -> str:
    g = m.groupdict()
    return (
        f"if({g['sig']}.aborted)return;"
        f"if({g['res']}&&!{g['sig']}.aborted){{{MARKER}"
        f"const {g['blob']}=await {g['res']}.blob(),{g['url']}=URL.createObjectURL({g['blob']});"
        f"if({g['sig']}.aborted)return;"
        f"{g['set']}({g['speaking']},!0),{g['queue']}().enqueue({g['url']}),{g['set']}({g['loading']},!1)}}"
    )


patched = ahead_done = 0
for path in CHUNKS.glob("*.js"):
    text = path.read_text()
    new = text
    if AHEAD_MARKER in new:
        ahead_done += 1
    elif len(FETCH.findall(new)) == 1 and (MARKER in new or STOCK.search(new)):
        new = FETCH.sub(ahead, new)
        ahead_done += 1
    if MARKER in new:
        patched += 1
    elif "URL.createObjectURL" in new and ".enqueue(" in new and STOCK.search(new):
        if len(STOCK.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected read-aloud enqueue sites; not patched")
        new = STOCK.sub(fixed, new)
        patched += 1
    if new != text:
        path.write_text(new)
        print(f"{path.name}: patched")

if patched != 1 or ahead_done != 1:
    sys.exit(f"expected one read-aloud loop (enqueue {patched}, fetch-ahead {ahead_done})")
print("read-aloud patches in place")
