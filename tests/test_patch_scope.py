import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PatchScopeTests(unittest.TestCase):
    def test_unrelated_large_chunk_is_skipped_quickly(self):
        # Minified third-party bundles contain long identifiers/data. Unanchored
        # regexes must not scan those as if they were call-overlay components.
        source=(ROOT/'webui/patches/patch_openwebui_call_audio.py').read_text()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'vendor.js').write_text('const data="'+'x'*100000+'";')
            result=subprocess.run(['python3','-c',source],env=dict(os.environ, OWUI_CHUNKS=d),capture_output=True,text=True,timeout=3)
            self.assertNotEqual(result.returncode,0) # expected components are absent
            self.assertIn('expected one of each',result.stderr)
if __name__=='__main__':unittest.main()
