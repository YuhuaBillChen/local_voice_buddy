"""Cut fixed per-turn waits in OWUI's send path and voice loop; safe to rerun.

1. Location refresh no longer blocks sending. With Settings > Interface >
   userLocation on, Chat.svelte awaits navigator.geolocation.getCurrentPosition
   (no maximumAge, so a fresh fix every time, ~3.5 s on Android) before every
   request. The result only refreshes the profile string that the
   get_current_location tool reads, so fire it in the background instead.

2. Voice call end-of-speech silence 2000 ms -> 1200 ms (CallOverlay analyseAudio).

3. Wait (up to 5 s) for the socket before sending. The request carries
   session_id = socket.id; without it OWUI treats the request as a plain API
   call and attaches no builtin tools (time, location, web search) and runs
   it synchronously. A PWA resumed from the background sends before its
   socket has reconnected; the stock 3.5 s location await used to hide that
   race (2026-09-30: a resumed turn went out with 0 tools).
"""
from pathlib import Path
import os
import re
import sys

CHUNKS = Path(os.environ.get("OWUI_CHUNKS", "/app/build/_app/immutable/chunks"))
MARKER = "/*localllm-call-latency*/"
SILENCE_MS = 1200

# minified: await jt();let xt;(Mt=n())!=null&&Mt.userLocation&&(xt=await $p(localStorage.token).catch(zt=>{}));const pt=
LOCATION = re.compile(
    r"let ([\w$]+);\(([\w$]+)=([\w$]+)\(\)\)!=null&&\2\.userLocation&&\(\1=await ([\w$]+)\(localStorage\.token\)\.catch\(([\w$]+)=>\{\}\)\);"
)
# minified: $&&Date.now()-It>2e3&&(j=!0,x)
SILENCE = re.compile(r"(Date\.now\(\)-[\w$]+)>2e3(&&\([\w$]+=!0,[\w$]+\))")
# minified: session_id:(fo=z())==null?void 0:fo.id
SESSION = re.compile(r"session_id:\(([\w$]+)=([\w$]+)\(\)\)==null\?void 0:\1\.id")
# the location statement after fix_location (stock or patched)
LOCATION_PATCHED = re.compile(
    r"let ([\w$]+);\(([\w$]+)=([\w$]+)\(\)\)!=null&&\2\.userLocation&&([\w$]+)\(localStorage\.token\)\.catch\(([\w$]+)=>\{\}\);"
)
SOCKET_MARKER = "/*localllm-socket-wait*/"


def fix_location(m: re.Match) -> str:
    var, tmp, settings, fn, err = m.groups()
    return (
        f"let {var};({tmp}={settings}())!=null&&{tmp}.userLocation&&"
        f"{fn}(localStorage.token).catch({err}=>{{}});"
    )


def socket_wait(text: str) -> str:
    getters = set(m.group(2) for m in SESSION.finditer(text))
    sites = LOCATION_PATCHED.findall(text)
    if len(getters) != 1 or len(sites) != 1:
        sys.exit(f"unexpected session_id/location code (getters {getters}, sites {len(sites)}); not patched")
    socket = getters.pop()
    wait = (
        f"{SOCKET_MARKER}await(async()=>{{for(let _w=0;_w<50&&!({socket}()&&{socket}().connected);_w++)"
        "await new Promise(_r=>setTimeout(_r,100))})();"
    )
    return LOCATION_PATCHED.sub(lambda m: m.group(0) + wait, text)


done = 0
for path in CHUNKS.glob("*.js"):
    text = path.read_text()
    if "ttsSentContentPartCount" not in text:
        continue
    new = text
    if MARKER not in new:
        if len(LOCATION.findall(new)) != 1 or len(SILENCE.findall(new)) != 1:
            sys.exit(f"{path.name}: unexpected send/VAD code (location {len(LOCATION.findall(new))}, silence {len(SILENCE.findall(new))}); not patched")
        new = LOCATION.sub(fix_location, new)
        new = SILENCE.sub(lambda m: f"{m.group(1)}>{SILENCE_MS}{m.group(2)}", new)
        new = MARKER + new
    if SOCKET_MARKER not in new:
        new = socket_wait(new)
    if new != text:
        path.write_text(new)
        print(f"{path.name}: patched")
    else:
        print(f"{path.name}: already patched")
    done += 1
if done != 1:
    sys.exit(f"expected exactly one chat/call-overlay chunk, found {done}")
print("call latency patch in place")
