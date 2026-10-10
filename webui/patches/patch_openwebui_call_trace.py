"""Diagnostic: beacon the OWUI call-overlay's audio lifecycle to the backend log.

Reproducing Android Chrome media behaviour off-device is not possible, so this
instruments CallOverlay.svelte's minified chunk with GET /api/version?ll=<event>
beacons (uvicorn logs the query string). Events: start/chunk/finish (Chat.svelte
-> overlay), play:start/playing/ended/pause/error/reject (#audioElement),
interrupt:<vad|tap>, loop:wait/done/exit, rec:stop, stt, submitted.

Only lengths and timings are logged, never text. Safe to rerun; remove with a fresh OWUI image.
Set OWUI_CHUNKS to dry-run on a copy.
"""
from pathlib import Path
import os
import re
import sys

CHUNKS = Path(os.environ.get("OWUI_CHUNKS", "/app/build/_app/immutable/chunks"))
MARKER = "/*localllm-call-trace*/"
HEADER = (
    MARKER
    + 'let __llw="";const __ll=m=>{try{fetch("/api/version?ll="+encodeURIComponent(m)+"&t="+Date.now(),'
    + '{keepalive:!0,cache:"no-store"}).catch(()=>{})}catch(e){}};\n'
)

EDITS = [
    # he(): #audioElement playback of one chunk
    (
        'Ne.onended=ye,Ne.onerror=()=>ye(),Ne.onpause=ye,Ne.play().then(()=>{Ne.muted=!1}).catch(It=>{ye(It)})',
        '__ll("play:start"),Ne.onended=()=>{__ll("play:ended:"+Ne.currentTime.toFixed(1)+"/"+(Ne.duration||0).toFixed(1)),ye()},'
        'Ne.onerror=()=>{__ll("play:error:"+(Ne.error&&Ne.error.code)),ye()},'
        'Ne.onpause=()=>{__ll("play:pause:"+Ne.currentTime.toFixed(1)+"/"+(Ne.duration||0).toFixed(1)),ye()},'
        'Ne.play().then(()=>{Ne.muted=!1,__ll("play:playing")}).catch(It=>{__ll("play:reject:"+(It&&It.name)),ye(It)})',
        1,
    ),
    # De(): interrupt, with caller tag
    ('De=async()=>{c(K,!1),', 'De=async(__w)=>{__ll("interrupt:"+(__w||"?")+":K="+r(K)),c(K,!1),', 1),
    ('$||($=!0,De())', '$||($=!0,De("vad"))', 1),
    ('le("click",Wt,()=>{r(K)&&De()})', 'le("click",Wt,()=>{r(K)&&De("tap")})', 2),
    # overlay event handlers
    ('Je=async ue=>{const{id:me}=ue.detail;B=!0,', 'Je=async ue=>{const{id:me}=ue.detail;__ll("start:"+String(me).slice(0,8)+":same="+(te===me)),B=!0,', 1),
    ('tt=async ue=>{const{id:me,content:Ne}=ue.detail;if(te===me){', 'tt=async ue=>{const{id:me,content:Ne}=ue.detail;__ll("chunk:"+(te===me)+":"+Ne.length);if(te===me){', 1),
    ('Xe=async ue=>{const{id:me,content:Ne}=ue.detail;ce[me]=!0,B=!1}', 'Xe=async ue=>{const{id:me,content:Ne}=ue.detail;__ll("finish:"+Ne.length),ce[me]=!0,B=!1}', 1),
    # et(): the sequential playback loop
    ('else Ge[ue].unshift(Ye),`${Ye}`,await new Promise(ye=>setTimeout(ye,200))', 'else Ge[ue].unshift(Ye),__llw!==Ye&&(__llw=Ye,__ll("loop:wait:"+Ye.length)),await new Promise(ye=>setTimeout(ye,200))', 1),
    ('else if(ce[ue]&&Ge[ue]&&Ge[ue].length===0){c(K,!1);break}else await new Promise(Ye=>setTimeout(Ye,200));`${ue}`}', 'else if(ce[ue]&&Ge[ue]&&Ge[ue].length===0){__ll("loop:done"),c(K,!1);break}else await new Promise(Ye=>setTimeout(Ye,200));__ll("loop:exit:aborted="+me.aborted)}', 1),
    # recording / STT / submit
    ('x.onstop=ue=>{r(S),ge()}', 'x.onstop=ue=>{__ll("rec:stop"),r(S),ge()}', 1),
    ('if(Ne&&(Ne.text,Ne.text!=="")){const Ct=await y()(Ne.text,{_raw:!0})}', 'if(Ne&&(Ne.text,Ne.text!=="")){__ll("stt:"+Ne.text.length);const Ct=await y()(Ne.text,{_raw:!0});__ll("submitted")}', 1),
]

done = 0
for path in CHUNKS.glob("*.js"):
    text = path.read_text()
    if MARKER in text:
        print(f"{path.name}: already patched"); done += 1; continue
    if "ttsSentContentPartCount" not in text or "audioElement" not in text:
        continue
    new = text
    for old, rep, count in EDITS:
        if new.count(old) != count:
            sys.exit(f"{path.name}: expected {count} of {old[:60]!r}, found {new.count(old)}; not patched")
        new = new.replace(old, rep)
    path.write_text(HEADER + new)
    print(f"{path.name}: patched"); done += 1
if done != 1:
    sys.exit(f"expected exactly one call-overlay chunk, found {done}")
print("call trace patch in place")
