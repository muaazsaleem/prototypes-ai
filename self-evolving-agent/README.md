# 🧬 Gemini 2.5 Self-Evolving AI Agent Prototype

This repository contains an interactive and beautifully formatted Python prototype demonstrating two distinct paradigms of autonomous AI capability expansion: **One-Time Script Execution** and **Long-Term Dynamic Tool Registration**.

Using **Gemini 2.5 Flash** and the next-generation **`google-genai`** Python SDK, this agent can dynamically write and run custom code to solve tasks beyond its starting capabilities.

---

## 🚀 Two Distinct Execution Philosophies

The prototype lets you choose between, or compare, two major ways agents expand their capabilities:

### Flow 1: One-Time Script Execution (Disposability-first)
* **How it works**: The agent is provided a tool called `execute_one_time_script(code)`. When it needs terminal/system capability, it writes a bespoke Python script designed to solve the task directly (e.g. imports `platform` and `os` to fetch OS metadata and files), executes it in a clean environment, and retrieves the results.
* **Trade-off**: Fast (completed in a single prompt turn), zero-state footprint, but has no API reusability or modular structure.

### Flow 2: Long-Term Tool Registration (Modularity-first)
* **How it works**: The agent is provided a meta-tool called `create_and_register_new_tool(name, code, description)`. When it needs a capability, it conceptually designs a modular, reusable Python function (e.g. `run_bash_command`), registers it dynamically in the runtime, and then *invokes it with custom parameters* in subsequent steps.
* **Trade-off**: Highly modular and reusable, fully integrated into Gemini's JSON schema tooling engine, but takes more message round-trips to bootstrap.

---

## 📁 Architectural Lifecycle Comparison

### Flow 1: One-Time Script Execution
```
┌──────────────────────────────┐      ┌────────────────────────────────┐      ┌──────────────────────────────┐
│  1. User gives complex task  │ ───> │  2. Agent writes bespoke code  │ ───> │  3. Code executes once,      │
└──────────────────────────────┘      └────────────────────────────────┘      │     returns stdout directly  │
                                                                              └──────────────┬───────────────┘
                                                                                             ▼
                                                                              ┌──────────────────────────────┐
                                                                              │  4. Agent synthesizes answer │
                                                                              └──────────────────────────────┘
```

### Flow 2: Long-Term Tool Registration
```
┌──────────────────────────────┐      ┌────────────────────────────────┐      ┌──────────────────────────────┐
│  1. User gives complex task  │ ───> │  2. Agent Realizes Lacks Tool  │ ───> │  3. Calls Meta-tool to write │
└──────────────────────────────┘      └────────────────────────────────┘      │     reusable Tool (tools/X.py)│
                                                                              └──────────────┬───────────────┘
                                                                                             ▼
┌──────────────────────────────┐      ┌────────────────────────────────┐      ┌──────────────────────────────┐
│  6. Agent synthesizes answer │ <─── │  5. Agent calls new Tool X     │ <─── │  4. Tool dynamically loaded  │
│     from execution results   │      │     with custom parameters     │      │     & registered in SDK      │
└──────────────────────────────┘      └────────────────────────────────┘      └──────────────────────────────┘
```

---

## 🛠️ Installation & Setup

1. **Prerequisites**: Ensure you have Python 3.10+ installed.
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

To run the interactive prototype, execute:

```bash
python main.py
```

### Options Available:
* **Option 1**: Run the One-Time Script Execution Flow.
* **Option 2**: Run the Long-Term Dynamic Tool Registration Flow.
* **Option 3**: Run **both** flows sequentially and print a beautiful side-by-side analysis comparing execution time, turn counts, and architectural trade-offs!

---

## 📁 File Structure

- `agent.py`: Houses the `SelfEvolvingAgent` runner supporting dual-mode execution (`one_time` and `long_term`), the console logging engine, and the code-compiler runtime.
- `main.py`: Interactive entrypoint to choose or compare the execution paradigms.
- `tools/`: Workspace directory where permanent dynamic tools are written and compiled on the fly.
