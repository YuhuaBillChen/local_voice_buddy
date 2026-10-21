# Interactive answers

In a typed chat the model can answer with cards, tables, charts, editable forms and SVG drawings
instead of plain text. It decides by itself when that helps; you can also ask ("compare these in a
table", "make a budget calculator"). Controls recalculate inside the answer, and a form's submit
button sends its values back to the chat. Voice calls do not get this tool: a drawn answer cannot be
spoken.

**How it works.** `webui/Dockerfile` builds the MIT-licensed
[Open Intelligent UI](https://github.com/thesysdev/open-intelligent-ui) component library at a pinned
commit (`03213439358bf3408ad61a46ec9e3230c5572e48`) and copies only the browser files, its license
and the dependency notices into the web UI image. Two built-in tools are ours (`webui/openui/`):
`render_openui` shows the answer, `get_openui_reference` gives the model the exact arguments of a
component when it needs one. The answer runs in Open WebUI's sandboxed frame with no access to the
page or your data, and asks nothing from the network.

**Speed.** On the reference mini PC a pie chart from five numbers (the website recording) takes
40-65 s from sending the question to the finished drawing; a comparison table with a written
recommendation took about 1.5 minutes. The two tool descriptions add about 200 tokens to the start of every typed chat (921 instead of 698).

**Settings.** On by default (`BUILTIN_TOOLS=time,openui`). Remove `openui` to turn it off; a model's
own Builtin Tools settings in Admin Settings > Models take precedence. Maps and remote images are off
by default; `OPENUI_NETWORK=true` allows them (map tiles from OpenFreeMap/Esri and routes from
OSRM, which then see the requested places; images load from their HTTPS address). Image search,
YouTube and arbitrary HTML are not included.

The license, dependency notices and pinned revision are served from
`/static/buddy-openui/LICENSE-open-intelligent-ui.txt`, `THIRD_PARTY_NOTICES.txt` and `upstream.json`.
The separate `thesysdev/openwebui-plugin` is not used.
