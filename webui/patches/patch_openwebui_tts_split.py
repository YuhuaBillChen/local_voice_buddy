"""Make OWUI's read-aloud split Chinese into short chunks; safe to rerun after OWUI recreation.

Stock OWUI splits only after `.!?` + whitespace, and merges a chunk into the
next while it has < 4 whitespace-separated words or < 50 chars. Chinese has no
spaces after 。！？ and always counts as one "word", so a whole CJK reply went
to TTS as one request and the first audio waited for all of it.

For CJK this splits at 。！？；， as well, and merges only while a chunk is
shorter than a threshold that grows 4, 8, 14, then 20 characters. CosyVoice
synthesises at ~0.8x real time and one request at a time, so a short first
chunk makes the first audio early, and each next chunk only has to be ready
before the previous one finishes playing; a flat 6-then-20 rule left ~1.7 s of
silence after the first chunk. English keeps the stock rule.

Chunks 2 and 3 are also capped at 20 and 24 characters: the clause after a
short first chunk can run long without punctuation, and with the 27B
generating on the same box it was not ready before chunk 1 finished. An
over-long chunk is cut at its last punctuation within the cap, else after
的/了/着/过, else before a preposition, else at the cap; the rest starts the
next chunk. (12/16 cut too eagerly and sounded choppy, 2026-10-06.)

That cut split words: "before a preposition" (在/到/对/和...) and "at the cap"
cut 提|到, 具|体, 同一|个 in real replies (2026-10-10), which CosyVoice then
pronounced oddly. Without punctuation inside the cap an over-long chunk is now
cut at the last word boundary from the browser's Chinese word segmenter
(Intl.Segmenter), and left whole if there is none.

Qwen often writes half-width ,;!? inside Chinese text, which the full-width
rule missed, so a CJK character followed by one of those is a split point too.

English used the stock rule (cut only after .!?, merge to >= 4 words and >= 50
characters), so a long first sentence became a 110-135 character first chunk
and the first audio came 6-13 s after the first token (2026-10-06). English
now also splits after , ; : and merges progressively: >= 3 words and 15, then
40, then 50 characters.
"""
from pathlib import Path
import sys

CHUNKS = Path("/app/build/_app/immutable/chunks")
SPLIT_STOCK = '"(?<=[.!?])\\\\s+|\\\\n+"'
SPLIT_V1 = '"(?<=[.!?])\\\\s+|(?<=[。！？；])\\\\s*|\\\\n+"'
SPLIT_V2 = '"(?<=[.!?])\\\\s+|(?<=[。！？；，])\\\\s*|\\\\n+"'
SPLIT_V3 = '"(?<=[.!?])\\\\s+|(?<=[。！？；，])\\\\s*|(?<=[\\u3400-\\u9fff][,;!?])\\\\s*|\\\\n+"'
SPLIT_NEW = '"(?<=[.!?])\\\\s+|(?<=[。！？；，])\\\\s*|(?<=[\\u3400-\\u9fff][,;!?])\\\\s*|(?<=[A-Za-z0-9][,;:])\\\\s+|\\\\n+"'
MERGE_STOCK = "i<4||a<50?"
MERGE_V1 = "(/[\\u3400-\\u9fff]/.test(s)?a<12:i<4||a<50)?"
MERGE_V2 = "(/[\\u3400-\\u9fff]/.test(s)?a<(r?20:6):i<4||a<50)?"
MERGE_V3 = "(/[\\u3400-\\u9fff]/.test(s)?a<([4,8,14][r]??20):i<4||a<50)?"
MERGE_NEW = "(/[\\u3400-\\u9fff]/.test(s)?a<([4,8,14][r]??20):i<3||a<([15,40][r]??50))?"
REDUCE_END = 'e[r]=s+" "+t:e.push(t)}else e.push(t);return e},[])'
CAP_V1 = (
    'e[r]=s+" "+t:e.push(t)}else e.push(t);'
    "for(let k=e.length-1,c;(c=[0,12,16][k])&&/[\\u3400-\\u9fff]/.test(e[k])&&e[k].length>c;k++){"
    "const s=e[k];let q=0;"
    'for(const f of[j=>/[。！？；，、]/.test(s[j-1]),j=>"的了着过".includes(s[j-1]),j=>"在和把去到给让被跟从向对".includes(s[j])]){'
    "for(let j=c;j>3&&!q;j--)f(j)&&(q=j);if(q)break}"
    "q=q||c;e[k]=s.slice(0,q).trim();e.push(s.slice(q).trim())}"
    "return e},[])"
)
CAP_V2 = (
    'e[r]=s+" "+t:e.push(t)}else e.push(t);'
    "for(let k=e.length-1,c;(c=[0,20,24][k])&&/[\\u3400-\\u9fff]/.test(e[k])&&e[k].length>c;k++){"
    "const s=e[k];let q=0;"
    'for(const f of[j=>/[。！？；，、,;:!?]/.test(s[j-1]),j=>"的了着过".includes(s[j-1]),j=>"在和把去到给让被跟从向对".includes(s[j])]){'
    "for(let j=c;j>3&&!q;j--)f(j)&&(q=j);if(q)break}"
    "q=q||c;e[k]=s.slice(0,q).trim();e.push(s.slice(q).trim())}"
    "return e},[])"
)

