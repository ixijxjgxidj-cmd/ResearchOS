"""Always-on Project Memory service managing <project_id>/MEMORY.md.

Synthesizes a lightweight, generated context snapshot (L0 memory)
composed of Stable Memory and Working Memory within a strict token budget (400-800 tokens).
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from researchos.core.context_builder import estimate_tokens
from researchos.core.project_service import SUBDIRS, ProjectService
from researchos.core.storage_service import (
    atomic_write_text,
    dump_frontmatter,
    file_lock,
    parse_frontmatter,
)
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    ProjectMemoryFrontmatter,
    utc_now,
)
from researchos.utils.exceptions import ProjectNotFoundError, ValidationError
from researchos.utils.sanitizer import sanitize_markdown_text

# Regex to match Memory IDs cited in text: legacy (MEM-2026-0001) or prefix format (DEC-001, OBS-001, etc.)
MEM_ID_REGEX = re.compile(
    r"\b(MEM-\d{4}-\d{3,}|(?:DEC|OBS|NEG|HYP|REF|KNO|HAN)-\d{3,})\b"
)

# Standard v3 sections
V3_MEMORY_SECTIONS = [
    "STABLE MEMORY",
    "WORKING MEMORY",
    "CRITICAL WARNINGS",
    "MEMORY POINTERS",
]

# Legacy v2 sections for backwards compatibility validation
LEGACY_MEMORY_SECTIONS = [
    "Project Identity",
    "Core Research Idea",
    "Confirmed Findings",
    "Current Hypotheses",
    "Important Decisions",
    "Current Research Status",
    "Paper Structure",
    "Important Memory Pointers",
    "Next Actions",
    "Important Warnings",
]


class ProjectMemoryService:
    """Manages the Always-on Project Memory (<project_id>/MEMORY.md)."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)

    def get_memory_file(self, project_id: str) -> Path:
        """Returns the path to MEMORY.md inside the target project."""
        p_dir = self.project_svc.get_project_dir(project_id)
        return p_dir / "MEMORY.md"

    def get_project_memory(self, project_id: str) -> str:
        """Retrieves MEMORY.md content. If missing, automatically rebuilds it."""
        mem_file = self.get_memory_file(project_id)
        if not mem_file.exists():
            return self.rebuild_project_memory(project_id)
        return mem_file.read_text(encoding="utf-8")

    def _get_next_memory_version(self, project_id: str) -> int:
        """Atomically retrieves and increments the project's memory_version."""
        p_dir = self.project_svc.get_project_dir(project_id)
        meta_dir = p_dir / ".researchos"
        meta_dir.mkdir(parents=True, exist_ok=True)
        state_file = meta_dir / "state.json"
        lock_file = meta_dir / "memory_md.lock"

        with file_lock(lock_file, timeout=10.0):
            current_ver = 0
            if state_file.exists():
                try:
                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    current_ver = int(data.get("memory_version", 0))
                except Exception:
                    current_ver = 0

            next_ver = current_ver + 1
            payload = {
                "memory_version": next_ver,
                "last_refreshed": utc_now().isoformat(),
            }
            atomic_write_text(state_file, json.dumps(payload, indent=2))
            return next_ver

    def is_memory_stale(self, project_id: str) -> bool:
        """Checks if MEMORY.md is missing, corrupted, or older than authoritative files."""
        mem_file = self.get_memory_file(project_id)
        if not mem_file.exists():
            return True

        try:
            content = mem_file.read_text(encoding="utf-8")
            if not content.strip():
                return True
            meta, _ = parse_frontmatter(content)
            if not meta or "generated_at" not in meta:
                return True

            gen_val = meta["generated_at"]
            if isinstance(gen_val, datetime):
                gen_dt = gen_val
            else:
                gen_dt = datetime.fromisoformat(str(gen_val).replace("Z", "+00:00"))

            p_dir = self.project_svc.get_project_dir(project_id)
            for rel in ("PROJECT.md", "STATE.md", "HANDOFF.md"):
                auth_f = p_dir / rel
                if auth_f.exists():
                    f_mtime = datetime.fromtimestamp(auth_f.stat().st_mtime, tz=UTC)
                    if f_mtime > gen_dt:
                        return True
            return False
        except Exception:
            return True

    def refresh_project_memory_if_stale(self, project_id: str) -> str:
        """Re-synthesizes MEMORY.md if it is stale or missing, otherwise returns current."""
        if self.is_memory_stale(project_id):
            return self.rebuild_project_memory(project_id, preserve_custom_notes=True)
        return self.get_project_memory(project_id)

    def update_project_memory(
        self,
        project_id: str,
        content: str,
        reason: str | None = None,
    ) -> str:
        """Atomically updates MEMORY.md with concurrency locking and secret sanitization."""
        if not content or not content.strip():
            raise ValidationError("MEMORY.md content cannot be empty.")

        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mem_file = self.get_memory_file(project_id)
        lock_path = p_dir / ".researchos" / "memory_md.lock"

        clean_text = sanitize_markdown_text(content.strip())
        now = utc_now().isoformat()

        # Update or inject timestamp header
        if "*Last Updated:" in clean_text:
            clean_text = re.sub(
                r"\*Last Updated: [^\*]+\*",
                f"*Last Updated: {now}*",
                clean_text,
                count=1,
            )
        elif not clean_text.startswith("---"):
            clean_text = f"*Last Updated: {now}*\n\n{clean_text}"

        with file_lock(lock_path, timeout=10.0):
            if mem_file.exists():
                try:
                    bak_file = mem_file.with_name("MEMORY.md.bak")
                    atomic_write_text(bak_file, mem_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            atomic_write_text(mem_file, clean_text)
            self.project_svc.touch_project(project_id)

        return clean_text

    def validate_project_memory(self, project_id: str) -> dict[str, Any]:
        """Validates MEMORY.md against required sections, cited memory IDs, and token budget."""
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mem_file = self.get_memory_file(project_id)
        if not mem_file.exists():
            return {
                "project_id": project_id,
                "valid": False,
                "errors": [f"MEMORY.md does not exist for project '{project_id}'."],
                "warnings": [],
                "sections_found": [],
                "missing_sections": list(V3_MEMORY_SECTIONS),
                "cited_memory_ids": [],
                "missing_cited_ids": [],
                "estimated_tokens": 0,
                "within_budget": False,
            }

        content = mem_file.read_text(encoding="utf-8")
        tokens = estimate_tokens(content)

        errors: list[str] = []
        warnings: list[str] = []

        # Determine section standard: v3 standard or legacy v2
        is_v3 = "STABLE MEMORY" in content or "## 1. STABLE MEMORY" in content
        target_sections = V3_MEMORY_SECTIONS if is_v3 else LEGACY_MEMORY_SECTIONS

        sections_found: list[str] = []
        missing_sections: list[str] = []

        for req in target_sections:
            pattern = re.compile(rf"##\s*(\d+\.\s*)?{re.escape(req)}", re.IGNORECASE)
            if pattern.search(content):
                sections_found.append(req)
            else:
                missing_sections.append(req)

        # Allow flexible section matching if user customizes
        if missing_sections and not is_v3:
            # Check if at least core sections exist
            if "Project Identity" in sections_found:
                pass
            else:
                errors.append(f"Missing required sections: {missing_sections}")
        elif missing_sections and is_v3:
            errors.append(f"Missing required sections: {missing_sections}")

        # Cited Memory IDs
        cited_ids = list(dict.fromkeys(MEM_ID_REGEX.findall(content)))
        missing_cited_ids: list[str] = []
        for mid in cited_ids:
            if not self._memory_exists_on_disk(p_dir, mid):
                missing_cited_ids.append(mid)

        if missing_cited_ids:
            warnings.append(f"Cited Memory IDs not found in project store: {missing_cited_ids}")

        # Budget verification
        within_budget = tokens <= 2500  # Hard ceiling
        if tokens > 1200:
            warnings.append(
                f"MEMORY.md token count ({tokens}) exceeds recommended budget of 800-1200 tokens."
            )

        valid = len(errors) == 0

        return {
            "project_id": project_id,
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "sections_found": sections_found,
            "missing_sections": missing_sections,
            "cited_memory_ids": cited_ids,
            "missing_cited_ids": missing_cited_ids,
            "estimated_tokens": tokens,
            "within_budget": within_budget,
        }

    def _memory_exists_on_disk(self, project_dir: Path, memory_id: str) -> bool:
        """Checks if a memory ID exists in records or subdirectories."""
        clean_id = memory_id.strip()
        for sub in SUBDIRS:
            folder = project_dir / sub
            if not folder.exists():
                continue
            if (folder / f"{clean_id}.md").exists():
                return True
            if list(folder.glob(f"{clean_id}*.md")):
                return True
        return False

    @staticmethod
    def _parse_existing_sections(content: str) -> dict[str, str]:
        """Parses markdown content into section title -> section body."""
        sections: dict[str, str] = {}
        current_title: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines():
            m = re.match(r"^#{1,3}\s*(?:\d+\.\s*)?([^\n#]+)", line)
            if m:
                if current_title:
                    sections[current_title] = "\n".join(current_lines).strip()
                current_title = m.group(1).strip()
                current_lines = []
            elif current_title is not None:
                current_lines.append(line)

        if current_title:
            sections[current_title] = "\n".join(current_lines).strip()

        return sections

    @staticmethod
    def _find_section_content(
        sections: dict[str, str], canonical_name: str
    ) -> str | None:
        """Finds section content matching canonical name case-insensitively."""
        c_norm = canonical_name.lower().strip()
        for key, val in sections.items():
            k_norm = key.lower().strip()
            if c_norm in k_norm or k_norm in c_norm:
                return val
        return None

    def _extract_text_under_header(self, content: str, header_regex: str) -> list[str]:
        """Extracts bullet lines under a specific markdown header."""
        lines = []
        found = False
        pat = re.compile(header_regex, re.IGNORECASE)
        for line in content.splitlines():
            if pat.search(line):
                found = True
                continue
            if found:
                if line.startswith("#"):
                    break
                s = line.strip()
                if s and (s.startswith("-") or re.match(r"^\d+\.", s)):
                    lines.append(s)
        return lines

    def rebuild_project_memory(
        self,
        project_id: str,
        max_tokens: int = 1000,
        preserve_custom_notes: bool = True,
    ) -> str:
        """Deterministically synthesizes MEMORY.md from authoritative state and records.

        Generated standard structure:
            - Frontmatter (schema_version: 1, project_id, generated_at, memory_version)
            - 1. STABLE MEMORY (Project Identity, Fixed Constraints, Key Decisions)
            - 2. WORKING MEMORY (Current Stage, Current Task, Last Completed Work, Next Actions, Current Blockers, Open Questions)
            - 3. CRITICAL WARNINGS
            - 4. MEMORY POINTERS
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        proj = self.project_svc.get_project(project_id)
        mem_file = self.get_memory_file(project_id)

        # 0. Backup existing MEMORY.md and extract custom notes if requested
        existing_sections: dict[str, str] = {}
        old_raw_content = ""
        custom_notes_block: str | None = None
        if mem_file.exists():
            try:
                old_raw_content = mem_file.read_text(encoding="utf-8")
                # Immediate backup
                bak_file = mem_file.with_name("MEMORY.md.bak")
                atomic_write_text(bak_file, old_raw_content)

                # Timestamped backup in .researchos/backups/
                backups_dir = p_dir / ".researchos" / "backups"
                backups_dir.mkdir(parents=True, exist_ok=True)
                ts = utc_now().strftime("%Y%m%d_%H%M%S")
                atomic_write_text(backups_dir / f"MEMORY_{ts}.md", old_raw_content)

                if preserve_custom_notes:
                    existing_sections = self._parse_existing_sections(old_raw_content)
                    m = re.search(
                        r"(<!-- RESEARCHOS_CUSTOM_NOTES_START -->.*?<!-- RESEARCHOS_CUSTOM_NOTES_END -->)",
                        old_raw_content,
                        re.DOTALL,
                    )
                    if m:
                        custom_notes_block = m.group(1).strip()
                    elif "custom notes" in [k.lower() for k in existing_sections.keys()]:
                        custom_body = self._find_section_content(existing_sections, "Custom Notes")
                        if custom_body:
                            custom_notes_block = f"### Custom Notes\n{custom_body}"
            except Exception:
                existing_sections = {}

        # 1. Load active project memories
        all_memories = self._load_project_memories(project_id)
        active_mems = [
            m for m in all_memories
            if (m.status == MemoryStatus.ACTIVE or getattr(m.status, "value", str(m.status)) in ("active", "verified"))
        ]

        negatives = [m for m in active_mems if m.type == MemoryType.NEGATIVE]
        decisions = [m for m in active_mems if m.type == MemoryType.DECISION]
        observations = [m for m in active_mems if m.type == MemoryType.OBSERVATION]

        # 2. Extract Authoritative Info
        # A. Stable Memory: PROJECT.md
        proj_root_rel = f"ResearchVault/{project_id}"
        core_research_question = proj.frontmatter.research_goal or "Advance research objectives."
        target_venue = "_Not yet established_"
        proj_file = p_dir / "PROJECT.md"
        fixed_constraints: list[str] = []
        if proj_file.exists():
            proj_text = proj_file.read_text(encoding="utf-8")
            constraints_lines = self._extract_text_under_header(proj_text, r"##\s*(Fixed\s+)?Constraints")
            if constraints_lines:
                fixed_constraints.extend(constraints_lines)

        # Check existing custom constraints / venue / notes
        custom_stable_notes: list[str] = []
        sec1_text = self._find_section_content(existing_sections, "Project Identity")
        if sec1_text:
            m_ven = re.search(r"-\s*(\*\*)?Target Publication Venue(\*\*)?:\s*([^\n]+)", sec1_text, re.IGNORECASE)
            if m_ven and "_Not yet established_" not in m_ven.group(3):
                target_venue = m_ven.group(3).strip()

            for line in sec1_text.splitlines():
                sline = line.strip()
                if not sline:
                    continue
                if any(
                    sline.startswith(prefix)
                    for prefix in [
                        "- Project:",
                        "- Research Goal:",
                        "- Core Research Question:",
                        "- Target Publication Venue:",
                        "- Project Root:",
                        "- **Research Topic**:",
                        "- **Core Goal**:",
                        "- **Description**:",
                        "- **Target Publication Venue**:",
                    ]
                ):
                    continue
                custom_stable_notes.append(sline)

        # Preserve custom notes from legacy section 2
        sec2_text = self._find_section_content(existing_sections, "Core Research Idea")
        if sec2_text:
            for line in sec2_text.splitlines():
                sline = line.strip()
                if not sline or "_Not yet established_" in sline:
                    continue
                if sline == f"- {proj.frontmatter.description}":
                    continue
                custom_stable_notes.append(sline)

        # Key Decisions from active records + custom
        key_decision_lines: list[str] = []
        for dec in decisions[-5:]:
            key_decision_lines.append(f"- {dec.id}: {dec.title}")
        sec5_text = self._find_section_content(existing_sections, "Important Decisions") or self._find_section_content(existing_sections, "Key Decisions")
        if sec5_text:
            for line in sec5_text.splitlines():
                sline = line.strip()
                if sline and not sline.startswith("- _No major") and not any(dec.id in sline for dec in decisions):
                    key_decision_lines.append(sline)

        # B. Working Memory: STATE.md & HANDOFF.md
        current_stage = proj.frontmatter.status or "Active investigation."
        current_task = "Active research tasks."
        completed_work: list[str] = []
        next_actions: list[str] = []
        current_blockers: list[str] = []
        open_questions: list[str] = []

        # Read STATE.md
        state_file = p_dir / "STATE.md"
        if state_file.exists():
            state_text = state_file.read_text(encoding="utf-8")
            stage_lines = self._extract_text_under_header(state_text, r"##\s*3\.\s*当前研究进展") or self._extract_text_under_header(state_text, r"##\s*Current\s+Progress")
            if stage_lines:
                current_stage = stage_lines[0].lstrip("- *").strip()
            blocker_lines = self._extract_text_under_header(state_text, r"##\s*5\.\s*尚未解决的问题") or self._extract_text_under_header(state_text, r"##\s*Current\s+Blockers")
            for bl in blocker_lines:
                if "_None" not in bl and bl.strip() != "-":
                    current_blockers.append(bl.lstrip("- *").strip())
            q_lines = self._extract_text_under_header(state_text, r"##\s*4\.\s*当前重要问题") or self._extract_text_under_header(state_text, r"##\s*Key\s+Questions")
            for ql in q_lines:
                if "_No" not in ql and ql.strip() != "-":
                    open_questions.append(ql.lstrip("- *").strip())
            next_lines = self._extract_text_under_header(state_text, r"##\s*7\.\s*下一步关注事项") or self._extract_text_under_header(state_text, r"##\s*Next\s+Focus")
            if next_lines:
                next_actions.extend([nl.lstrip("0123456789.- *").strip() for nl in next_lines])

        # Read HANDOFF.md
        handoff_file = p_dir / "HANDOFF.md"
        if handoff_file.exists():
            handoff_text = handoff_file.read_text(encoding="utf-8")
            t_lines = self._extract_text_under_header(handoff_text, r"##\s*Current\s+Task")
            if t_lines:
                current_task = t_lines[0].lstrip("- *").strip()
            c_lines = self._extract_text_under_header(handoff_text, r"##\s*Completed\s+Work")
            if c_lines:
                completed_work = [cl.lstrip("- *").strip() for cl in c_lines if "_None" not in cl]
            n_lines = self._extract_text_under_header(handoff_text, r"##\s*Next\s+Steps")
            if n_lines:
                next_actions = [nl.lstrip("0123456789.- *").strip() for nl in n_lines if "_None" not in nl]
            i_lines = self._extract_text_under_header(handoff_text, r"##\s*Issues")
            for il in i_lines:
                if "_None" not in il and il.strip() != "-":
                    current_blockers.append(il.lstrip("- *").strip())

        # Check existing custom status/action notes
        custom_working_notes: list[str] = []
        sec6_text = (
            self._find_section_content(existing_sections, "Current Research Status")
            or self._find_section_content(existing_sections, "Current Blockers")
            or self._find_section_content(existing_sections, "WORKING MEMORY")
        )
        if sec6_text:
            for line in sec6_text.splitlines():
                sline = line.strip()
                if (
                    sline
                    and not sline.startswith("- **State Source**")
                    and not sline.startswith("- **Total Active Memories**")
                    and sline != "- Project initialized; initial baseline phase."
                    and sline != "- None recorded."
                    and not sline.startswith("#")
                ):
                    if "blocker" in sline.lower() or "exhaustion" in sline.lower():
                        if sline not in current_blockers:
                            current_blockers.append(sline.lstrip("- *").strip())
                    elif "milestone" in sline.lower() or "pipeline" in sline.lower():
                        custom_working_notes.append(sline.lstrip("- *").strip())
                    else:
                        custom_stable_notes.append(sline)

        sec9_text = self._find_section_content(existing_sections, "Next Actions")
        if sec9_text:
            for line in sec9_text.splitlines():
                sline = line.strip()
                if sline and not sline.startswith("1. Review existing") and not sline.startswith("2. Execute validation"):
                    act = sline.lstrip("0123456789.- *").strip()
                    if act and act not in next_actions:
                        next_actions.append(act)

        # C. Critical Warnings
        critical_warnings: list[str] = []
        for neg in negatives[-4:]:
            critical_warnings.append(f"- [WARNING] {neg.id}: {neg.title}")

        sec10_text = self._find_section_content(existing_sections, "Important Warnings") or self._find_section_content(existing_sections, "Critical Warnings")
        if sec10_text:
            for line in sec10_text.splitlines():
                sline = line.strip()
                if not sline or "_No critical" in sline:
                    continue
                if not any(neg.id in sline for neg in negatives):
                    if not sline.startswith("-"):
                        sline = f"- {sline}"
                    if "[WARNING]" not in sline:
                        sline = sline.replace("- ", "- [WARNING] ")
                    critical_warnings.append(sline)

        # Version increment
        memory_version = self._get_next_memory_version(project_id)
        now = utc_now().isoformat()

        # Build Document
        fm = ProjectMemoryFrontmatter(
            schema_version=1,
            project_id=project_id,
            generated_at=utc_now(),
            memory_version=memory_version,
        )

        body_lines = [
            "# MEMORY",
            f"*Always-on Project Memory: {proj.project_name}*",
            "",
            "## 1. STABLE MEMORY",
            "",
            "### Project Identity",
            f"- Project: {proj.project_name}",
            f"- Research Goal: {proj.frontmatter.research_goal or 'Advance research objectives.'}",
            f"- Core Research Question: {core_research_question}",
            f"- Target Publication Venue: {target_venue}",
            f"- Project Root: {proj_root_rel}",
        ]
        if custom_stable_notes:
            for csn in custom_stable_notes:
                body_lines.append(f"- {csn}" if not csn.startswith("-") else csn)

        body_lines.append("")
        body_lines.append("### Fixed Constraints")
        if fixed_constraints:
            for fc in fixed_constraints:
                body_lines.append(fc if fc.startswith("-") else f"- {fc}")
        else:
            body_lines.append("- Standard zero-leakage, isolated research vault protocol.")

        body_lines.append("")
        body_lines.append("### Key Decisions")
        if key_decision_lines:
            for kdl in key_decision_lines[-5:]:
                body_lines.append(kdl if kdl.startswith("-") else f"- {kdl}")
        else:
            body_lines.append("- No architectural decisions recorded yet.")

        body_lines.append("")
        body_lines.append("## 2. WORKING MEMORY")
        body_lines.append("")
        body_lines.append("### Current Stage")
        body_lines.append(f"- {current_stage}")

        body_lines.append("")
        body_lines.append("### Current Task")
        body_lines.append(f"- {current_task}")

        body_lines.append("")
        body_lines.append("### Last Completed Work")
        if completed_work:
            for cw in completed_work[:4]:
                body_lines.append(f"- {cw}")
        else:
            body_lines.append("- Initial project workspace established.")

        if observations:
            body_lines.append("")
            body_lines.append("### Recent Findings")
            for obs in observations[-4:]:
                body_lines.append(f"- {obs.id}: {obs.title}")

        body_lines.append("")
        body_lines.append("### Next Actions")
        if next_actions:
            for idx, act in enumerate(next_actions[:5], 1):
                body_lines.append(f"{idx}. {act}")
        else:
            body_lines.append("1. Review project definition and literature.")
            body_lines.append("2. Begin recording observations, decisions, and knowledge.")

        body_lines.append("")
        body_lines.append("### Current Blockers")
        if current_blockers:
            for blk in current_blockers[:4]:
                body_lines.append(f"- {blk}")
        else:
            body_lines.append("- None recorded.")

        if custom_working_notes:
            for cwn in custom_working_notes:
                body_lines.append(f"- {cwn}")

        body_lines.append("")
        body_lines.append("### Open Questions")
        if open_questions:
            for oq in open_questions[:3]:
                body_lines.append(f"- {oq}")
        else:
            body_lines.append("- None recorded.")

        body_lines.append("")
        body_lines.append("## 3. CRITICAL WARNINGS")
        body_lines.append("")
        if critical_warnings:
            for cw in critical_warnings[:5]:
                body_lines.append(cw)
        else:
            body_lines.append("- [WARNING] No critical pitfalls recorded yet.")

        body_lines.append("")
        body_lines.append("## 4. MEMORY POINTERS")
        body_lines.append("")
        body_lines.append("- Project Definition: PROJECT.md")
        body_lines.append("- Detailed State: STATE.md")
        body_lines.append("- Latest Handoff: HANDOFF.md")
        body_lines.append("- Memory Index: INDEX.md")
        body_lines.append("- Detailed Records: records/")
        if observations:
            body_lines.append(f"- Key Observations: {', '.join(f'`{o.id}`' for o in observations[-4:])}")
        if decisions:
            body_lines.append(f"- Key Decisions: {', '.join(f'`{d.id}`' for d in decisions[-4:])}")
        if negatives:
            body_lines.append(f"- Key Pitfalls: {', '.join(f'`{n.id}`' for n in negatives[-4:])}")

        # If custom paper structure existed, retain as pointer note
        sec7_text = self._find_section_content(existing_sections, "Paper Structure")
        if sec7_text:
            body_lines.append("")
            body_lines.append("### Paper Structure Notes")
            for line in sec7_text.splitlines():
                if line.strip():
                    body_lines.append(line.strip())

        if custom_notes_block:
            body_lines.append("")
            body_lines.append(custom_notes_block)

        full_content = dump_frontmatter(fm.model_dump(mode="json"), "\n".join(body_lines))

        # Enforce budget: if tokens > 1000, prune non-critical lists
        est = estimate_tokens(full_content)
        if est > 1200:
            # Drop paper structure notes if any
            if "### Paper Structure Notes" in full_content:
                full_content = full_content.split("### Paper Structure Notes")[0].strip() + "\n"

        lock_path = p_dir / ".researchos" / "memory_md.lock"
        with file_lock(lock_path, timeout=10.0):
            atomic_write_text(mem_file, full_content)
            self.project_svc.touch_project(project_id)

        return full_content

    def _load_project_memories(self, project_id: str) -> list[Any]:
        from researchos.models.memory import Memory
        p_dir = self.project_svc.get_project_dir(project_id)
        memories = []
        for sub in SUBDIRS:
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue
            for f in sorted(sub_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(content)
                    if "id" in meta and "type" in meta:
                        fm = MemoryFrontmatter.model_validate(meta)
                        rel_path = f.relative_to(p_dir).as_posix()
                        memories.append(Memory(frontmatter=fm, content=body, file_path=rel_path))
                except Exception:
                    continue
        return memories
