"""Run with stdin in the built image, --network none and a disposable DATA_DIR."""
import asyncio,json,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
Path(os.environ['DATA_DIR']).mkdir(parents=True,exist_ok=True)
from open_webui.utils import tools
from open_webui.utils.middleware import process_tool_result
from open_webui.tools import buddy_openui

async def main():
 req=SimpleNamespace(state=SimpleNamespace(internal=False,direct=False),headers={'origin':'https://buddy.test:3000'},base_url='http://localhost:8080')
 async def config_many(*args,**kw):return {}
 async def config_get(*args,**kw):return {}
 with patch.object(tools.Config,'get_many',side_effect=config_many),patch.object(tools.Config,'get',side_effect=config_get):
  registry=await tools.get_builtin_tools(req,{'__user__':{'role':'admin','id':'test'}},model={})
  assert 'render_openui' in registry and 'get_openui_reference' in registry,registry.keys()
  spec=registry['render_openui']['spec'];assert '__request__' not in spec['parameters']['properties']
  assert set(spec['parameters']['properties'])=={'code','title'},spec
  response=await registry['render_openui']['callable'](code='root = Col([Text("hello")])')
  processed=await process_tool_result(req,'render_openui',response,'builtin')
  assert any('<!doctype html>' in str(item) for item in processed),str(processed)[:300]
  disabled=await tools.get_builtin_tools(req,{'__user__':{'role':'admin','id':'test'}},model={'info':{'meta':{'builtinTools':{'openui':False}}}})
  assert 'render_openui' not in disabled
  reference=await registry['get_openui_reference']['callable'](names='Input,Svg,Map')
  assert 'Svg(' in reference and 'Input(' in reference and 'Map(' not in reference
 assert '/static/buddy-openui/host.js' in Path('/app/build/index.html').read_text()
 assert 'window.buddyPrepare(Me)' in Path('/app/build/_app/immutable/chunks/D1XkYf1e.js').read_text()
 assert 'window.buddyPrepare(se)' in Path('/app/build/_app/immutable/chunks/BjRGu3Y4.js').read_text()
 assert 'window.buddyPrepare(J)' in Path('/app/build/_app/immutable/chunks/s2ZoGhDo.js').read_text()
 assert 'window.buddyPrepare(T)' in Path('/app/build/_app/immutable/chunks/CjrAIo5u.js').read_text()
 assert (buddy_openui.ASSETS/'host.js').is_file()
 assert 'No image search or automatic fallback.' in (buddy_openui.ASSETS/'reference.txt').read_text()
 assert (buddy_openui.ASSETS/'LICENSE-open-intelligent-ui.txt').read_text().startswith('The MIT License')
 print(json.dumps({'builtin_registered':True,'reserved_args_hidden':True,'inline_middleware':True,'model_opt_out':True,'reference':True,'license':True,'schema_characters':len(json.dumps(spec))}))
asyncio.run(main())
