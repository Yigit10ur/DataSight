from app.accounts import github, google
from app.accounts.oauth import SignInError
from app.accounts.store import Account, AccountError, AccountStore, UsernameTaken
from app.config import settings

__all__ = [
    "Account",
    "AccountError",
    "AccountStore",
    "SignInError",
    "UsernameTaken",
    "account_store",
    "github",
    "google",
]

account_store = AccountStore(
    path=lambda: settings.database_path,
    session_ttl=lambda: settings.session_ttl_seconds,
)
