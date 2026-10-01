from app.accounts import google
from app.accounts.store import Account, AccountError, AccountStore, UsernameTaken
from app.config import settings

__all__ = ["Account", "AccountError", "AccountStore", "UsernameTaken", "account_store", "google"]

account_store = AccountStore(
    path=lambda: settings.database_path,
    session_ttl=lambda: settings.session_ttl_seconds,
)
