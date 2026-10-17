import ast
from pathlib import Path
import re
import subprocess
import sys
import unittest

PATCH = Path(__file__).resolve().parents[1] / 'webui/patches/patch_openwebui_call_audio.py'


class PrerollTests(unittest.TestCase):
    def test_recording_graph_is_bounded_reused_and_released(self):
        tree = ast.parse(PATCH.read_text())
        nodes = [n for n in tree.body if
                 isinstance(n, ast.FunctionDef) and n.name == 'recorder_preroll' or
                 isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('AC_MARKER', 'CLOSE_AC') for t in n.targets)]
        ns = {'re': re, 'sys': sys}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PATCH), 'exec'), ns)
        source = '''/*localllm-call-ac*/
function record(){return new MediaRecorder(r(S));}
function close(){CLOSE}
'''.replace('CLOSE', ns['CLOSE_AC'])
        patched = ns['recorder_preroll'](source)
        self.assertEqual(ns['recorder_preroll'](patched), patched)
        harness = '''
const assert=require('node:assert/strict');global.window={};
let contexts=0,sources=0,closed=0,stopped=0,disconnected=0;
class AudioContext {
 constructor(){contexts++;this.state='running';}
 createMediaStreamSource(s){sources++;return {connect(){},disconnect(){disconnected++;}};}
 createDelay(max){assert.equal(max,1);return {delayTime:{value:0},connect(){},disconnect(){disconnected++;}};}
 createMediaStreamDestination(){return {stream:{getTracks(){return [{stop(){stopped++;}}];}}};}
 close(){closed++;this.state='closed';return Promise.resolve();}
}
class MediaRecorder{constructor(s){this.stream=s;}}
let S={};const r=x=>x;
'''
        assertions = '''
const first=record();
assert.notEqual(first.stream,S,'recorder must use buffered microphone');
assert.equal(window.__llRecordDelay.delayTime.value,.35);
for(let i=0;i<20;i++)assert.equal(record().stream,first.stream);
assert.equal(contexts,1);assert.equal(sources,1);
S={};assert.notEqual(record().stream,first.stream);
assert.equal(stopped,1);assert.equal(disconnected,2);
close();assert.equal(stopped,2);assert.equal(disconnected,4);assert.equal(closed,1);
assert.equal(window.__llRecordDest,null);assert.equal(window.__llAC,null);
record();assert.equal(contexts,2);close();assert.equal(stopped,3);
'''
        result = subprocess.run(['node', '-e', harness + patched + assertions], text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
