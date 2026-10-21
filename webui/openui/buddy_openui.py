"""Buddy-owned Open WebUI adapter; no code from the OpenWebUI OpenUI plugin."""
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from starlette.responses import HTMLResponse

ASSETS = Path('/app/backend/open_webui/static/buddy-openui')


def network_enabled():
    return os.environ.get('OPENUI_NETWORK', 'false').lower() == 'true'


def origin_for(request):
    # Browser origin makes embeds work through HTTPS reverse proxies and ports.
    raw = request.headers.get('origin') if request else None
    raw = raw or (str(request.base_url) if request else '')
    parsed = urlsplit(raw)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password
            or re.search(r'''[\s;'"<>]''', parsed.netloc)):
        raise ValueError('A valid application origin is required')
    return f'{parsed.scheme}://{parsed.netloc}'


def build_html(code, title, origin, network=False):
    origin = 'https://buddy.invalid'  # Rebound by the host before this inert template runs.
    config = json.dumps({'code': code, 'origin': origin, 'network': network}, ensure_ascii=False)
    config = config.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    safe = html.escape(origin, quote=True)
    policy = (f"default-src 'none'; script-src {origin}; style-src {origin} 'unsafe-inline'; "
              f"font-src {origin} data:; img-src {origin} data: blob:" + (' https:' if network else '') + '; '
              + ("connect-src https://tiles.openfreemap.org https://server.arcgisonline.com https://router.project-osrm.org; " if network else "connect-src 'none'; ")
              + "worker-src blob: " + origin + "; frame-src 'none'; base-uri 'none'; form-action 'none'")
    return f'''<!doctype html><template data-buddy-template><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">
<title>{html.escape(title)}</title><link rel="stylesheet" href="{safe}/static/buddy-openui/buddy-openui.css">
<style>*{{box-sizing:border-box}}html,body{{margin:0;background:transparent}}body{{overflow-wrap:anywhere}}#buddy-root,.iui-col>*,.iui-card{{min-width:0}}input,textarea,select{{max-width:100%}}</style>
</head><body><div id="buddy-root"></div><script type="application/json" id="buddy-config">{config}</script>
<script data-buddy-openui src="{safe}/static/buddy-openui/buddy-openui.js"></script></body></template>'''


async def get_openui_reference(names: str = '') -> str:
    """Look up exact OpenUI positional arguments before drawing an unfamiliar component.

    :param names: Comma-separated component or @function names, e.g. Input,Form,Svg,Map. Empty lists available names.
    :return: Matching signatures and syntax rules; external maps/images require OPENUI_NETWORK=true.
    """
    lines = (ASSETS / 'reference.txt').read_text().splitlines()
    lines = [line.removeprefix('- ') for line in lines]
    signatures = [line for line in lines if re.match(r'^@?[A-Z]\w*\(', line)]
    if not network_enabled():
        signatures = [line for line in signatures if not re.match(r'^(Map|MapMarker|Image)\(', line)]
    requested = {name.strip().lstrip('@') for name in names.split(',') if name.strip()}
    selected = [line for line in signatures if line.split('(')[0].lstrip('@') in requested] if requested else [line.split('(')[0] for line in signatures]
    return ('One statement per line; root = Col([...]); positional arguments; declare $state = value; '
            'use @ToAssistant("message") on submit buttons; form values travel with it.\n' + '\n'.join(selected[:40] if requested else selected))


async def render_openui(code: str, title: str = 'Buddy', __request__=None):
    """Show interactive cards, tables, charts, forms or SVG drawings when useful or requested.
    Normal chat and voice answers remain plain text. First line: root = Col([...]).
    Use positional calls, double-quoted strings and one statement per line.
    Basic components: Title(text,size?), Text(text), Card(children[]), Col(children[]),
    Grid(children[],columns?,minWidth?,gap?), Table(columns[],rows[][]),
    Chart(type,data,x,series: string[]), Button(label,@ToAssistant("message")), Form(children[]).
    Chart data is a list of rows: Chart("pie", [{"item":"A","n":3},{"item":"B","n":5}], "item", ["n"]).
    For controls, SVG or other arguments, call get_openui_reference with component names.
    Declare every state variable with an initial value on its own line after root, e.g. $amount = 10.
    Then use Input($amount,"Amount","number") and Text("Total: " + $amount).
    Use real data and quote all object keys. Do not repeat the rendered answer as text.

    :param code: Complete OpenUI Lang program, beginning with root = Col([...]).
    :param title: Short title in the user's language.
    :return: An interactive inline answer. No files or services are changed by rendering.
    """
    if not isinstance(code, str) or len(code) > 100000 or not re.match(r'^\s*root\s*=\s*Col\s*\(', code):
        return 'Not rendered: use root = Col([...]) on the first line; maximum 100000 characters.'
    response = HTMLResponse(build_html(code, str(title)[:200], origin_for(__request__), network_enabled()),
                            headers={'Content-Disposition': 'inline'})
    return response, {'status': 'rendered', 'message': 'Visible interactive answer. Do not repeat it. Continue only if the user asks.'}
