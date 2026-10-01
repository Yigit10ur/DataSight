import pytest

from app.accounts import Account
from app.api.auth import current_account
from app.config import settings
from app.main import app

# Most tests are about datasets, not accounts, and run as this one signed-in account.
TEST_ACCOUNT = Account(id="test-account", username="tester")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "accounts: sign in through the real account routes instead of as TEST_ACCOUNT"
    )


@pytest.fixture(autouse=True)
def accounts_database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "accounts.db")


@pytest.fixture(autouse=True)
def roomy_account(monkeypatch):
    """Every test shares TEST_ACCOUNT and the one store, so lift its per-account caps.

    Tests about those caps set them again themselves.
    """
    monkeypatch.setattr(settings, "max_datasets_per_user", 10_000)
    monkeypatch.setattr(settings, "max_user_store_bytes", 1 << 40)


@pytest.fixture(autouse=True)
def signed_in(request):
    if request.node.get_closest_marker("accounts"):
        yield
        return
    app.dependency_overrides[current_account] = lambda: TEST_ACCOUNT
    yield
    app.dependency_overrides.pop(current_account, None)
