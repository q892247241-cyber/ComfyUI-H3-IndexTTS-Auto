"""Unit tests run without a GPU or ComfyUI. They do not validate RunningHub installation."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from h3_dialogue_parser import extract_h3_dialogue

# Simulate ComfyUI's package-style import from custom_nodes/<plugin>/__init__.py
spec = importlib.util.spec_from_file_location(
    "comfyui_h3_indextts_auto", str(ROOT / "__init__.py"),
    submodule_search_locations=[str(ROOT)],
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class DummyWaveform:
    def __init__(self, sample_count):
        self.shape = (1, 1, sample_count)


class TestRegistration(unittest.TestCase):
    def test_node_names(self):
        self.assertEqual(set(module.NODE_CLASS_MAPPINGS), {
            "H3DialogueExtractToIndexTTS", "H3DurationFromTTS"})
        self.assertEqual(set(module.NODE_DISPLAY_NAME_MAPPINGS),
                         set(module.NODE_CLASS_MAPPINGS))

    def test_input_and_output_contracts(self):
        node = module.H3DialogueExtractToIndexTTS
        inputs = node.INPUT_TYPES()
        self.assertEqual(list(inputs["required"]),
                         ["h3_prompt", "default_role", "strict", "allow_multi_role"])
        self.assertIn("role_aliases_json", inputs["optional"])
        self.assertEqual(node.RETURN_TYPES, ("STRING", "STRING"))
        dur = module.H3DurationFromTTS
        self.assertEqual(list(dur.INPUT_TYPES()["required"]),
                         ["audio", "min_seconds", "tail_padding_seconds", "max_audio_seconds"])
        self.assertEqual(dur.RETURN_TYPES, ("FLOAT", "STRING"))


class TestExtract(unittest.TestCase):
    def test_chinese_quote_emotion(self):
        text = "角色A用焦急质问的语气说：「你为什么现在才告诉我？」"
        rows, report = extract_h3_dialogue(text, "角色A")
        one = json.loads(rows)[0]
        self.assertEqual(one["role"], "角色A")
        self.assertEqual(one["text"], "你为什么现在才告诉我？")
        self.assertIn("焦急", one["emotion"]["text"])
        self.assertEqual(json.loads(report)["count"], 1)

    def test_d_tag_speaker(self):
        rows, _ = extract_h3_dialogue(
            "[Shot 2] <Subject 2> (S2) angrily commands: <d>[Chinese] 住手！</d>",
            "角色A")
        self.assertEqual(json.loads(rows)[0]["role"], "角色B")
        self.assertEqual(json.loads(rows)[0]["text"], "住手！")

    def test_aliases(self):
        rows, _ = extract_h3_dialogue('七七轻声说：「等我一下。」',
                                      '角色B', '{"七七":"角色A"}')
        one = json.loads(rows)[0]
        self.assertEqual(one["role"], "角色A")
        self.assertEqual(one["text"], "等我一下。")

    def test_no_dialogue_raises(self):
        with self.assertRaises(ValueError):
            extract_h3_dialogue("全景，人物走进房间，没有人开口。", "角色A")

    def test_multi_speaker_rejected_by_default(self):
        text = '角色A说：「你好。」角色B回答：「你好。」'
        with self.assertRaises(ValueError):
            extract_h3_dialogue(text, "角色A", strict=True, allow_multi_role=False)

    def test_multi_speaker_allowed(self):
        text = '角色A说：「你好。」角色B回答：「你好。」'
        rows, _ = extract_h3_dialogue(text, "角色A", strict=True, allow_multi_role=True)
        self.assertEqual(len(json.loads(rows)), 2)

    def test_node_returns_script(self):
        node = module.H3DialogueExtractToIndexTTS()
        script, report = node.extract("角色C冷静地说：『别吵了。』", "角色C")
        self.assertEqual(json.loads(script)[0]["role"], "角色C")
        self.assertEqual(json.loads(report)["count"], 1)


class TestDuration(unittest.TestCase):
    def test_tts_audio_length_and_padding(self):
        node = module.H3DurationFromTTS()
        duration, report = node.duration(
            {"sample_rate": 24000, "waveform": DummyWaveform(24000 * 6)},
            min_seconds=4.0, tail_padding_seconds=0.4, max_audio_seconds=15.0)
        self.assertAlmostEqual(duration, 6.4)
        self.assertAlmostEqual(json.loads(report)["tts_seconds"], 6.0)

    def test_minimum_duration(self):
        node = module.H3DurationFromTTS()
        seconds, _ = node.duration(
            {"sample_rate": 24000, "waveform": DummyWaveform(24000 * 2)})
        self.assertEqual(seconds, 4.0)

    def test_overlong_audio_raises(self):
        node = module.H3DurationFromTTS()
        with self.assertRaises(ValueError):
            node.duration({"sample_rate": 24000, "waveform": DummyWaveform(24000 * 16)})


if __name__ == '__main__':
    unittest.main()
