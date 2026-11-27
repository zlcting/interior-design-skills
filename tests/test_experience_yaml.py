"""Keep shipped authoring examples compatible with the SDK publisher adapter."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/interior-experience-yaml'

def actions(value):
    if isinstance(value, dict):
        if 'operation' in value and 'capabilityKey' in value:
            yield value
        for child in value.values():
            yield from actions(child)
    elif isinstance(value, list):
        for child in value:
            yield from actions(child)

class ExperienceYamlTests(unittest.TestCase):
    def test_boolean_and_sample_examples_are_immediate_without_changing_cameras(self):
        document = yaml.safe_load((SKILL / 'assets/方案中心-体验编排模板-第2稿.yaml').read_text())
        all_actions = list(actions(document))
        self.assertGreater(len(all_actions), 10)
        for action in all_actions:
            if isinstance(action['value'], bool) or action['operation'] != 'write':
                self.assertEqual(action.get('transitionMs', 0), 0, action)
        curtain = next(a for a in all_actions if a['capabilityKey'] == 'position')
        self.assertEqual(curtain['transitionMs'], 4500)
        self.assertEqual(document['defaults']['camera']['transitionMs'], 800)
        self.assertEqual(document['cameraPresets']['kitchen-device']['transitionMs'], 600)
        self.assertFalse(document['initialState']['furniture_mw4nxz05']['power'])
        self.assertEqual(document['initialState']['furniture_mw4rn5u1']['position'], 0)

    def test_template_does_not_ship_unsupported_events_or_object_command_arguments(self):
        document = yaml.safe_load((SKILL / 'assets/方案中心-体验编排模板-第2稿.yaml').read_text())
        self.assertIn('REPLACE_', document['sceneVersionId'])
        for action in actions(document):
            self.assertNotEqual(action['operation'], 'subscribe')
            if action['operation'] == 'execute':
                self.assertIsNone(action['value'])

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_checker_requires_explicit_business_context_or_sdk_only_mode(self):
        result = subprocess.run(['node', str(SKILL / 'scripts/check-experience.mjs'),
            '--business-root', '/missing', '--home3d', '/missing', '--yaml', '/missing',
            '--scene-version', 'confirmed'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Choose exactly one', json.loads(result.stderr)['error'])
