"""Behavioral checks for the voice patches on the v0.12 compiler shapes."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

PATCHES = Path(__file__).resolve().parents[1] / 'webui' / 'patches'


def run_js(source):
    result = subprocess.run(['node', '-e', source], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout


def definitions(name, functions=(), variables=()):
    path = PATCHES / f'patch_openwebui_{name}.py'
    nodes = [node for node in ast.parse(path.read_text()).body if
             isinstance(node, ast.FunctionDef) and node.name in functions or
             isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in variables for t in node.targets)]
    ns = {'re': re, 'sys': sys}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    return ns


class VoiceV012Tests(unittest.TestCase):
    def test_new_splitter_streams_chinese_and_english_without_losing_text(self):
        # Exact reducer shape from stock v0.12.0; index/content names were swapped.
        source = r'''const Iu=n=>n.split(new RegExp("(?<=[.!?])\\s+|\\n+")).map(s=>s.trim()).filter(Boolean),Lu=n=>Iu(n).reduce((e,t)=>{const s=e.length-1;if(s>=0){const r=e[s],i=r.split(/\s+/).length,a=r.length;i<4||a<50?e[s]=r+" "+t:e.push(t)}else e.push(t);return e},[]);'''
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'split.js'
            path.write_text(source)
            env = dict(os.environ, OWUI_CHUNKS=d)
            for _ in range(2):
                subprocess.run([sys.executable, str(PATCHES / 'patch_openwebui_tts_split.py')], env=env, check=True, capture_output=True)
                patched = path.read_text()
                if _ == 0:
                    first = patched
                else:
                    self.assertEqual(first, patched)
            script = patched + r'''const a=require('node:assert/strict');
for(const text of ['你好朋友。今天我们一起看看新的语音功能，能够边生成边朗读。','Hello my friend, today we can hear the first phrase before the whole answer finishes.']){
 const chunks=Lu(text);a.ok(chunks.length>1);a.ok(chunks[0].length<30);
 a.equal(chunks.join('').replace(/\s/g,''),text.replace(/\s/g,''));
}'''
            run_js(script)

    def test_preroll_reuses_buffer_and_releases_tracks_for_both_builds(self):
        ns = definitions('call_audio', ('recorder_preroll',), ('AC_MARKER', 'CLOSE_AC'))
        for stream in ('r(S)', 'S'):
            source = f'/*localllm-call-ac*/function record(){{return new MediaRecorder({stream});}}function close(){{{ns["CLOSE_AC"]}}}'
            patched = ns['recorder_preroll'](source)
            self.assertEqual(ns['recorder_preroll'](patched), patched)
            harness = '''const assert=require('node:assert/strict');global.window={};let contexts=0,sources=0,closed=0,stopped=0;
class AudioContext{constructor(){contexts++;this.state='running';}createMediaStreamSource(){sources++;return{connect(){},disconnect(){}}}createDelay(max){assert.equal(max,1);return{delayTime:{value:0},connect(){},disconnect(){}}}createMediaStreamDestination(){return{stream:{getTracks(){return[{stop(){stopped++}}]}}}}close(){closed++;this.state='closed';return Promise.resolve()}}
class MediaRecorder{constructor(s){this.stream=s}}let S={};const r=x=>x;
'''
            run_js(harness + patched + '''const first=record();assert.notEqual(first.stream,S);assert.equal(window.__llRecordDelay.delayTime.value,.35);for(let i=0;i<20;i++)assert.equal(record().stream,first.stream);assert.equal(contexts,1);assert.equal(sources,1);close();assert.equal(closed,1);assert.equal(stopped,1);assert.equal(window.__llRecordDest,null);''')

    def test_new_interrupt_preserves_upstream_abort_and_realtime_guard(self):
        ns = definitions('call_audio', ('abort_playback_on_interrupt',))
        source = 'ie=async()=>{if(I())return I().stopSpeaking();__ll("interrupt:K="+r(q));c(q,!1),Oe.abort(),B&&S()()};'
        patched = ns['abort_playback_on_interrupt'](source)
        self.assertEqual(patched.count('Oe.abort()'), 1)
        self.assertEqual(ns['abort_playback_on_interrupt'](patched), patched)
        run_js('''const assert=require('node:assert/strict');let aborted=0,realtime=0,bridge=null,ie;const I=()=>bridge,__ll=()=>{},r=x=>x,c=()=>{},q=false,B=false,Oe={abort(){aborted++}};''' + patched + '''(async()=>{await ie();assert.equal(aborted,1);bridge={stopSpeaking(){realtime++}};await ie();assert.equal(aborted,1);assert.equal(realtime,1)})().catch(e=>{console.error(e);process.exitCode=1});''')


if __name__ == '__main__':
    unittest.main()
