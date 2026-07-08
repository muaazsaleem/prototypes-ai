# ReAct Agent Token Overhead Demonstration

Demonstrates the **ReAct (Reasoning + Acting)** pattern: how an LLM interleaves
Thought → Action → Observation cycles to solve tasks using external tools, and
analytically showcases the **quadratic token overhead** ($O(N^2)$) that can occur
in agentic loops if left unmanaged.

---

## 🧰 Tools and Setup

This prototype implements the following tools:
- **`search`**: Simulated web search (compact vs. bloated modes) to find factual demographic and economic information.
- **`summariser`**: Text summarisation via Gemini to compress large payloads.
- **`calculator` (Commented Out)**: Fully implemented arithmetic expression evaluator. It is commented out of the active tools list by default, demonstrating how the agent falls back to performing calculations internally using its native reasoning capabilities when the tool is unexposed. You can uncomment it in `main.py` to compare tool-based vs. internal math processing.

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

## 📊 Demonstration Scenario

The script runs an unoptimized RAG scenario to demonstrate quadratic token accumulation:

### Scenario: Raw/Bloated Payload (Unoptimized RAG)
- **Task:** Calculate the population density for both India and China. Identify the country with the lower density, and calculate what its total GDP would be if its population increased to match the other country's density.
- **Payloads:** Simulated tool responses are large, detailed paragraphs (~700 tokens each).
- **Result:** Demonstrates how large RAG chunks compound quadratically, running up the token count exponentially across 6+ steps.

---

## 🛠️ Best Practices for Mitigation

1. **Strict Loop Detection:** Automatically halt agents if they repeat the exact same tool and arguments.
2. **Context Pruning & Summarization:** Summarize previous steps and compress tool responses, only carrying forward synthesized insights.
3. **Chunked & Targeted Retrieval:** Ensure tools return only the exact data required, rather than dumping large database rows or raw pages.
4. **Parallel Tool Calling:** Let the LLM trigger multiple independent actions simultaneously in a single turn, reducing sequential turns.
