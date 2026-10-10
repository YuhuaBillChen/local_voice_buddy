"""Make phones pick up patched OWUI bundles; safe to rerun.

Patched chunks keep their file names, and OWUI serves /_app/immutable/* with
no Cache-Control, so browsers apply heuristic freshness (10% of the file's
age) and an installed PWA can run a stale copy for hours after a patch
(2026-09-30: a phone kept the pre-patch call overlay for 40 minutes). Force
revalidation (ETag, so a 304 when unchanged) and bump _app/version.json so an
open SvelteKit app notices the release and reloads on its next navigation.
"""
from pathlib import Path
import hashlib
import re
import sys

MAIN = Path("/app/backend/open_webui/main.py")
BUILD = Path("/app/build/_app")
MARKER = "localllm: patched bundles keep their file names"
OLD = """        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                if path.endswith('.js'):"""
NEW = f"""        try:
            response = await super().get_response(path, scope)
            if path.startswith('_app/immutable/'):
                # {MARKER}; revalidate on every load so patches reach installed PWAs
                response.headers['Cache-Control'] = 'no-cache'
            return response
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                if path.endswith('.js'):"""

text = MAIN.read_text()
if MARKER in text:
    print("cache header patch already applied")
else:
    if text.count(OLD) != 1:
        sys.exit("unexpected SPAStaticFiles.get_response; not patched")
    new = text.replace(OLD, NEW)
    compile(new, str(MAIN), "exec")
    MAIN.write_text(new)
    print("cache header patch applied; restart open-webui")

digest = hashlib.sha1()
for path in sorted((BUILD / "immutable").rglob("*.js")):
    body = path.read_bytes()
    if b"/*localllm-" in body:
        digest.update(path.name.encode() + body)
version = "localllm-" + digest.hexdigest()[:12]

# SvelteKit compares the version baked into its client runtime with
# version.json; the two must always move together or every navigation
# would trigger a full reload.
BAKED = re.compile(r'([\w$]+)="(?:[0-9a-f]{40}|localllm-[0-9a-f]{12})"(,[\w$]+="sveltekit:snapshot")')
runtimes = [
    path for path in (BUILD / "immutable" / "chunks").glob("*.js")
    if 'sveltekit:snapshot' in path.read_text() and BAKED.search(path.read_text())
]
if len(runtimes) != 1:
    sys.exit(f"expected one SvelteKit client runtime with a baked version, found {len(runtimes)}; version not bumped")
runtime = runtimes[0]
source = runtime.read_text()
if len(BAKED.findall(source)) != 1:
    sys.exit(f"{runtime.name}: ambiguous baked version; version not bumped")
bumped = BAKED.sub(lambda m: f'{m.group(1)}="{version}"{m.group(2)}', source)
if bumped != source:
    runtime.write_text(bumped)
target = BUILD / "version.json"
wanted = '{"version":"%s"}' % version
if not target.exists() or target.read_text() != wanted:
    target.write_text(wanted)
print(f"release version {version} ({runtime.name} + version.json)")
