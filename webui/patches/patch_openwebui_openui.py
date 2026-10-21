"""Register Buddy's local UI renderer as two small built-in tools; rerunnable."""
from pathlib import Path

PATH = Path('/app/backend/open_webui/utils/tools.py')
MARKER = '# buddy: local OpenUI tools'
ANCHOR = "    # Time utilities - available for date calculations\n"
BLOCK = '''    # buddy: local OpenUI tools
    # not in voice calls: a drawn answer cannot be spoken, and its description costs every turn
    if is_builtin_tool_enabled('openui') and get_model_capability('builtin_tools') and not (features or {}).get('voice'):
        from open_webui.tools.buddy_openui import render_openui, get_openui_reference
        builtin_functions.extend([render_openui, get_openui_reference])

'''


def patched_source(text):
    if MARKER in text:
        return text
    if text.count(ANCHOR) != 1:
        raise ValueError('unexpected get_builtin_tools layout; OpenUI not installed')
    result = text.replace(ANCHOR, BLOCK + ANCHOR, 1)
    compile(result, str(PATH), 'exec')
    return result


if __name__ == '__main__':
    source = PATH.read_text()
    result = patched_source(source)
    if result != source:
        PATH.write_text(result)
    print('Buddy OpenUI tools installed')

    index = Path('/app/build/index.html')
    page = index.read_text()
    tag = '<script src="/static/buddy-openui/host.js"></script>'
    if tag not in page:
        if page.count('</head>') != 1:
            raise ValueError('unexpected frontend index layout')
        index.write_text(page.replace('</head>', tag + '</head>'))

    # Prepare srcdoc synchronously, before browser navigation; no observer race.
    bindings = {
        's2ZoGhDo.js': ('Ae(M,"srcdoc",J)', 'Ae(M,"srcdoc",window.buddyPrepare(J))'),
        'CjrAIo5u.js': ('le(E,"srcdoc",T)', 'le(E,"srcdoc",window.buddyPrepare(T))'),
        'D1XkYf1e.js': ('Le(de,"srcdoc",Me)', 'Le(de,"srcdoc",window.buddyPrepare(Me))'),
        'BjRGu3Y4.js': ('Le(ee,"srcdoc",se)', 'Le(ee,"srcdoc",window.buddyPrepare(se))'),
    }
    for name, (old, replacement) in bindings.items():
        chunk = Path('/app/build/_app/immutable/chunks') / name
        frontend = chunk.read_text()
        new = replacement + '/*localllm-buddy-srcdoc*/'
        if new not in frontend:
            if frontend.count(old) != 1:
                raise ValueError(f'unexpected OWUI iframe binding: {name}')
            chunk.write_text(frontend.replace(old, new))
