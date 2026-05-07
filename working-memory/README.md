# Working Memory: Context Overflow & Memory Management

Demonstrates that context is finite and memory management is an engineering problem, not a prompt problem.

An AI agent reviews a 10-step database migration plan. At each step it receives new tool output and must remember everything it has seen. The prototype runs the same task three times to demonstrate different memory management techniques:

- Phase 1 -- Eviction (Sliding Window): Drops the oldest turns from the context when the token budget is exceeded.
- Phase 2 -- Summarization: Compresses completed steps mid-flight into a dense bullet-point memory block to keep the context size small.
- Phase 3 -- External Storage (Chroma DB): Keeps the context strictly to the current step and uses a vector database to retrieve and inject relevant past steps on demand.

At the end of all three phases, the agent is asked to recall a specific fact from Step 1 (exact rollback command and time window). The eviction agent fails because the tokens were permanently dropped; both the summarization and external storage agents succeed because they preserved the necessary facts using engineering techniques.

## Concept

| | Eviction | Summarization | External Storage |
|---|---|---|---|
| Context growth | Linear until budget, then plateaus | Bounded by periodic compression | Flat, bounded strictly per step |
| Memory mechanism | None | Generative compression | Vector database retrieval |
| Step-1 recall | LOST | RETAINED | RETAINED |

The key insight: the model did not forget because it was "bad at remembering". It forgot because the tokens were physically absent from the context window. The fix is not a better prompt -- it is an engineering step (summarization or external retrieval) that keeps critical facts accessible.

## Approach

The prototype implements three separate lifecycle loops in `main.py` to handle the finite context budget.

### Eviction

During the eviction phase, the system appends the latest turn to the context array and calculates the total token count. If the count exceeds the configured budget, it removes the oldest user and assistant message pair from the history list until the context is back under budget. This sliding window approach guarantees the agent will not hit a hard API limit, but it results in total amnesia for early conversation steps.

### Summarization

The summarization strategy relies on mid-flight compression. The agent monitors the step count as it progresses. When a specific threshold is reached, it triggers a separate LLM call to compress all raw inputs and findings from completed steps into a dense, prose-free bulleted list. The script then replaces the entire verbose conversation history with this single compressed memory block, resetting the context size and allowing the agent to continue without losing critical facts.

### External Storage

The external storage phase uses Chroma DB as a vector database. It relies on a custom `GeminiEmbeddingFunction` to seamlessly generate embeddings via the Gemini API without requiring heavy local PyTorch dependencies.

In this phase, the agent never accumulates a running history. Each LLM call consists strictly of the current step and any retrieved context. After the agent generates a finding for the current step, the tool output and the finding are embedded and stored as a document in Chroma DB. On subsequent steps, the script queries the database for the most relevant past documents and injects them directly into the current prompt. This Retrieval-Augmented Generation approach keeps the token usage extremely low and constant per step while maintaining access to the entire project history.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python3 main.py
```

Expected runtime: ~3-5 minutes due to embedding API rate limits and summarization steps.

## Output

- Step-by-step token bars for all three phases, highlighted when over budget or using retrieval
- Inline compression stats for the summarization phase
- Verification results showing what is retained vs lost
- Final comparison table showing token usage per step across the three techniques