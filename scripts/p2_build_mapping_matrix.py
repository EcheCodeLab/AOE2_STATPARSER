#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _has_path(inv: dict[str, Any], method: str, path: str) -> bool:
    try:
        return path in inv["part2"]["P2-001_mgz_summary_inventory"]["paths"][method]
    except Exception:
        return False


def _rows() -> list[dict[str, str]]:
    return [
        # MatchMeta / P2-009
        {
            "canonical_entity": "match_meta",
            "canonical_field": "match_id",
            "p2_ids": "P2-003,P2-009",
            "source_lib": "local",
            "source_accessor": "replay filename stem",
            "source_path": "<path>.stem",
            "transform": "identity",
            "status_target": "derivable",
            "notes": "No viene de mgz; se deriva del archivo",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "duration_sec",
            "p2_ids": "P2-005,P2-009",
            "source_lib": "mgz.fast",
            "source_accessor": "postgame",
            "source_path": "world_time",
            "transform": "world_time/1000",
            "status_target": "direct",
            "notes": "Fuente principal actual",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "duration_sec",
            "p2_ids": "P2-005,P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_duration",
            "source_path": "$",
            "transform": "/1000",
            "status_target": "direct",
            "notes": "Fallback viable",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "map_id",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_map",
            "source_path": "id",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "map_name",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_map",
            "source_path": "name",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "map_dimension",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_map",
            "source_path": "dimension",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "map_seed",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_map",
            "source_path": "seed",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "dataset_name",
            "p2_ids": "P2-009,P2-024",
            "source_lib": "mgz.summary",
            "source_accessor": "get_dataset",
            "source_path": "name",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "dataset_id",
            "p2_ids": "P2-009,P2-024",
            "source_lib": "mgz.summary",
            "source_accessor": "get_dataset",
            "source_path": "id",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "patch_or_version",
            "p2_ids": "P2-009,P2-024",
            "source_lib": "mgz.summary",
            "source_accessor": "get_version",
            "source_path": "$",
            "transform": "stringify",
            "status_target": "direct",
            "notes": "Normalizar luego a string estable",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "diplomacy_type",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_diplomacy",
            "source_path": "type",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "match_meta",
            "canonical_field": "team_size",
            "p2_ids": "P2-009",
            "source_lib": "mgz.summary",
            "source_accessor": "get_diplomacy",
            "source_path": "team_size",
            "transform": "identity",
            "status_target": "direct",
            "notes": "",
        },
        # PlayerMeta / P2-010
        {
            "canonical_entity": "player_meta",
            "canonical_field": "player_id",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].number",
            "transform": "int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "player_name",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].name",
            "transform": "str",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "civilization_id",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].civilization",
            "transform": "int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "color_id",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].color_id",
            "transform": "int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "winner",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].winner",
            "transform": "bool",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "team_id",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_teams+get_players",
            "source_path": "get_teams + [].number mapping",
            "transform": "join by player number",
            "status_target": "derivable",
            "notes": "No viene plano en get_players",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "eapm",
            "p2_ids": "P2-010,P2-017",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].eapm",
            "transform": "nullable int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "rating_snapshot",
            "p2_ids": "P2-010",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].rate_snapshot",
            "transform": "nullable int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "position_x",
            "p2_ids": "P2-010,P2-018",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].position[]",
            "transform": "index 0",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "player_meta",
            "canonical_field": "position_y",
            "p2_ids": "P2-010,P2-018",
            "source_lib": "mgz.summary",
            "source_accessor": "get_players",
            "source_path": "[].position[]",
            "transform": "index 1",
            "status_target": "direct",
            "notes": "",
        },
        # RawEvent / P2-003/P2-011..P2-018
        {
            "canonical_entity": "raw_event",
            "canonical_field": "event_id",
            "p2_ids": "P2-003",
            "source_lib": "mgz.model",
            "source_accessor": "enumerate(match.actions)",
            "source_path": "actions[idx]",
            "transform": "idx",
            "status_target": "derivable",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "match_id",
            "p2_ids": "P2-003",
            "source_lib": "local",
            "source_accessor": "from replay path",
            "source_path": "<path>.stem",
            "transform": "identity",
            "status_target": "derivable",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "t_ms",
            "p2_ids": "P2-003,P2-005",
            "source_lib": "mgz.model",
            "source_accessor": "action.timestamp",
            "source_path": "actions[].timestamp",
            "transform": "seconds*1000",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "time_sec",
            "p2_ids": "P2-005",
            "source_lib": "mgz.model",
            "source_accessor": "action.timestamp",
            "source_path": "actions[].timestamp",
            "transform": "total_seconds",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "player_id",
            "p2_ids": "P2-003,P2-010",
            "source_lib": "mgz.model",
            "source_accessor": "action.player.number",
            "source_path": "actions[].player.number",
            "transform": "int",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "action_type",
            "p2_ids": "P2-003,P2-021",
            "source_lib": "mgz.model",
            "source_accessor": "action.type.name",
            "source_path": "actions[].type.name",
            "transform": "str",
            "status_target": "direct",
            "notes": "Desconocidos se preservan",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "action_family",
            "p2_ids": "P2-003",
            "source_lib": "local",
            "source_accessor": "_action_family(action_type)",
            "source_path": "derived",
            "transform": "lookup",
            "status_target": "derivable",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "x",
            "p2_ids": "P2-018",
            "source_lib": "mgz.model",
            "source_accessor": "action.position.x",
            "source_path": "actions[].position.x",
            "transform": "float|NaN",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "y",
            "p2_ids": "P2-018",
            "source_lib": "mgz.model",
            "source_accessor": "action.position.y",
            "source_path": "actions[].position.y",
            "transform": "float|NaN",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "payload_json",
            "p2_ids": "P2-003,P2-021",
            "source_lib": "mgz.model",
            "source_accessor": "action.payload",
            "source_path": "actions[].payload",
            "transform": "json.dumps",
            "status_target": "direct",
            "notes": "",
        },
        {
            "canonical_entity": "raw_event",
            "canonical_field": "event_type_semantic",
            "p2_ids": "P2-011,P2-012,P2-013,P2-014,P2-015,P2-016,P2-017",
            "source_lib": "local",
            "source_accessor": "rule engine from action_type+payload",
            "source_path": "derived",
            "transform": "classifier",
            "status_target": "derivable",
            "notes": "Baseline heuristico implementado; falta cierre de taxonomia final",
        },
        # ID mapping / P2-019
        {
            "canonical_entity": "id_mapping",
            "canonical_field": "unit_id_to_name",
            "p2_ids": "P2-019,P2-020",
            "source_lib": "mgz payload",
            "source_accessor": "payload unit/building/technology identifiers",
            "source_path": "actions[].payload.*",
            "transform": "dictionary by patch",
            "status_target": "derivable",
            "notes": "Baseline replay-derivado implementado con patch_version; falta consolidacion global por patch",
        },
    ]


