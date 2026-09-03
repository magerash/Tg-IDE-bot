# Agents Configuration

## Quick Reference
| Shortcut | Agent | Color | Role |
|----------|-------|-------|------|
| OB | backend-orchestrator | cyan | Handler implementation, subprocess, file I/O |
| PM | product-strategy-analyst | blue | Feature planning, research, task breakdown |
| QA | qa-testing-engineer | orange | Code review, security audit, testing |
| SA | system-architect | pink | Architecture design, technical decisions |
| UI | ui-frontend-specialist | green | Telegram UX, keyboards, message formatting |

## Overview
All agents in `.claude/agents/` are tailored for this Python Telegram remote-control bot project. Each agent knows the project structure, tech stack, file limits, and Windows-specific gotchas.

## Key Context Shared Across All Agents
- **Project type**: Python TG remote-control bot on Windows
- **Tech stack**: python-telegram-bot v20+, mss, Pillow, pyautogui, pygetwindow, ctypes, subprocess
- **Structure**: `bot.py` + `config.py` + `handlers/` + `utils/`
- **Security**: `@auth_required` on every handler
- **File limits**: handler 150, utils 100, bot.py 100, config 50 lines

## Agent Responsibilities

### backend-orchestrator (OB)
- New command handler implementation
- Subprocess management (async, timeouts, encoding)
- File I/O and delivery logic
- Windows API integration (clipboard, window focus)
- Debugging handler issues

### product-strategy-analyst (PM)
- Major feature analysis and research
- Technical approach evaluation
- Task breakdown and phased planning
- Saves research to `docs/analysis/`

### qa-testing-engineer (QA)
- Handler code review and security audit
- Auth decorator verification
- Subprocess timeout/encoding checks
- File limit compliance
- Pre-release validation reports

### system-architect (SA)
- Module structure design
- Technical trade-off analysis (async vs threading, etc.)
- Handler splitting decisions
- Integration planning for new features
- Saves decisions to `docs/analysis/`

### ui-frontend-specialist (UI)
- Telegram message formatting (MarkdownV2/HTML)
- Inline keyboard design and callback handlers
- Help text and error message UX
- Command interaction patterns
- Output truncation and `.txt` file fallback

## Files
```
.claude/agents/
  backend-orchestrator.md
  product-strategy-analyst.md
  qa-testing-engineer.md
  system-architect.md
  ui-frontend-specialist.md
```
