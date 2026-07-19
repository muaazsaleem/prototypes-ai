# Multi-Agent Hand-off Deadlock Simulation Prototype

A visually stunning, lightweight Python prototype demonstrating **system deadlock (infinite routing loop)** in multi-agent architectures due to circular policy dependencies.

This project demonstrates the issue using real agent tooling (function calling) powered by the official **Google GenAI SDK (`google-genai`)** and **Gemini 2.5 Flash** with a robust, high-fidelity fallback simulator.

---

## 📸 The Problem: Circular Policy Dependency

In multi-agent systems with direct agent-to-agent hand-offs, routing deadlocks occur when Agent A and Agent B depend on prerequisites that only the other can satisfy:

```
┌──────────────────┐               Handoff (Needs Damage Verification)               ┌────────────────────┐
│   Refund Agent   │ ──────────────────────────────────────────────────────────────> │   Shipping Agent   │
│                  │                                                                 │                    │
│ Prerequisite:    │ <────────────────────────────────────────────────────────────── │ Prerequisite:      │
│ Shipping must    │               Handoff (Needs Authorized Refund Ticket)          │ Refund ticket must │
│ confirm damage   │                                                                 │ be authorized first│
└──────────────────┘                                                                 └────────────────────┘
```

Because neither can proceed without the other acting first, they enter an infinite routing cycle (Deadlock), burning API tokens and hanging execution.

---

## 🛠️ Project Structure

```
deadlock/
├── .gitignore           # Ignores venv, caches, and environment variables
├── requirements.txt     # Pin-points google-genai, python-dotenv, and rich
├── main.py     # Main prototype script with inner-agent loops
└── README.md            # You are here!
```

---

## 🚀 Getting Started

### 1. Set Up Environment

Ensure you have Python 3.10+ installed.

```bash
# Clone or navigate to the directory
cd deadlock

# Create virtual environment if not already present
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Gemini API Key (Optional)

You can run the prototype in **Simulated Mode** immediately without any API keys. 

To run using actual **Gemini 2.5 Flash** models with genuine function calling:

1. Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
2. The script will automatically detect the key, instantiate the `google-genai` client, and run live API requests!

### 3. Run the Simulation

Execute the main script:

```bash
python main.py
```

---

## 🔍 How the Code Works

The implementation models a highly realistic agent hand-off loop:

1. **Outer Loop**: Orchestrates which agent is currently active.
2. **Inner loops (`run_refund_agent` and `run_shipping_agent`)**: Run within each agent's execution scope. The agent is queried with its strict system prompt, the user's inquiry, and the complete hand-off/tool history.
3. **Decide Action**:
   - If the model decides to invoke its hand-off tool (e.g., `handoff_to_shipping`), the inner loop is broken, returning the next agent's name to the outer loop.
   - If the maximum steps (e.g., `8`) are reached, the system detects a deadlock, breaks execution, and generates a post-mortem diagnostic analysis report.

---

## 💡 How to Mitigate Agent Deadlocks

This prototype proposes three production-grade remedies:

1. **Orchestrator Routing (Centralized Control)**: Replace direct point-to-point hand-offs with a central router/orchestrator that tracks visit frequency. If an agent-cycle is detected, the orchestrator breaks the loop and routes to a human operator or default fallback handler.
2. **Prerequisite Relaxation**: Decouple states so agents can work independently. For example, allow the Shipping Agent to inspect transit damage status independently of whether a refund ticket is authorized.
3. **Loop Detection Middleware**: Monitor the agent execution stack. If the same ticket is routed back to a previously visited agent with no change in state, halt execution with a cycle exception immediately.
