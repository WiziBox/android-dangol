# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dangol_stage', ROOT / 'tools/stage_device.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StageDeviceTests(unittest.TestCase):
    def workspace(self, base):
        source = base / 'android'
        (source / 'build').mkdir(parents=True)
        (source / 'build/envsetup.sh').write_text('# synthetic workspace')
        return source

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.workspace(Path(temp))
            result = module.stage(source)
            self.assertEqual(result['files_preflighted'], 48)
            self.assertFalse((source / 'device').exists())
            self.assertFalse(result['device_io'])

    def test_apply_new_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.workspace(Path(temp))
            result = module.stage(source, True)
            self.assertTrue(result['device_sources_staged'])
            self.assertEqual(len(list((source / 'device/nexell/dangol').rglob('*.*'))), 48)
            with self.assertRaises(ValueError):
                module.stage(source, True)

    def test_missing_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                module.stage(Path(temp))

    def test_unsafe_paths(self):
        for value in ('../bad', '/bad', 'a\\b', 'C:bad', 'a/.git/b', './a', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.relative(value)

    def test_config_policy(self):
        tree = ROOT / 'source/device/nexell/dangol'
        product = (tree / 'device.mk').read_text()
        self.assertIn('ro.hardware.hwcomposer=dangol', product)
        self.assertNotIn('ro.hardware.hwcomposer=dangol_next', product)
        self.assertNotIn('bcmdhd.ko:', product)
        self.assertNotIn('audio_policy.conf:', product)
        product_defaults = (tree / 'lineage_dangol.mk').read_text()
        self.assertIn('ro.adb.secure=1', product_defaults)
        self.assertNotIn('5555', product_defaults)
        index = json.loads((ROOT / 'source/dangol-device-provenance.json').read_text())
        self.assertEqual(len(index['files']), 16)
        for entry in index['files']:
            self.assertIn('SPDX-License-Identifier: Apache-2.0', (tree / entry['path']).read_text())


if __name__ == '__main__':
    unittest.main()