def build_matrix(inventory_path: Path) -> list[dict[str, str]]:
    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    for row in _rows():
        availability = "n/a"
        if row["source_lib"] == "mgz.summary":
            accessor = row["source_accessor"].split("+")[0]
            path = row["source_path"]
            if "+" in row["source_accessor"] or "+" in row["source_path"]:
                availability = "partial"
            elif _has_path(inv, accessor, path):
                availability = "present"
            else:
                availability = "missing"
        elif row["source_lib"] == "mgz.fast":
            post_paths = inv["part2"]["P2-002_mgz_fast_inventory"]["postgame"]["paths"]
            availability = "present" if row["source_path"] in post_paths else "missing"
        out.append({
            **row,
            "availability_sample_replay": availability,
        })
    return out


def write_csv(rows: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "canonical_entity",
        "canonical_field",
        "p2_ids",
        "source_lib",
        "source_accessor",
        "source_path",
        "transform",
        "status_target",
        "availability_sample_replay",
        "notes",
    ]
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows: list[dict[str, str]], out: Path, inventory_path: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    by_status: dict[str, int] = {}
    by_avail: dict[str, int] = {}
    for r in rows:
        by_status[r["status_target"]] = by_status.get(r["status_target"], 0) + 1
        by_avail[r["availability_sample_replay"]] = by_avail.get(r["availability_sample_replay"], 0) + 1

    lines: list[str] = []
    lines.append("# Parte 2 - Matriz de mapeo mgz -> canonico")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Fuente de inventario: `{inventory_path}`")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Filas totales: `{total}`")
    for k in sorted(by_status):
        lines.append(f"- status `{k}`: `{by_status[k]}`")
    for k in sorted(by_avail):
        lines.append(f"- availability muestra `{k}`: `{by_avail[k]}`")

    lines.append("")
    lines.append("## Gaps prioritarios (impacto Parte 2)")
    lines.append("")
    for r in rows:
        if r["status_target"] == "gap":
            lines.append(f"- `{r['canonical_entity']}.{r['canonical_field']}` ({r['p2_ids']}): {r['notes']}")

    lines.append("")
    lines.append("## Campos con fuente directa confirmada en muestra")
    lines.append("")
    for r in rows:
        if r["availability_sample_replay"] == "present" and r["status_target"] in {"direct", "derivable"}:
            lines.append(
                f"- `{r['canonical_entity']}.{r['canonical_field']}` <- `{r['source_lib']}::{r['source_accessor']}::{r['source_path']}`"
            )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Part 2 mapping matrix (mgz -> canonical fields)")
    parser.add_argument("--inventory", default="reports/p2_inventory_mgz_sample_396581946.json")
    parser.add_argument("--out-csv", default="reports/p2_mapping_matrix.csv")
    parser.add_argument("--out-md", default="reports/P2_MAPEO_CANONICO.md")
    args = parser.parse_args()

    inv = Path(args.inventory)
    if not inv.exists():
        raise SystemExit(f"Inventory file not found: {inv}")

    rows = build_matrix(inv)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    write_csv(rows, out_csv)
    write_md(rows, out_md, inv)

    print(json.dumps({
        "inventory": str(inv),
        "out_csv": str(out_csv),
        "out_md": str(out_md),
        "rows": len(rows),
        "status_counts": {
            "direct": sum(1 for r in rows if r["status_target"] == "direct"),
            "derivable": sum(1 for r in rows if r["status_target"] == "derivable"),
            "gap": sum(1 for r in rows if r["status_target"] == "gap"),
        },
    }, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
