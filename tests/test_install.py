import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InstallerTests(unittest.TestCase):
    def shell(self, command, env=None):
        return subprocess.run(['bash', '-c', 'set -euo pipefail; source scripts/install_helpers.sh; ' + command], cwd=ROOT, env=env, text=True, capture_output=True)

    def test_missing_model_is_not_valid_even_with_marker(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model'; Path(str(p)+'.ok').touch()
            self.assertNotEqual(self.shell(f'model_verified "{p}" 3 unused').returncode,0)

    def test_same_size_corruption_is_detected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model'; p.write_bytes(b'bad'); Path(str(p)+'.ok').touch()
            digest=hashlib.sha256(b'yes').hexdigest()
            self.assertNotEqual(self.shell(f'model_verified "{p}" 3 {digest}').returncode,0)
            p.write_bytes(b'yes')
            self.assertEqual(self.shell(f'model_verified "{p}" 3 {digest}').returncode,0)

    def test_model_validation_follows_symlinks(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'cached-model'; target.write_bytes(b'yes')
            link=Path(d)/'model'; link.symlink_to(target)
            digest=hashlib.sha256(b'yes').hexdigest()
            self.assertEqual(self.shell(f'model_verified "{link}" 3 {digest}').returncode,0)
            target.write_bytes(b'bad')
            self.assertNotEqual(self.shell(f'model_verified "{link}" 3 {digest}').returncode,0)

    def test_failed_pull_builds_even_if_old_image_exists(self):
        r=self.shell('docker() { echo "$*"; if [[ "$*" == "pull "*-voice@* ]]; then return 1; fi; }; prepare_images')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('build setup',r.stdout)
        self.assertNotIn('build whisper',r.stdout)
        self.assertIn('build webui',r.stdout)

    def test_speech_images_are_pulled_by_digest_under_the_compose_tag(self):
        import re
        r=self.shell('docker() { echo "$*"; }; prepare_images')
        self.assertEqual(r.returncode,0,r.stderr)
        compose=(ROOT/'compose.yml').read_text()
        for service,image in (('setup','npu-cosyvoice-voice'),('whisper','npu-cosyvoice-whisper')):
            tag=re.search(r'image: (ghcr\.io/\S+/'+image+r':[\w.]+)',compose).group(1)
            pulled=re.search(r'^pull (\S+/'+image+r'@sha256:\S+)$',r.stdout,re.M)
            self.assertTrue(pulled,r.stdout)
            self.assertIn(f'tag {pulled.group(1)} {tag}',r.stdout)
            self.assertRegex(pulled.group(1),r'@sha256:[0-9a-f]{64}$')
        self.assertIn('#v'+re.search(r'npu-cosyvoice-voice:([\w.]+)',compose).group(1)+'}',compose)

    def test_ready_uses_actual_published_port(self):
        r=self.shell('docker() { echo "127.0.0.1:32770"; }; published_webui_port')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(r.stdout.strip(),'32770')
        for mapping in ('', '127.0.0.1:0', '127.0.0.1:bad'):
            r=self.shell('docker() { echo "'+mapping+'"; }; published_webui_port')
            self.assertNotEqual(r.returncode,0)

    def test_ready_requires_recognizer_and_ui(self):
        for service in ('whisper','webui','voice'):
            r=self.shell('docker() { [[ "$*" != *"exec -T '+service+' "* ]]; }; services_ready')
            self.assertNotEqual(r.returncode,0,service)
        self.assertEqual(self.shell('docker() { return 0; }; services_ready').returncode,0)

    def test_grub_replaces_wrong_values_and_preserves_other_options(self):
        spec=importlib.util.spec_from_file_location('support', ROOT/'scripts/install_support.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        old='GRUB_TIMEOUT=5\nGRUB_CMDLINE_LINUX_DEFAULT="quiet amdgpu.gttsize=1024 splash ttm.pages_limit=1"\n'
        new=m.render_grub(old)
        self.assertTrue(m.grub_ready(new))
        self.assertIn('quiet',new);self.assertIn('splash',new);self.assertIn('GRUB_TIMEOUT=5',new)
        self.assertEqual(m.render_grub(new),new)
        self.assertFalse(m.grub_ready(old))
        with self.assertRaises(ValueError):m.render_grub('GRUB_CMDLINE_LINUX_DEFAULT=$CUSTOM\n')

if __name__=='__main__': unittest.main()
