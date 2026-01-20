from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st


DEFAULT_DB_RELATIVE = Path("data") / "portal.db"


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    description: str
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class Artifact:
    id: str
    project_id: str
    type: str
    title: str
    content_json: Optional[Dict[str, Any]]
    content_text: str
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float


def _db_path() -> Path:
    env = os.getenv("PORTAL_DB_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / DEFAULT_DB_RELATIVE


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content_json TEXT,
            content_text TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id, created_at);")
    conn.commit()


def _row_to_project(r: sqlite3.Row) -> Project:
    return Project(
        id=str(r["id"]),
        name=str(r["name"]),
        description=str(r["description"] or ""),
        created_at=float(r["created_at"]),
        updated_at=float(r["updated_at"]),
    )


def _row_to_artifact(r: sqlite3.Row) -> Artifact:
    cj = r["content_json"]
    mj = r["metadata_json"]
    return Artifact(
        id=str(r["id"]),
        project_id=str(r["project_id"]),
        type=str(r["type"]),
        title=str(r["title"]),
        content_json=json.loads(cj) if cj else None,
        content_text=str(r["content_text"] or ""),
        metadata=json.loads(mj) if mj else {},
        created_at=float(r["created_at"]),
        updated_at=float(r["updated_at"]),
    )


def create_project(name: str, description: str = "") -> Project:
    conn = get_conn()
    pid = uuid.uuid4().hex
    now = time.time()
    conn.execute(
        "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (pid, name.strip() or "Untitled", description.strip(), now, now),
    )
    conn.commit()
    return get_project(pid)


def list_projects() -> List[Project]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    return [_row_to_project(r) for r in rows]


def get_project(project_id: str) -> Project:
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        raise KeyError(f"Project not found: {project_id}")
    return _row_to_project(row)


def touch_project(project_id: str) -> None:
    conn = get_conn()
    now = time.time()
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
    conn.commit()


def save_artifact(
    project_id: str,
    type: str,
    title: str,
    content_json: Optional[Dict[str, Any]] = None,
    content_text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Artifact:
    conn = get_conn()
    aid = uuid.uuid4().hex
    now = time.time()
    conn.execute(
        """
        INSERT INTO artifacts (id, project_id, type, title, content_json, content_text, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            aid,
            project_id,
            type,
            title.strip() or type,
            json.dumps(content_json, ensure_ascii=False) if content_json is not None else None,
            content_text or "",
            json.dumps(metadata or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    touch_project(project_id)
    return get_artifact(aid)


def update_artifact_text(artifact_id: str, content_text: str) -> None:
    conn = get_conn()
    now = time.time()
    conn.execute(
        "UPDATE artifacts SET content_text = ?, updated_at = ? WHERE id = ?",
        (content_text, now, artifact_id),
    )
    conn.commit()


def list_artifacts(project_id: str, type: Optional[str] = None, limit: int = 200) -> List[Artifact]:
    conn = get_conn()
    if type:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE project_id = ? AND type = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    return [_row_to_artifact(r) for r in rows]


def get_artifact(artifact_id: str) -> Artifact:
    conn = get_conn()
    row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        raise KeyError(f"Artifact not found: {artifact_id}")
    return _row_to_artifact(row)


def latest_artifact(project_id: str, type: str) -> Optional[Artifact]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM artifacts WHERE project_id = ? AND type = ? ORDER BY created_at DESC LIMIT 1",
        (project_id, type),
    ).fetchone()
    return _row_to_artifact(row) if row else None


def set_current_project(project_id: str) -> None:
    st.session_state["current_project_id"] = project_id


def get_current_project_id() -> Optional[str]:
    return st.session_state.get("current_project_id")

