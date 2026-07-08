# ReAct Agent Token Overhead Demonstration

Demonstrates the **ReAct (Reasoning + Acting)** pattern: how an LLM interleaves
Thought → Action → Observation cycles to solve tasks using external tools, and
analytically showcases the **quadratic token overhead** ($O(N^2)$) that can occur
in agentic loops if left unmanaged.

---

## 🔬 The Core Problem: Why Agentic Loops are Token-Hungry

Every time an agent runs a ReAct step, it appends the entire history of:
- All previous **Thoughts**
- All previous **Tool Calls (Actions)**
- All previous **Tool Responses (Observations)**

And resends that complete conversational history to the model. This leads to several massive overheads:

1. **Quadratic Scaling ($O(N^2)$):** If a task requires $N$ steps and each step adds $K$ tokens on average, the input tokens for step $i$ are roughly $Prompt + (i-1)K$. Summing this over $N$ steps yields a total billing of:
   $$\text{Total Input Tokens} = N \cdot Prompt + \frac{N(N-1)}{2} K \approx O(N \cdot Prompt + N^2 \cdot K)$$
2. **Double Billing on Thoughts:** Any thought the LLM generates is billed once as an **Output Token**, and then resent as an **Input Token** in *every subsequent step*.
3. **Payload Bloat:** If a tool returns a massive raw document (e.g., scraped HTML or raw SQL tables), that entire chunk is carried forward and billed as input on every subsequent cycle.
4. **Infinite Loops:** If an agent gets stuck retrying a query or correcting a parsing error, it can quickly consume thousands of tokens with zero progress.

---

## 🏃 Run the Demo

To run the demonstration and view the token tracking metrics in real-time:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Export your Gemini API key
export GEMINI_API_KEY="your-api-key-here"

# 3. Run the demonstration script
python main.py
```

---

## 📊 Simulated Scenarios

The script runs three scenarios to demonstrate these concepts:

### Scenario 1: Optimized/Compact ReAct (Baseline)
- **Task:** Calculate $0.1\%$ of the population of India.
- **Payloads:** Returns compact, targeted factual answers.
- **Safety:** Loop detection enabled.
- **Result:** Completes quickly in 3 steps with very low token consumption.

### Scenario 2: Raw/Bloated Payload (Unoptimized RAG)
- **Task:** Compare the population and GDP of India and China, calculate their GDP per capita, and summarize.
- **Payloads:** Simulated tool responses are large, detailed paragraphs (~700 tokens each).
- **Result:** Demonstrates how large RAG chunks compound quadratically, running up the token count exponentially across 6+ steps.

### Scenario 3: Runaway Looping Agent (Safeguards Disabled)
- **Task:** Search for population of Brazil (missing from DB).
- **Payloads:** Returns a busy/retry prompt.
- **Safety:** Loop detection **disabled**; max steps capped at 8.
- **Result:** Demonstrates how easily a minor failure mode or transient error can burn through thousands of tokens in seconds.

---

## 🛠️ Best Practices for Mitigation

1. **Strict Loop Detection:** Automatically halt agents if they repeat the exact same tool and arguments (implemented in Scenario 1).
2. **Context Pruning & Summarization:** Summarize previous steps and compress tool responses, only carrying forward synthesized insights.
3. **Chunked & Targeted Retrieval:** Ensure tools return only the exact data required, rather than dumping large database rows or raw pages.
4. **Parallel Tool Calling:** Let the LLM trigger multiple independent actions simultaneously in a single turn, reducing sequential turns.
