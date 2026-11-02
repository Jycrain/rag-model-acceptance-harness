# compound/: Claude Code tooling

| Path | Kind | Purpose |
|---|---|---|
| `rag-model-acceptance/SKILL.md` | skill | the whole campaign, phase by phase, each with a gate |
| `skills/blind-audit/SKILL.md` | skill | light vs full blind audit, procedure, limits to state |
| `agents/blind-reviewer.md` | agent | judges `has_source` / `complete_answer` blind, with literal quotes |
| `agents/adversary.md` | agent | attacks the consensus after the reviewers |
| `agents/leak-reviewer.md` | agent | blind read of what would be published |
| `workflows/blind-audit.workflow.js` | workflow | batches × reviewer models, retry on missed canary, adversary per batch |
| `../prompts/*.md` | portable prompts | the same three briefs for any LLM or human (no Claude Code needed); see `../AGENTS.md` |
| `scripts/anonymize_check.py` | script | generic and private leak scan |
| `forbidden-terms.example` | example | format of the private list (the real list stays outside the repo) |

## Install (project or user level)
```
mkdir -p .claude/skills .claude/agents .claude/workflows
cp -r compound/rag-model-acceptance compound/skills/blind-audit .claude/skills/
cp compound/agents/*.md .claude/agents/
cp compound/workflows/*.js .claude/workflows/
```
Agents never commit, push or publish. The workflow reads no file: pass batches as `args`, write results to `audit/`, run `src/audit_consensus.py`.
Cost: a full run is `batches × (reviewers + 1)` agents (the script warns above 10): ask the owner first.
