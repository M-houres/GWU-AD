import importlib.util
from pathlib import Path
from types import SimpleNamespace


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c3d9e1f7a2b4_expand_task_status_enum_for_preprocessing.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("task_status_enum_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_upgrade_expands_mysql_task_status_enum(monkeypatch) -> None:
    module = _load_migration_module()
    alter_calls: list[dict] = []

    class FakeOp:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="mysql"))

        def alter_column(self, table_name, column_name, **kwargs):
            alter_calls.append({"table_name": table_name, "column_name": column_name, **kwargs})

        def execute(self, _statement):
            raise AssertionError("mysql upgrade should alter the enum column directly")

    monkeypatch.setattr(module, "op", FakeOp())

    module.upgrade()

    assert len(alter_calls) == 1
    call = alter_calls[0]
    assert call["table_name"] == "tasks"
    assert call["column_name"] == "status"
    assert tuple(call["existing_type"].enums) == module.OLD_TASK_STATUS_VALUES
    assert tuple(call["type_"].enums) == module.NEW_TASK_STATUS_VALUES


def test_downgrade_normalizes_new_statuses_before_mysql_enum_shrink(monkeypatch) -> None:
    module = _load_migration_module()
    alter_calls: list[dict] = []
    statements: list[str] = []

    class FakeOp:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="mysql"))

        def alter_column(self, table_name, column_name, **kwargs):
            alter_calls.append({"table_name": table_name, "column_name": column_name, **kwargs})

        def execute(self, statement):
            statements.append(str(statement))

    monkeypatch.setattr(module, "op", FakeOp())

    module.downgrade()

    assert statements == ["UPDATE tasks SET status = 'PENDING' WHERE status IN ('PREPROCESSING', 'QUEUED')"]
    assert len(alter_calls) == 1
    call = alter_calls[0]
    assert call["table_name"] == "tasks"
    assert call["column_name"] == "status"
    assert tuple(call["existing_type"].enums) == module.NEW_TASK_STATUS_VALUES
    assert tuple(call["type_"].enums) == module.OLD_TASK_STATUS_VALUES
