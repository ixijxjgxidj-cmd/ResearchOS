---
name: memory-write
description: Record high-value scientific research knowledge, decisions, observations, hypotheses, negative results, or references to ResearchOS Universal Memory.
---

# memory-write Skill

Use this skill whenever an agent achieves a finding, makes an architectural decision, validates or refutes a hypothesis, discovers an important pitfall, or needs to link external artifacts.

## Usage Guidelines

1. **Classify Memory Type**:
   - `knowledge`: Validated concepts, methods, formulas.
   - `decision`: Architectural/methodological choices with rationales.
   - `hypothesis`: Assumptions and testable propositions.
   - `observation`: Empirical results, metric summaries, benchmarking data.
   - `negative`: Failed attempts, invalid configurations, non-reproducible paths.
   - `reference`: Papers, repositories, external datasets.
   - `handoff`: Shift handoff notes.

2. **Call MCP Tool**:
   ```json
   {
     "tool": "memory_add",
     "arguments": {
       "project_id": "my-project",
       "type": "observation",
       "title": "Sub-sampling improves training speed by 3x without accuracy loss",
       "content": "Full experimental details and metric comparisons...",
       "tags": ["performance", "training"],
       "source_agent": "codex",
       "source_skill": "training-skill",
       "source_ref": "exp-run-042",
       "confidence": 0.95
     }
   }
   ```

3. **Or CLI Command**:
   ```bash
   researchos memory add my-project --type observation --title "..." --content "..." --tag performance
   ```
