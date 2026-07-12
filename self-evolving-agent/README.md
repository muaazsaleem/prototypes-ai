# 🧬 Gemini 2.5 Self-Evolving AI Agent Prototype

This repository contains a highly interactive, beautifully designed Python prototype demonstrating a **Self-Evolving AI Agent**.

Using **Gemini 2.5 Flash** and the official next-generation **`google-genai`** Python SDK, this agent has the unique ability to **write and register its own tools on the fly** when it encounters tasks it cannot solve with its starting toolset.

---

## 🚀 How It Works Under the Hood

The agent starts with a minimal set of pre-defined tools:
1. `get_current_time()`: Retrieves the current system date/time.
2. `fetch_webpage_content(url)`: Fetches a snippet of content from a webpage.
3. `create_and_register_new_tool(name, code, description)`: **The Meta-Tool.**

### The Evolution Cycle

```
                   ┌──────────────────────────────┐
                   │  1. User gives a complex task │
                   └──────────────┬───────────────┘
                                  ▼
                   ┌──────────────────────────────┐
                   │ 2. Agent checks tool list:    │
                   │    Realizes it lacks tool X  │
                   └──────────────┬───────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Agent calls Meta-Tool: 'create_and_register_new_tool'        │
│    - Generates complete, annotated Python code for tool X.      │
│    - Saves it dynamically to `tools/X.py`.                       │
│    - Dynamically loads and imports the new callable function.   │
│    - Adds the function to the Agent's active tools dictionary.  │
└────────────────────────────────┬────────────────────────────────┘
                                 ▼
                   ┌──────────────────────────────┐
                   │ 4. Success message returned  │
                   │    to model context          │
                   └──────────────┬───────────────┘
                                  ▼
                   ┌──────────────────────────────┐
                   │ 5. Agent immediately calls   │
                   │    newly registered Tool X   │
                   └──────────────┬───────────────┘
                                  ▼
                   ┌──────────────────────────────┐
                   │ 6. Agent solves task with X! │
                   └──────────────────────────────┘
```

When given a challenge that requires terminal operations (e.g., getting OS and CPU info, or listing directory files), the agent:
1. Realizes it has no terminal tool.
2. Dynamically generates the Python code for a bash tool (`run_bash_command`).
3. Saves it to `tools/run_bash_command.py` and registers it in its runtime toolset.
4. Uses it to query system information.
5. Successfully outputs the final summary!

---

## 🛠️ Installation & Setup

1. **Prerequisites**: Ensure you have Python 3.10+ installed and your virtual environment activated.
2. **Install dependencies**:
   ```bash
   pip install google-genai rich requests
   ```
3. **Configure API Key**:
   Set your Gemini API key in your environment variables:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

---

## 🏃‍♂️ Running the Agent

To execute the demo and watch the agent evolve and solve the task in real-time, simply run:

```bash
python main.py
```

### What you will see:
- A beautifully formatted terminal output (using the `rich` library) showing each step of the agent's thought process, tool generation, dynamic imports, and execution.
- A new file `tools/run_bash_command.py` created automatically containing the clean, type-hinted, and docstring-documented bash execution tool created by Gemini.

---

## 📁 File Structure

- `agent.py`: Houses the `SelfEvolvingAgent` runner, history log, manual tool execution loop, and the dynamic import engine.
- `main.py`: Entrypoint for running the demonstration task.
- `tools/`: Workspace directory where dynamic tools are written and compiled on the fly.
