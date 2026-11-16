# AI agents (MCP server)

`pythonfmu3 mcp` runs PythonFMU3 as an [MCP](https://modelcontextprotocol.io) server. AI
agents such as Claude (Desktop or Code), GitHub Copilot in VS Code and Cursor can then
write, check, simulate and build FMUs for you.

The agent doesn't just write code: it runs the same checks and simulations as
[PythonFMU3 Studio](studio.md), reads the results and fixes what's wrong before it builds
the FMU.

## Install

The server needs Python 3.10 or later:

```bash
pip install "pythonfmu3[mcp]"
```

This adds the `mcp` package. Building FMUs needs
PythonFMU3's native library for your platform, as for any FMU build (see
[Installation](install.md)).

## Connect an agent

The server takes a workspace folder, where it reads and writes models:

```bash
pythonfmu3 mcp ~/fmu-models
```

You don't run this yourself: the agent starts it. Use the full path to `pythonfmu3`
(`which pythonfmu3` in your virtual environment) if the agent doesn't find it.

### Claude Desktop

In `claude_desktop_config.json` (**Settings → Developer → Edit Config**):

```json
{
  "mcpServers": {
    "pythonfmu3": {
      "command": "/path/to/.venv/bin/pythonfmu3",
      "args": ["mcp", "/Users/you/fmu-models""]
    }
  }
}
```

### Claude Code

```bash
claude mcp add pythonfmu3 -- /path/to/.venv/bin/pythonfmu3 mcp /Users/you/fmu-models
```

### VS Code (GitHub Copilot)

In `.vscode/mcp.json`, then use Copilot Chat in agent mode:

```json
{
  "servers": {
    "pythonfmu3": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/pythonfmu3",
      "args": ["mcp", "${workspaceFolder}/models"]
    }
  }
}
```

Other MCP clients work the same way: the command is `pythonfmu3`, the arguments are
`mcp <folder>`, and the transport is stdio.

## What the agent can do

| Tool | What it does |
| --- | --- |
| `get_guide` | How to write PythonFMU3 models, and the recommended workflow |
| `list_files`, `read_file` | See the models, FMUs and results in the workspace |
| `write_model` | Save a whole model and return its checks |
| `edit_model` | Replace part of a model (much cheaper than rewriting it) and return its checks |
| `copy_template` | Start a model from a template |
| `run_checks` | The Studio's checks: variables, causality, settable inputs, the model description |
| `simulate` | Run the model (Python preview, or the built FMU in fmusim or FMPy) and summarise its outputs (or chosen variables); the full result is saved as CSV in `results/` |
| `build_fmu` | Build the FMU into `build/` |
| `inspect_fmu`, `validate_fmu` | Describe or validate any FMU |
| `list_templates`, `read_template` | Working example models, for reference |

Try asking:

- "Write a Co-Simulation FMU of a water tank with an inflow input and a drain valve, check
  it and simulate it for 100 s."
- "Fix the problems in `controller.py`."
- "Make me a bouncing ball and simulate it for 5 s."

## Keeping it quick and cheap

The tools are designed to keep what the agent reads and writes small: changes go through
`edit_model` instead of rewriting files, templates are copied rather than retyped, every
change returns the checks, and simulations return a summary of the outputs rather than the
data. On your side:

- Be specific in the request (interface, parameters, units, stop time), so the agent needs
  fewer rounds.
- Say "don't build yet" while iterating; building is only needed for the final FMU.
- Start a new chat for each new model, and use a smaller, faster model for routine work.

## Security

- The server reads and writes only inside the workspace folder.
- Model code runs in a separate Python process for each request.
- The server runs the code in your models, as building an FMU does, and the agent writes
  that code. Use a workspace folder for agent work, and review models before using them
  elsewhere.
