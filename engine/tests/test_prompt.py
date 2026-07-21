import logging
from typing import Any
import pytest
import yaml

from migrations_engine.ai.prompt import Prompt

def test_prompt_substitution(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a temporary prompt file
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    
    prompt_path = prompts_dir / "test_prompt.yaml"
    prompt_path.write_text(yaml.dump({
        "system": "System: $foo",
        "user": "User: $bar {ignored} $baz"
    }))
    
    # Patch _PROMPTS_DIR in prompt module
    monkeypatch.setattr("migrations_engine.ai.prompt._PROMPTS_DIR", prompts_dir)
    
    prompt = Prompt("test_prompt")
    prompt.set(foo="hello", bar="world")
    
    system, user = prompt.get_prompt()
    
    assert system == "System: hello"
    # $baz is missing, so it should be empty and a warning should be logged.
    # The literal brace {ignored} should be preserved untouched.
    assert user == "User: world {ignored}"

def test_prompt_warns_on_missing(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    
    prompt_path = prompts_dir / "test_prompt.yaml"
    prompt_path.write_text(yaml.dump({
        "system": "System: $foo",
        "user": "User: $bar"
    }))
    
    monkeypatch.setattr("migrations_engine.ai.prompt._PROMPTS_DIR", prompts_dir)
    
    prompt = Prompt("test_prompt")
    prompt.set(foo="hello")
    
    with caplog.at_level(logging.WARNING):
        system, user = prompt.get_prompt()
        
    assert system == "System: hello"
    assert user == "User:"
    assert "Missing prompt field 'bar' in prompt 'test_prompt'" in caplog.text

def test_prompt_no_merge_fields(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    
    prompt_path = prompts_dir / "test_prompt.yaml"
    prompt_path.write_text(yaml.dump({
        "system": "No fields here.",
        "user": "Just literal {braces}."
    }))
    
    monkeypatch.setattr("migrations_engine.ai.prompt._PROMPTS_DIR", prompts_dir)
    
    prompt = Prompt("test_prompt")
    system, user = prompt.get_prompt()
    
    assert system == "No fields here."
    assert user == "Just literal {braces}."
