# Token Streaming Demo

Demonstrates that **streaming reduces perceived latency (TTFT), not total latency**.

Two side-by-side panels call the same model with the same prompt:
- **Left (No Streaming):** blank until the full response arrives — TTFT = total latency
- **Right (Streaming):** tokens appear word-by-word immediately — TTFT is a fraction of total latency

Use **"Compare Both"** to run them simultaneously and feel the difference.

---

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.
