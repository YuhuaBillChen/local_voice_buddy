"""Offer the model only the built-in tools in BUILTIN_TOOLS (default: time); safe to rerun.

With native function calling, Open WebUI (v0.11.4) attaches every built-in tool category a model
does not explicitly turn off: knowledge bases, chat history, notes, tasks, ask-user, time and more.
Their descriptions made the first prompt of every new chat 6.6K tokens, which takes 85 s to read on
the iGPU before the first word of the reply (2026-10-10). A model's own "Builtin Tools" settings
(Admin Settings > Models) still take precedence; this only changes the default for categories it
does not mention. BUILTIN_TOOLS is a comma-separated list of categories, e.g. "time,memory,web_search".
"""
from pathlib import Path
import sys

PATH = Path("/app/backend/open_webui/utils/tools.py")
MARKER = "localllm: built-in tool categories default to BUILTIN_TOOLS"
OLD = """    def is_builtin_tool_enabled(category: str, default: bool = True) -> bool:
        builtin_tools = model.get('info', {}).get('meta', {}).get('builtinTools', {})
        return builtin_tools.get(category, default)
"""
NEW = f"""    def is_builtin_tool_enabled(category: str, default: bool = True) -> bool:
        # {MARKER}
        builtin_tools = model.get('info', {{}}).get('meta', {{}}).get('builtinTools', {{}})
        enabled = os.environ.get('BUILTIN_TOOLS', 'time').replace(' ', '').split(',')
        return builtin_tools.get(category, category in enabled)
"""

text = PATH.read_text()
if MARKER in text:
    print("builtin tools patch already applied")
    sys.exit(0)
if text.count(OLD) != 1:
    sys.exit("unexpected get_builtin_tools; not patched")
new = text.replace(OLD, NEW)
if "\nimport os\n" not in new:
    new = "import os\n" + new
compile(new, str(PATH), "exec")
PATH.write_text(new)
print("builtin tools patch applied; restart open-webui")
