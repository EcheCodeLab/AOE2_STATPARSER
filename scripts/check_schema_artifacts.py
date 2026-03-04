#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_TABLES = {
    "matches",
    "players",
    "events_raw",
    "metrics_timeseries",
    "labels_ml",
    "spatial_frames",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_sql_tables(sql_text: str) -> set[str]:
    # Matches: create table if not exists public.table_name (
    pattern = re.compile(
        r"create\s+table\s+if\s+not\s+exists\s+public\.(\w+)\s*\(",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return {m.group(1).strip().lower() for m in pattern.finditer(sql_text)}


def _extract_contract_scope(contract_text: str) -> set[str]:
    m = re.search(r"^Scope:\s*(.+)$", contract_text, flags=re.MULTILINE)
    if not m:
        return set()
    names = set(re.findall(r"`([a-zA-Z0-9_]+)`", m.group(1)))
    return {n.lower() for n in names}


def _extract_contract_table_sections(contract_text: str) -> set[str]:
    names = re.findall(r"^##\s+Table:\s+`([a-zA-Z0-9_]+)`\s*$", contract_text, flags=re.MULTILINE)
    return {n.lower() for n in names}


def _extract_migration_names(migrations_md: str) -> set[str]:
    names = re.findall(r"`(\d{4}__[^`]+\.sql)`", migrations_md)
    return {n.strip() for n in names}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    schema_sql = root / "db" / "supabase_schema.sql"
    contract_md = root / "db" / "SCHEMA_CONTRACT.md"
    migrations_md = root / "db" / "MIGRATIONS.md"
    migrations_dir = root / "db" / "migrations"

    problems: list[str] = []

    if not schema_sql.exists():
        problems.append(f"Missing file: {schema_sql}")
    if not contract_md.exists():
        problems.append(f"Missing file: {contract_md}")
    if not migrations_md.exists():
        problems.append(f"Missing file: {migrations_md}")
    if not migrations_dir.exists():
        problems.append(f"Missing directory: {migrations_dir}")
    if problems:
        for p in problems:
            print(f"[ERR] {p}")
        return 1

    sql_tables = _extract_sql_tables(_read(schema_sql))
    missing_sql = sorted(REQUIRED_TABLES - sql_tables)
    if missing_sql:
        problems.append(f"Tables missing in supabase_schema.sql: {', '.join(missing_sql)}")

    contract_text = _read(contract_md)
    scope_tables = _extract_contract_scope(contract_text)
    missing_scope = sorted(REQUIRED_TABLES - scope_tables)
    if missing_scope:
        problems.append(f"Tables missing in SCHEMA_CONTRACT.md scope: {', '.join(missing_scope)}")

    section_tables = _extract_contract_table_sections(contract_text)
    missing_sections = sorted(REQUIRED_TABLES - section_tables)
    if missing_sections:
        problems.append(f"Missing table sections in SCHEMA_CONTRACT.md: {', '.join(missing_sections)}")

    migration_files = sorted(p.name for p in migrations_dir.glob("*.sql"))
    if not migration_files:
        problems.append("No migration files found in db/migrations")
    else:
        # Enforce lexical order and contiguous numbering from first migration.
        nums = []
        for f in migration_files:
            m = re.match(r"^(\d{4})__", f)
            if not m:
                problems.append(f"Migration file does not follow NNNN__name.sql: {f}")
                continue
            nums.append(int(m.group(1)))
        if nums:
            nums_sorted = sorted(nums)
            expected = list(range(nums_sorted[0], nums_sorted[-1] + 1))
            if nums_sorted != expected:
                problems.append(
                    "Migration numbering has gaps: "
                    f"found {nums_sorted}, expected contiguous {expected}"
                )

    migration_refs = _extract_migration_names(_read(migrations_md))
    missing_refs = sorted(set(migration_files) - migration_refs)
    if missing_refs:
        problems.append(
            "Migration files missing from MIGRATIONS.md naming examples/list: "
            + ", ".join(missing_refs)
        )

    if problems:
        for p in problems:
            print(f"[ERR] {p}")
        return 1

    print("[OK] Schema artifacts are consistent.")
    print(f"[OK] Tables checked: {', '.join(sorted(REQUIRED_TABLES))}")
    print(f"[OK] Migrations checked: {', '.join(migration_files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
