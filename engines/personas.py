from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def normalize_dashes(s: str) -> str:
    return re.sub(f"[{DASH_CHARS}]", "-", s or "")


def slugify(s: str) -> str:
    s = normalize_dashes(s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _ensure_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _ensure_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


@dataclass(frozen=True)
class Persona:
    uid: str
    segment_id: str
    segment_label: str
    segment_summary: str
    persona_id: str
    gender: str
    core: Dict[str, Any]
    extended: Dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.core.get("name") or "Unknown")

    @property
    def label(self) -> str:
        # Human-friendly label for UI
        age = self.core.get("age")
        occ = self.core.get("occupation")
        bits = [self.name]
        if age:
            bits.append(f"{age}")
        if occ:
            bits.append(str(occ))
        return " - ".join(bits)


def _patch_core(core: Dict[str, Any]) -> Dict[str, Any]:
    core = dict(core or {})

    core.setdefault("income", 0)
    core.setdefault("goals", [])
    core.setdefault("values", [])
    core.setdefault("personality_traits", [])
    core.setdefault("concerns", [])
    core.setdefault("decision_making", "Unknown")

    bt = _ensure_dict(core.get("behavioural_traits"))
    bt.setdefault("risk_tolerance", "Moderate")
    bt.setdefault("investment_experience", "Unknown")
    bt.setdefault("information_sources", [])
    bt.setdefault("preferred_channels", [])
    core["behavioural_traits"] = bt

    cc = _ensure_dict(core.get("content_consumption"))
    cc.setdefault("preferred_formats", [])
    cc.setdefault("preferred_channels", [])
    cc.setdefault("additional_notes", "")
    core["content_consumption"] = cc

    return core


def _convert_old_schema(old: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy {personas:[{segment,male,female}]} into {segments:[...]}"""
    groups = _ensure_list(old.get("personas"))

    segments: List[Dict[str, Any]] = []
    for g in groups:
        label = g.get("segment", "Unknown")
        seg_id = slugify(label)

        people: List[Dict[str, Any]] = []
        for gender in ("male", "female"):
            if gender not in g:
                continue
            p = dict(g[gender] or {})
            core = {k: v for k, v in p.items() if k not in {"scenarios", "peer_influence", "risk_tolerance_differences", "behavioural_enrichment"}}
            ext = {
                "behavioural_enrichment": p.get("behavioural_enrichment", p.get("behavioral_enrichment", {})),
                "risk_tolerance_differences": p.get("risk_tolerance_differences", ""),
                "scenarios": p.get("scenarios", {}),
                "peer_influence": p.get("peer_influence", {}),
            }
            core = _patch_core(core)
            people.append({"id": slugify(p.get("name", f"{gender}_{seg_id}")), "gender": gender, "core": core, "extended": ext})

        segments.append({"id": seg_id, "label": label, "summary": "", "personas": people})

    return {"schema_version": "1.0", "segments": segments}


def _find_personas_file() -> Optional[Path]:
    here = Path(__file__).resolve().parent.parent
    candidates = [here / "personas.json", Path.cwd() / "personas.json"]
    for p in candidates:
        if p.exists() and p.is_file():
            return p

    for base in (here, Path.cwd()):
        for p in sorted(base.glob("personas*.json")):
            if p.exists() and p.is_file():
                return p

    return None


@st.cache_data
def load_personas() -> Tuple[Optional[Path], List[Dict[str, Any]], List[Persona]]:
    path = _find_personas_file()
    if path is None:
        return None, [], []

    raw = json.loads(path.read_text(encoding="utf-8"))
    if "segments" not in raw and "personas" in raw:
        raw = _convert_old_schema(raw)

    segments = _ensure_list(raw.get("segments"))

    flat: List[Persona] = []
    for seg in segments:
        seg_id = seg.get("id") or slugify(seg.get("label", ""))
        seg_label = seg.get("label", "Unknown")
        seg_summary = seg.get("summary", "")
        for persona in _ensure_list(seg.get("personas")):
            pid = persona.get("id") or slugify(_ensure_dict(persona.get("core")).get("name", ""))
            uid = f"{seg_id}:{pid}"
            core = _patch_core(_ensure_dict(persona.get("core")))
            ext = _ensure_dict(persona.get("extended"))
            flat.append(
                Persona(
                    uid=uid,
                    segment_id=seg_id,
                    segment_label=seg_label,
                    segment_summary=seg_summary,
                    persona_id=pid,
                    gender=persona.get("gender", "unknown"),
                    core=core,
                    extended=ext,
                )
            )

    return path, segments, flat


def persona_label(p: Persona) -> str:
    # Useful in format_func for selectbox
    risk = _ensure_dict(p.core.get("behavioural_traits")).get("risk_tolerance")
    return f"{p.name} ({p.segment_label}) - Risk: {risk}"
