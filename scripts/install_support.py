"""Edit only the two GPU-memory boot parameters; never execute a GRUB config."""
import argparse
from pathlib import Path
import re
import sys

LINE = re.compile(r'^(GRUB_CMDLINE_LINUX_DEFAULT=)([\"\'])([^\n]*?)\2([ \t]*(?:#.*)?)$', re.M)
PARAM = re.compile(r'(?<!\S)(?:amdgpu\.gttsize|ttm\.pages_limit)=\S+')
EXPECTED = ['amdgpu.gttsize=24576', 'ttm.pages_limit=6291456']

def grub_ready(text):
    matches = list(LINE.finditer(text))
    if len(matches) != 1:
        return False
    return sorted(PARAM.findall(matches[0][3])) == sorted(EXPECTED)

def render_grub(text):
    matches = list(LINE.finditer(text))
    if len(matches) != 1:
        raise ValueError('Expected one quoted GRUB_CMDLINE_LINUX_DEFAULT line; edit the boot parameters manually.')
    if grub_ready(text):
        return text
    m = matches[0]
    remaining = PARAM.sub('', m[3]).strip()
    new = m[1] + m[2] + ' '.join(EXPECTED) + (' ' + remaining if remaining else '') + m[2] + m[4]
    return text[:m.start()] + new + text[m.end():]

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['grub-ready','grub-render'])
    p.add_argument('file', type=Path)
    args = p.parse_args()
    try:
        text = args.file.read_text()
        if args.command == 'grub-ready':
            sys.exit(0 if grub_ready(text) else 1)
        print(render_grub(text), end='')
    except (OSError, ValueError) as e:
        sys.exit(str(e))
