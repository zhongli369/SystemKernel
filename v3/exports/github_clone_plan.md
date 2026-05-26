# SystemKernel v3.0 — GitHub Clone Plan

> **PLAN ONLY** — No actual cloning is performed by this module.
> All items require manual review before execution.

- **Root directory:** `F:\Claude\Github`
- **Plan hash:** `e38a62da69d95369`
- **Total items:** 14

## Clone Now

| Priority | Repository | Target Path | Post-Clone Action |
|----------|------------|-------------|-------------------|
| S | Anthropic Skills | `F:/Claude/Github/anthropic-skills` | extract_format_reference |
| S | Repomix | `F:/Claude/Github/repomix` | run_cli_help |
| S | ccusage | `F:/Claude/Github/ccusage` | run_cli_help |

### Anthropic Skills
- **URL:** https://github.com/anthropics/skills
- **Reason:** Format reference — clone to study file formats and conventions.
- **Post-clone:** `extract_format_reference`
- **Forbidden:** do_not_integrate_into_kernel, do_not_execute_skills_directly, do_not_embed_as_kernel_module

### Repomix
- **URL:** https://github.com/yamadashy/repomix
- **Reason:** Direct CLI tool — clone for local use. CC value=10.0/10.
- **Post-clone:** `run_cli_help`
- **Forbidden:** do_not_integrate_into_kernel, do_not_modify_kernel_boundary, do_not_embed_as_kernel_module

### ccusage
- **URL:** https://github.com/anthropics/ccusage
- **Reason:** Direct CLI tool — clone for local use. CC value=10.0/10.
- **Post-clone:** `run_cli_help`
- **Forbidden:** do_not_integrate_into_kernel, do_not_modify_kernel_boundary, do_not_embed_as_kernel_module

## Inspect Only

| Priority | Repository | Post-Clone Action |
|----------|------------|-------------------|
| S | AppFlowy | inspect_only |
| S | JupyterLab | inspect_only |
| S | SuperClaude | inspect_only |

### AppFlowy
- **URL:** https://github.com/AppFlowy-IO/appflowy
- **Reason:** Large application — inspect source code for design patterns only.
- **Forbidden:** do_not_run_as_dependency, do_not_integrate_into_kernel, do_not_modify_kernel_boundary, do_not_execute_without_review

### JupyterLab
- **URL:** https://github.com/jupyterlab/jupyterlab
- **Reason:** Large application — inspect source code for design patterns only.
- **Forbidden:** do_not_run_as_dependency, do_not_integrate_into_kernel, do_not_modify_kernel_boundary, do_not_execute_without_review

### SuperClaude
- **URL:** https://github.com/anthropics/SuperClaude
- **Reason:** Large application — inspect source code for design patterns only.
- **Forbidden:** do_not_run_as_dependency, do_not_integrate_into_kernel, do_not_modify_kernel_boundary, do_not_execute_without_review

## External Service Evaluation

| Priority | Repository | Post-Clone Action |
|----------|------------|-------------------|
| B | OpenAI Swarm | evaluate_external_service |
| C | mem0 | evaluate_external_service |
| B | Graphiti | evaluate_external_service |
| B | Continue | evaluate_external_service |

### OpenAI Swarm
- **URL:** https://github.com/openai/swarm
- **Reason:** External service — evaluate via API only. Risk=5.0/10.
- **Forbidden:** do_not_import_directly, do_not_install_locally_without_review, do_not_integrate_into_kernel, do_not_modify_kernel_boundary

### mem0
- **URL:** https://github.com/mem0ai/mem0
- **Reason:** External service — evaluate via API only. Risk=6.0/10.
- **Forbidden:** do_not_import_directly, do_not_install_locally_without_review, do_not_integrate_into_kernel, do_not_modify_kernel_boundary

### Graphiti
- **URL:** https://github.com/getzep/graphiti
- **Reason:** External service — evaluate via API only. Risk=5.0/10.
- **Forbidden:** do_not_import_directly, do_not_install_locally_without_review, do_not_integrate_into_kernel, do_not_modify_kernel_boundary

### Continue
- **URL:** https://github.com/continuedev/continue
- **Reason:** External service — evaluate via API only. Risk=5.0/10.
- **Forbidden:** do_not_import_directly, do_not_install_locally_without_review, do_not_integrate_into_kernel, do_not_modify_kernel_boundary

## Architecture Reference Only

| Priority | Repository |
|----------|------------|
| C | LangGraph |
| C | CrewAI |
| C | awesome-claude-code |
| C | Awesome-Prompt-Engineering |

### LangGraph
- **URL:** https://github.com/langchain-ai/langgraph
- **Reason:** Architecture reference only — not cloned. Study design patterns from documentation.

### CrewAI
- **URL:** https://github.com/crewAIInc/crewAI
- **Reason:** Architecture reference only — not cloned. Study design patterns from documentation.

### awesome-claude-code
- **URL:** https://github.com/anthropics/awesome-claude-code
- **Reason:** Architecture reference only — not cloned. Study design patterns from documentation.

### Awesome-Prompt-Engineering
- **URL:** https://github.com/promptslab/Awesome-Prompt-Engineering
- **Reason:** Architecture reference only — not cloned. Study design patterns from documentation.

## Safety Notes

- PLAN ONLY — no actual cloning is performed by this module.
- DIRECT_CLONE repos are external tools, NOT kernel modules.
- Large application repos (AppFlowy, JupyterLab) are inspect-only despite DIRECT_CLONE decision.
- External service repos must NOT be installed locally without review.
- Architecture reference repos are NOT cloned at all.
- All clones target F:/Claude/Github/ — outside the kernel boundary.
- No repo may be integrated into the kernel without a separate audit.
