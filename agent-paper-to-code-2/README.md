# Paper-to-Code Agent (paper2code)

An autonomous agent that reads research papers and implements their core algorithms in Python. Powered by Google Gemini.

## Features
- **PDF/Text Ingestion**: Automatically extracts text from research papers.
- **ReAct Loop**: Uses a Reason-Act cycle to understand the paper, write code, run it, and fix errors.
- **Local Execution**: Runs code in a temporary sandbox to verify correctness before finishing.

## Installation

1. **Clone the repository** (if applicable).
2. **Install dependencies**:
   ```bash
   pip install -q -U google-genai pypdf pytest
   ```
3. **Set your API Key**:
   ```bash
   export GEMINI_API_KEY='your-gemini-api-key'
   ```

## Usage

Run the agent by providing a path to a paper (PDF or TXT) and an output file path:

```bash
python main.py paper.pdf implementation.py
```

### Optional Arguments
- `--max-steps <int>`: Set the maximum number of ReAct iterations (default: 12).

## How it Works
1. **Ingest**: Loads the paper and cleans the text.
2. **Think**: The LLM reasons about the paper's core contribution.
3. **Act**: The LLM calls tools to extract sections, write code, or run code.
4. **Reflect**: The LLM inspects execution results (stdout/stderr) and iterates until the code works.
5. **Finish**: The final verified code is saved to the output path.

## Development

Run tests to ensure the toolset is working correctly:
```bash
python -m pytest test.py
```
