# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AP Statistics educational content repository that provides video links, worksheets, and Blooket quiz games organized by unit and topic. The project appears to be a comprehensive resource for AP Statistics curriculum delivery.

## Repository Structure

- **`/data`** - Contains unit-specific JSON files (unit1.json through unit9.json) and JavaScript files for curriculum data
  - `units.js` - Consolidated unit data with topics, video links, and Blooket references
  - `curriculum.js` - Large curriculum data file (>1.6MB)
  - `chart_questions.js` - Chart question definitions with hints

- **`/u2l5`** - Contains framework documentation for specific lessons
  - `framework.md` - Teaching framework for Unit 2, Topic 2.5 (Correlation)

## Multi-Agent Coordination

This project uses **MCP Agent Mail** and **bd (beads)** for multi-agent coordination and task tracking:

### Agent Mail Setup
- **Project Key**: Use the absolute path of this repository as `project_key` when registering agents
- **File Reservations**: Reserve files before editing with `file_reservation_paths` to avoid conflicts
- **Thread IDs**: Use beads issue IDs (e.g., `bd-123`) as thread identifiers for related discussions

### Issue Tracking with bd
```bash
# Check ready work
./bd.exe ready --json

# Create new issues
./bd.exe create "Issue title" -t bug|feature|task -p 0-4 --json

# Update status
./bd.exe update bd-42 --status in_progress --json

# Close completed work
./bd.exe close bd-42 --reason "Completed" --json
```

**Important**: Always use `--json` flag for programmatic use. Issues are stored in `.beads/issues.jsonl`.

## Development Commands

### Working with beads (bd)
The project uses a local `bd.exe` executable for issue tracking:
```bash
# View all issues
./bd.exe show:all --json

# Check for ready work (unblocked issues)
./bd.exe ready --json

# Show specific issue
./bd.exe show:bd-123 --json
```

### MCP Server Configuration
The project has MCP configuration files for different AI agents:
- `codex.mcp.json` - Codex agent configuration
- `cursor.mcp.json` - Cursor agent configuration
- `gemini.mcp.json` - Gemini agent configuration
- `.mcp.json` - General MCP configuration

## Code Architecture

### Data Model
The project uses a hierarchical structure for AP Statistics content:

1. **Units** (9 total units covering the AP Statistics curriculum)
   - Each unit has: `unitId`, `displayName`, `examWeight`, `topics[]`

2. **Topics** (lessons within each unit)
   - Each topic has: `id`, `name`, `description`, `videos[]`, `blookets[]`, `pdfs[]`

3. **Resources**
   - **Videos**: Primary AP Classroom URLs with backup Google Drive links
   - **Blookets**: Interactive quiz games for topic review
   - **PDFs**: Worksheet materials (referenced but not stored in repo)

### Key Data Files
- **`data/units.js`**: Master curriculum structure with all 9 units
- **Individual unit JSONs**: Detailed data for each unit (unit1.json - unit9.json)
- **`data/chart_questions.js`**: Chart-based question configurations

## Working with Educational Content

When modifying curriculum data:
1. The main source of truth is `data/units.js`
2. Individual unit JSON files contain more detailed information
3. Video links have both primary (`url`) and alternative (`altUrl`) sources
4. Blooket games are optional per topic and include dashboard links

## Agent Coordination Workflow

For multi-agent development:
1. Register your agent: `register_agent(project_key, agent_name, ...)`
2. Reserve files before editing: `file_reservation_paths(...)`
3. Use beads issue IDs as thread IDs in messages
4. Check inbox regularly: `fetch_inbox(project_key, agent_name)`
5. Release reservations when done: `release_file_reservations(...)`

## Important Notes

- This is an educational content repository focused on AP Statistics
- The project integrates with AP Classroom and Google Drive for video content
- Blooket integration provides gamified learning experiences
- File reservations prevent concurrent editing conflicts in multi-agent scenarios
- Always commit `.beads/issues.jsonl` with code changes to keep issue state synchronized