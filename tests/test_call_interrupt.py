import ast
from pathlib import Path
import re
import subprocess
import sys
import unittest

PATCH=Path(__file__).resolve().parents[1]/'webui/patches/patch_openwebui_call_audio.py'

class InterruptTests(unittest.TestCase):
    def patcher(self):
        nodes=[n for n in ast.parse(PATCH.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='abort_playback_on_interrupt']
        if not nodes:return lambda text:text
        ns={'re':re,'sys':sys}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(PATCH),'exec'),ns)
        return ns['abort_playback_on_interrupt']

    def test_interrupt_cancels_queued_audio_and_next_reply_can_play(self):
        source=r'''
const assert=require('node:assert/strict');
const played=[];let settle;
const audio={muted:false,currentTime:1,pause(){settle?.();}};
const document={getElementById(){return audio;}};
const __ll=()=>{},r=x=>x,c=()=>{};
let K=true,B=false,de=null;
const De=async(__w)=>{__ll("interrupt:"+(__w||"?")+":K="+r(K)),c(K,!1),B&&k()(),de&&(speechSynthesis.cancel(),de=null);const ue=document.getElementById("audioElement");ue&&(ue.muted=!0,ue.pause(),ue.currentTime=0,ue.muted=!1)};let qe=new AbortController;const Ue=new Map,we=new Map;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function loop(queue,signal){while(!signal.aborted&&queue.length){played.push(queue.shift());await new Promise(r=>settle=r);await wait(20);}}
(async()=>{
 loop(['first','stale'],qe.signal);await wait(5);await De('vad');await wait(40);
 assert.deepEqual(played,['first'],'interruption must stop queued stale audio');
 assert.equal(audio.muted,false,'interruption must not leave read-aloud muted');
 qe=new AbortController;loop(['new reply'],qe.signal);await wait(5);
 assert.deepEqual(played,['first','new reply']);
 await De('tap');await wait(40);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        patched=self.patcher()(source)
        self.assertIsNotNone(patched)
        self.assertEqual(self.patcher()(patched),patched)
        result=subprocess.run(['node','-e',patched],text=True,capture_output=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
