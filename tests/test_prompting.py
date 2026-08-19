from pathlib import Path

import pytest

from briefly.prompting import BackendType, build_prompt


def test_build_prompt_extraction():
    prompt = build_prompt(Path("paper.pdf"), type=BackendType.EXTRACTION)
    assert "paper.pdf" in prompt


def test_build_prompt_raises_for_unimplemented_backend_types():
    with pytest.raises(NotImplementedError):
        build_prompt(Path("paper.pdf"), type=BackendType.DIGESTION)
