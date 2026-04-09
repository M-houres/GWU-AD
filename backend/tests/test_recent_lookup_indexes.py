from app.models import CreditTransaction, Task


def _index_columns(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in index.columns)
        for index in table.indexes
    }


def test_recent_lookup_indexes_declared() -> None:
    task_indexes = _index_columns(Task.__table__)
    credit_indexes = _index_columns(CreditTransaction.__table__)

    assert ("user_id", "id") in task_indexes
    assert ("user_id", "id") in credit_indexes