CAP_V3 = (
    'e[r]=s+" "+t:e.push(t)}else e.push(t);'
    "for(let k=e.length-1,c;(c=[0,20,24][k])&&/[\\u3400-\\u9fff]/.test(e[k])&&e[k].length>c;k++){"
    "const s=e[k];let q=0;"
    "for(let j=c;j>3&&!q;j--)/[。！？；，、,;:!?]/.test(s[j-1])&&(q=j);"
    'if(!q&&typeof Intl<"u"&&Intl.Segmenter)for(const w of new Intl.Segmenter("zh",{granularity:"word"}).segment(s)){if(w.index>c)break;w.index>3&&(q=w.index)}'
    "if(!q)break;e[k]=s.slice(0,q).trim();e.push(s.slice(q).trim())}"
    "return e},[])"
)

# the marker lets patch_openwebui_frontend_release.py see this chunk change and bump the version
CAP = CAP_V3.replace("e.push(t);for(", "e.push(t);/*localllm-tts-split*/for(", 1)

patched = 0
for path in CHUNKS.glob("*.js"):
    text = path.read_text()
    split_old = next((p for p in (SPLIT_STOCK, SPLIT_V1, SPLIT_V2, SPLIT_V3) if p in text), None)
    if split_old is None and SPLIT_NEW not in text:
        continue
    patched += 1
    original = text
    if split_old:
        if text.count(split_old) != 1:
            sys.exit(f"{path.name}: unexpected OWUI build, TTS split patch not applied")
        text = text.replace(split_old, SPLIT_NEW)
    if MERGE_NEW not in text:
        merge_old = next((p for p in (MERGE_STOCK, MERGE_V1, MERGE_V2, MERGE_V3) if p in text), None)
        if merge_old is None or text.count(merge_old) != 1:
            sys.exit(f"{path.name}: unexpected OWUI build, TTS split patch not applied")
        text = text.replace(merge_old, MERGE_NEW)
    if CAP not in text:
        old_cap = next((c for c in (CAP_V3, CAP_V2, CAP_V1) if text.count(MERGE_NEW + c) == 1), None)
        if old_cap:
            text = text.replace(MERGE_NEW + old_cap, MERGE_NEW + CAP)
        elif text.count(MERGE_NEW + REDUCE_END) == 1:
            text = text.replace(MERGE_NEW + REDUCE_END, MERGE_NEW + CAP)
        else:
            sys.exit(f"{path.name}: unexpected OWUI build, TTS chunk caps not applied")
    if text == original:
        print(f"{path.name}: already patched")
    else:
        path.write_text(text)
        print(f"{path.name}: patched")

if patched != 1:
    sys.exit(f"expected exactly one chunk with the TTS splitter, found {patched}")
