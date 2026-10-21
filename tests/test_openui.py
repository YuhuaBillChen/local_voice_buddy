import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = load('buddy_openui', ROOT/'webui/openui/buddy_openui.py')
        cls.installer = load('buddy_openui_patch', ROOT/'webui/patches/patch_openwebui_openui.py')

    def test_inline_result_and_browser_origin_preserve_https_port(self):
        req = SimpleNamespace(headers={'origin':'https://buddy.example:3000'},base_url='http://internal:8080')
        response, context = asyncio.run(self.ui.render_openui('root = Col([Text("hello")])', __request__=req))
        self.assertEqual(response.headers['content-disposition'], 'inline')
        self.assertNotIn('https://buddy.example:3000', response.body.decode())
        self.assertIn('<template data-buddy-template>', response.body.decode())
        self.assertIn('https://buddy.invalid/static/buddy-openui/', response.body.decode())
        self.assertEqual(context['status'], 'rendered')

    def test_code_and_title_cannot_escape_html_or_json(self):
        result = self.ui.build_html('root = Col([Text("</script><script>bad</script>")])','<img onerror=x>','https://buddy.test')
        self.assertNotIn('<script>bad', result)
        self.assertIn('\\u003c/script', result)
        self.assertIn('&lt;img onerror=x&gt;', result)
        self.assertIn("connect-src &#x27;none&#x27;", result)
        config = result.split('id="buddy-config">')[1].split('</script>')[0]
        self.assertIn('</script>',json.loads(config)['code'])

    def test_saved_answer_is_independent_of_generation_origin(self):
        code = 'root = Col([Text("https://buddy.invalid/user-text")])'
        first = self.ui.build_html(code, 'title', 'https://old.example:3000')
        second = self.ui.build_html(code, 'title', 'https://new.example:4000')
        self.assertEqual(first, second)
        self.assertIn('https://buddy.invalid/user-text', first)

    def test_invalid_program_is_rejected_without_request(self):
        for code in ('<script>bad</script>', 'root = Row([])', 'root = Col([])'+(' '*100001)):
            self.assertIsInstance(asyncio.run(self.ui.render_openui(code)), str)

    def test_reference_only_returns_requested_supported_components(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'reference.txt').write_text('Input(value: string)\nMap(markers: Node[])\n@Round(value: number)\n')
            with patch.object(self.ui, 'ASSETS', Path(d)), patch.dict('os.environ',{'OPENUI_NETWORK':'false'}):
                ref=asyncio.run(self.ui.get_openui_reference('Input,Map'))
                self.assertIn('Input(value:', ref)
                self.assertNotIn('Map(markers:', ref)
                self.assertNotIn('@Round', ref)
            with patch.object(self.ui, 'ASSETS', Path(d)), patch.dict('os.environ',{'OPENUI_NETWORK':'true'}):
                self.assertIn('Map(markers:', asyncio.run(self.ui.get_openui_reference('Map')))

    def test_registry_is_idempotent_and_respects_model_disable(self):
        source='''async def get_builtin_tools(enabled, capable, features=None):
    def is_builtin_tool_enabled(category): return enabled
    def get_model_capability(category): return capable
    builtin_functions=[]
    # Time utilities - available for date calculations
    return builtin_functions
'''
        patched=self.installer.patched_source(source)
        self.assertEqual(self.installer.patched_source(patched),patched)
        # Inspect the condition rather than import Open WebUI in unit tests.
        block=next(n for n in ast.walk(ast.parse(patched)) if isinstance(n,ast.If))
        expression=compile(ast.Expression(block.test),'gate','eval')
        for enabled, capable, voice in ((False,True,False),(True,False,False),(True,True,False),(True,True,True)):
            self.assertEqual(eval(expression,{'is_builtin_tool_enabled':lambda _:enabled,'get_model_capability':lambda _:capable,'features':{'voice':voice}}), enabled and capable and not voice)
        with self.assertRaises(ValueError):self.installer.patched_source('changed upstream')

    def test_image_includes_assets_adapter_and_license_not_plugin(self):
        docker=(ROOT/'webui/Dockerfile').read_text()
        self.assertIn('03213439358bf3408ad61a46ec9e3230c5572e48',docker)
        self.assertIn('COPY --from=openui /out',docker)
        self.assertIn('builtin_tools openui frontend_release',docker)
        build=(ROOT/'webui/openui/build.mjs').read_text()
        self.assertIn('THIRD_PARTY_NOTICES.txt',build)
        self.assertNotIn('openwebui-plugin',docker)

if __name__=='__main__':unittest.main()
