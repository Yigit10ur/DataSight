from threading import Lock, RLock

_locks: dict[tuple[str, str], Lock] = {}
_guard = RLock()
MAX_LOCKS_PER_DATASET = 50


def question_lock(dataset_id: str, question: str) -> Lock:
    key = (dataset_id, " ".join(question.lower().split()))
    with _guard:
        owned = [item for item in _locks if item[0] == dataset_id]
        for old in owned[: max(0, len(owned) - MAX_LOCKS_PER_DATASET + 1)]:
            if not _locks[old].locked():
                _locks.pop(old, None)
        return _locks.setdefault(key, Lock())


def clear_question_state(dataset_id: str) -> None:
    with _guard:
        for key in [key for key in _locks if key[0] == dataset_id]:
            _locks.pop(key, None)
