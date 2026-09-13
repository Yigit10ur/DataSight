from pathlib import Path

from app.config import ENV_FILE, Settings


def test_the_env_file_is_found_from_any_working_directory():
    """The path is anchored to the source file, not to where the process started.

    A relative ".env" resolved against the working directory: the key loaded
    when the server was started from backend/ and quietly did not otherwise,
    which turns a missing explanation layer into a puzzle with no error message.
    """
    assert ENV_FILE.is_absolute()
    assert ENV_FILE == Path(__file__).resolve().parent.parent / ".env"
    assert Settings.model_config["env_file"] == ENV_FILE
