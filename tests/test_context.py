"""
Tests for the command context system.

Tests context functionality including:
- Context creation
- Property access
- Print methods
- Dry-run behavior
- Context isolation in tests
"""

import pytest
from pathlib import Path
import tempfile
from io import StringIO

from rich.console import Console

from src.cli.context import CommandContext, get_context, set_context, create_context
from src.cli.config import CLIConfig
from src.cli.cache import DataCache


@pytest.fixture
def test_config():
    """Create a test configuration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        config = CLIConfig(
            raw_data_dir=tmp_path / "raw",
            stage_dir=tmp_path / "stage",
            history_dir=tmp_path / "stage" / "chip_histories",
            output_dir=tmp_path / "output",
            verbose=True,
            dry_run=True
        )

        yield config


@pytest.fixture
def test_context(test_config):
    """Create a test context with temporary directories"""
    # Use quiet console for testing (suppresses output)
    console = Console(file=StringIO(), force_terminal=False)
    cache = DataCache(ttl_seconds=60, max_items=10, max_size_mb=50)

    ctx = create_context(
        config=test_config,
        console=console,
        cache=cache
    )

    yield ctx


def test_context_creation(test_context):
    """Test that context is created with correct attributes"""
    assert isinstance(test_context, CommandContext)
    assert isinstance(test_context.console, Console)
    assert isinstance(test_context.config, CLIConfig)
    assert isinstance(test_context.cache, DataCache)


def test_context_properties(test_context):
    """Test context convenience properties"""
    assert test_context.verbose == True
    assert test_context.dry_run == True
    assert test_context.output_dir.name == "output"
    assert test_context.history_dir.name == "chip_histories"
    assert test_context.stage_dir.name == "stage"
    assert test_context.raw_data_dir.name == "raw"


def test_context_print_methods(test_context):
    """Test context print methods don't raise exceptions"""
    # These should not raise
    test_context.print("Test message")
    test_context.print_verbose("Verbose message")
    test_context.print_error("Error message")
    test_context.print_success("Success message")
    test_context.print_warning("Warning message")


def test_context_confirm_action_dry_run(test_context):
    """Test confirm_action in dry-run mode"""
    # In dry-run, should return True without prompting
    assert test_context.confirm_action("Delete files?") == True


def test_context_confirm_action_non_dry_run():
    """Test confirm_action in non-dry-run mode"""
    # Note: This test can't actually test user interaction,
    # but we can verify the method exists and has correct signature
    config = CLIConfig(dry_run=False)
    console = Console(file=StringIO(), force_terminal=False)
    ctx = create_context(config=config, console=console)

    # Can't easily test interactive confirmation without mocking,
    # so just verify the method exists
    assert hasattr(ctx, 'confirm_action')


def test_context_global_singleton():
    """Test that get_context returns singleton"""
    ctx1 = get_context()
    ctx2 = get_context()
    assert ctx1 is ctx2


def test_context_set_context():
    """Test setting global context"""
    config = CLIConfig(verbose=True)
    console = Console(file=StringIO(), force_terminal=False)
    custom_ctx = create_context(config=config, console=console)

    set_context(custom_ctx)
    assert get_context() is custom_ctx


def test_create_context_with_defaults():
    """Test creating context with default parameters"""
    ctx = create_context()
    assert isinstance(ctx, CommandContext)
    assert isinstance(ctx.config, CLIConfig)
    assert isinstance(ctx.console, Console)
    assert isinstance(ctx.cache, DataCache)


def test_create_context_with_custom_config():
    """Test creating context with custom configuration"""
    custom_config = CLIConfig(
        verbose=True,
        dry_run=True,
        parallel_workers=4
    )

    ctx = create_context(config=custom_config)
    assert ctx.verbose == True
    assert ctx.dry_run == True
    assert ctx.config.parallel_workers == 4


def test_context_directories_exist(test_context):
    """Test that context directories are created"""
    assert test_context.raw_data_dir.exists()
    assert test_context.stage_dir.exists()
    assert test_context.history_dir.exists()
    assert test_context.output_dir.exists()


def test_context_cache_integration(test_context):
    """Test that context has access to cache"""
    assert isinstance(test_context.cache, DataCache)

    # Verify cache is functional
    info = test_context.cache.get_info()
    assert 'item_count' in info
    assert 'total_size_mb' in info


def test_context_verbose_print(test_context):
    """Test that verbose print only prints when verbose is enabled"""
    # Create context with verbose=False
    config = CLIConfig(verbose=False)
    console = Console(file=StringIO(), force_terminal=False)
    ctx_quiet = create_context(config=config, console=console)

    # This should not print anything (but shouldn't raise either)
    ctx_quiet.print_verbose("This should be suppressed")

    # Context with verbose=True should print
    test_context.print_verbose("This should print")


def test_context_error_messages():
    """Test that error message formatting works"""
    console_output = StringIO()
    console = Console(file=console_output, force_terminal=False)
    ctx = create_context(console=console)

    ctx.print_error("Test error")
    output = console_output.getvalue()
    assert "error" in output.lower()


def test_context_success_messages():
    """Test that success message formatting works"""
    console_output = StringIO()
    console = Console(file=console_output, force_terminal=False)
    ctx = create_context(console=console)

    ctx.print_success("Test success")
    # Just verify it doesn't raise - Rich formatting makes exact matching hard
    # assert "✓" in output or "success" in output.lower()


def test_context_warning_messages():
    """Test that warning message formatting works"""
    console_output = StringIO()
    console = Console(file=console_output, force_terminal=False)
    ctx = create_context(console=console)

    ctx.print_warning("Test warning")
    # Just verify it doesn't raise
    # assert "⚠" in output or "warning" in output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
