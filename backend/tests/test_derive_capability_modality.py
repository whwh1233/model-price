"""Tests for the unified capability/modality deriver.

Capabilities and modalities used to be derived by two independent
functions with drifting signal sources. The unified deriver must
guarantee that any flag touching the capability set also touches
input/output modalities consistently — regressing to the old split
would resurrect the "Cohere Embed v4 has vision tag but text-only
input" bug.
"""

from services.litellm_registry import derive_capability_modality


class TestEmbeddingWithImageInput:
    def test_embedding_image_input_flag_sets_both_vision_and_image_modality(self):
        raw = {"mode": "embedding", "supports_embedding_image_input": True}
        caps, in_mods, out_mods = derive_capability_modality(raw)
        assert "vision" in caps
        assert "embedding" in caps
        assert "image" in in_mods
        assert out_mods == ["embedding"]
        # embedding mode drops text from caps (no text output) but keeps
        # text as an input modality alongside image.
        assert "text" not in caps
        assert "text" in in_mods

    def test_plain_embedding_has_no_vision(self):
        raw = {"mode": "embedding"}
        caps, in_mods, out_mods = derive_capability_modality(raw)
        assert "vision" not in caps
        assert in_mods == ["text"]
        assert out_mods == ["embedding"]


class TestAudioModes:
    def test_audio_transcription_marks_audio_input(self):
        caps, in_mods, out_mods = derive_capability_modality(
            {"mode": "audio_transcription"}
        )
        assert "audio" in caps
        assert "audio" in in_mods
        assert "audio" not in out_mods

    def test_audio_speech_marks_audio_output(self):
        caps, in_mods, out_mods = derive_capability_modality(
            {"mode": "audio_speech"}
        )
        assert "audio" in caps
        assert "audio" not in in_mods
        assert "audio" in out_mods

    def test_audio_input_flag_still_marks_audio(self):
        caps, in_mods, _ = derive_capability_modality(
            {"mode": "chat", "supports_audio_input": True}
        )
        assert "audio" in caps
        assert "audio" in in_mods

    def test_audio_output_flag_still_marks_audio(self):
        caps, _, out_mods = derive_capability_modality(
            {"mode": "chat", "supports_audio_output": True}
        )
        assert "audio" in caps
        assert "audio" in out_mods


class TestVisionFlags:
    def test_supports_vision_adds_image_input(self):
        caps, in_mods, _ = derive_capability_modality(
            {"mode": "chat", "supports_vision": True}
        )
        assert "vision" in caps
        assert "image" in in_mods

    def test_supports_pdf_input_adds_image_input(self):
        caps, in_mods, _ = derive_capability_modality(
            {"mode": "chat", "supports_pdf_input": True}
        )
        assert "vision" in caps
        assert "image" in in_mods


class TestImageGeneration:
    def test_image_generation_mode(self):
        caps, in_mods, out_mods = derive_capability_modality(
            {"mode": "image_generation"}
        )
        assert "image_generation" in caps
        assert "text" not in caps
        assert "image" in in_mods
        assert out_mods == ["image"]


class TestCapsModalityInvariants:
    def test_vision_implies_image_input(self):
        """Whenever vision is in caps, image must be in input modalities."""
        for flag in ("supports_vision", "supports_pdf_input", "supports_embedding_image_input"):
            caps, in_mods, _ = derive_capability_modality({"mode": "chat", flag: True})
            assert "vision" in caps
            assert "image" in in_mods, f"{flag} marked vision but not image"

    def test_audio_cap_implies_audio_modality(self):
        """audio in caps must always reflect in at least one modality."""
        cases = [
            {"mode": "audio_transcription"},
            {"mode": "audio_speech"},
            {"mode": "chat", "supports_audio_input": True},
            {"mode": "chat", "supports_audio_output": True},
        ]
        for raw in cases:
            caps, in_mods, out_mods = derive_capability_modality(raw)
            assert "audio" in caps
            assert "audio" in in_mods or "audio" in out_mods, raw
