"""
Tests for the formal Pipeline builder.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
import time

from src.core.pipeline import (
    Pipeline,
    PipelineStep,
    StepStatus,
    PipelineResult,
    PipelineState,
)


def test_pipeline_creation():
    """Test basic pipeline creation and step addition."""
    pipeline = Pipeline("test-pipeline", description="Test pipeline")

    assert pipeline.name == "test-pipeline"
    assert pipeline.description == "Test pipeline"
    assert len(pipeline.steps) == 0


def test_add_step():
    """Test adding steps to pipeline."""
    pipeline = Pipeline("test")

    def mock_command(arg1, arg2):
        return arg1 + arg2

    pipeline.add_step(
        "test-step",
        mock_command,
        arg1=1,
        arg2=2,
        retry_count=2,
    )

    assert len(pipeline.steps) == 1
    step = pipeline.steps[0]
    assert step.name == "test-step"
    assert step.command == mock_command
    assert step.kwargs == {"arg1": 1, "arg2": 2}
    assert step.retry_count == 2


def test_method_chaining():
    """Test that add_step supports method chaining."""
    pipeline = (
        Pipeline("test")
        .add_step("step1", lambda: None)
        .add_step("step2", lambda: None)
        .add_step("step3", lambda: None)
    )

    assert len(pipeline.steps) == 3


def test_successful_pipeline_execution():
    """Test successful execution of all steps."""
    pipeline = Pipeline("test")

    results = []

    def step1():
        results.append("step1")
        return "result1"

    def step2():
        results.append("step2")
        return "result2"

    pipeline.add_step("step1", step1)
    pipeline.add_step("step2", step2)

    result = pipeline.execute(stop_on_error=True)

    assert result.success
    assert result.successful_steps == 2
    assert result.failed_steps == 0
    assert results == ["step1", "step2"]


def test_pipeline_failure_stops_execution():
    """Test that pipeline stops on first failure."""
    pipeline = Pipeline("test")

    executed_steps = []

    def step1():
        executed_steps.append("step1")

    def step2():
        executed_steps.append("step2")
        raise ValueError("Step 2 failed")

    def step3():
        executed_steps.append("step3")

    pipeline.add_step("step1", step1)
    pipeline.add_step("step2", step2)
    pipeline.add_step("step3", step3)

    result = pipeline.execute(stop_on_error=True)

    assert not result.success
    assert result.successful_steps == 1
    assert result.failed_steps == 1
    assert executed_steps == ["step1", "step2"]  # step3 not executed


def test_skip_on_error():
    """Test that pipeline continues when skip_on_error=True."""
    pipeline = Pipeline("test")

    executed_steps = []

    def step1():
        executed_steps.append("step1")

    def step2():
        executed_steps.append("step2")
        raise ValueError("Step 2 failed")

    def step3():
        executed_steps.append("step3")

    pipeline.add_step("step1", step1)
    pipeline.add_step("step2", step2, skip_on_error=True)  # Skip on error
    pipeline.add_step("step3", step3)

    result = pipeline.execute(stop_on_error=True)

    assert result.success  # Overall success despite step2 failure
    assert result.successful_steps == 2
    assert result.skipped_steps == 1
    assert executed_steps == ["step1", "step2", "step3"]


def test_retry_logic():
    """Test that steps retry on failure."""
    pipeline = Pipeline("test")

    attempt_count = {"count": 0}

    def flaky_command():
        attempt_count["count"] += 1
        if attempt_count["count"] < 3:
            raise ValueError("Transient failure")
        return "success"

    pipeline.add_step("flaky", flaky_command, retry_count=3, retry_delay=0.1)

    result = pipeline.execute(stop_on_error=True)

    assert result.success
    assert attempt_count["count"] == 3  # Failed twice, succeeded on third


def test_rollback_on_failure():
    """Test that rollback functions are called on failure."""
    pipeline = Pipeline("test")

    rollback_calls = []

    def step1():
        return "success"

    def rollback1():
        rollback_calls.append("rollback1")

    def step2():
        raise ValueError("Step 2 failed")

    def rollback2():
        rollback_calls.append("rollback2")

    pipeline.add_step("step1", step1, rollback_fn=rollback1)
    pipeline.add_step("step2", step2, rollback_fn=rollback2)

    result = pipeline.execute(stop_on_error=True, enable_rollback=True)

    assert not result.success
    assert rollback_calls == ["rollback1"]  # Only successful step rolled back


def test_checkpoint_save_and_load():
    """Test checkpoint save and load functionality."""
    pipeline = Pipeline("test", checkpoint_dir=Path("data/.test_checkpoints"))

    def step1():
        return "result1"

    pipeline.add_step("step1", step1, checkpoint=True)
    result = pipeline.execute(stop_on_error=True)

    # Load checkpoint
    checkpoint = pipeline.state.load_checkpoint()

    assert checkpoint is not None
    assert checkpoint["pipeline_name"] == "test"
    assert len(checkpoint["steps"]) == 1
    assert checkpoint["steps"][0]["status"] == "success"

    # Cleanup
    pipeline.state.clear_checkpoints()


def test_pipeline_yaml_export():
    """Test exporting pipeline definition to YAML."""
    import tempfile

    pipeline = Pipeline("test", description="Test pipeline")

    def mock_command(arg1, arg2):
        pass

    pipeline.add_step("step1", mock_command, arg1=1, arg2=2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml_path = Path(f.name)

    try:
        pipeline.to_yaml(yaml_path)

        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "name: test" in content
        assert "step1" in content
    finally:
        yaml_path.unlink(missing_ok=True)


def test_pipeline_yaml_import():
    """Test loading pipeline from YAML definition."""
    import tempfile
    import yaml

    # Create test YAML
    pipeline_def = {
        "name": "test-import",
        "description": "Test import",
        "steps": [
            {
                "name": "step1",
                "command": "mock_command",
                "kwargs": {"arg1": 1, "arg2": 2},
                "skip_on_error": False,
                "retry_count": 0,
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(pipeline_def, f)
        yaml_path = Path(f.name)

    try:
        def mock_command(arg1, arg2):
            return arg1 + arg2

        command_registry = {"mock_command": mock_command}

        pipeline = Pipeline.from_yaml(yaml_path, command_registry)

        assert pipeline.name == "test-import"
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].name == "step1"
        assert pipeline.steps[0].kwargs == {"arg1": 1, "arg2": 2}
    finally:
        yaml_path.unlink(missing_ok=True)


def test_step_timing():
    """Test that step timing is recorded."""
    pipeline = Pipeline("test")

    def slow_step():
        time.sleep(0.1)

    pipeline.add_step("slow", slow_step)
    result = pipeline.execute(stop_on_error=True)

    step = result.steps[0]
    assert step.elapsed_time is not None
    assert step.elapsed_time >= 0.1


def test_pipeline_result_attributes():
    """Test PipelineResult attributes."""
    pipeline = Pipeline("test")

    def success():
        pass

    def failure():
        raise ValueError("Failed")

    pipeline.add_step("success", success)
    pipeline.add_step("failure", failure, skip_on_error=True)

    result = pipeline.execute(stop_on_error=True)

    assert result.pipeline_name == "test"
    assert result.total_steps == 2
    assert result.successful_steps == 1
    assert result.skipped_steps == 1
    assert result.success  # Overall success due to skip_on_error


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Provide temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


def test_resume_from_checkpoint(temp_checkpoint_dir):
    """Test resuming pipeline from checkpoint."""
    # First execution (partial)
    pipeline1 = Pipeline("test", checkpoint_dir=temp_checkpoint_dir)

    executed = []

    def step1():
        executed.append("step1")

    def step2():
        executed.append("step2")
        raise ValueError("Failed")

    def step3():
        executed.append("step3")

    pipeline1.add_step("step1", step1, checkpoint=True)
    pipeline1.add_step("step2", step2, checkpoint=True)
    pipeline1.add_step("step3", step3)

    result1 = pipeline1.execute(stop_on_error=True)
    assert not result1.success
    assert executed == ["step1", "step2"]

    # Second execution (resume)
    pipeline2 = Pipeline("test", checkpoint_dir=temp_checkpoint_dir)
    pipeline2.add_step("step1", step1, checkpoint=True)
    pipeline2.add_step("step2", step2, checkpoint=True)  # Will fail again
    pipeline2.add_step("step3", step3)

    # Note: Current implementation doesn't skip completed steps automatically
    # This would require enhancing the resume logic to check checkpoint status
    # For now, this test documents the current behavior
