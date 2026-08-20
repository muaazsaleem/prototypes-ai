# OTA Fix-It Debugger Prototype

This prototype demonstrates a simple **Observe-Think-Act (OTA)** loop using an LLM via [OpenRouter](https://openrouter.ai) (OpenAI-compatible API).

## How it works

1.  **Observe**: The debugger runs `broken_code.py` and captures the stack trace if it fails.
2.  **Think**: It sends the broken code and the error message to the model, asking for a fix.
3.  **Act**: It applies the suggested fix back to `broken_code.py` and repeats the loop until the code runs successfully or the maximum iterations are reached.

## Files

- `broken_code.py`: A simple Python script with intentional bugs (a typo and a potential zero-division error).
- `ota_debugger.py`: The core script that implements the OTA loop.

## Setup

This prototype is managed by [pixi](https://pixi.sh). From the repo root:

1.  **Install dependencies** (creates the `ota` environment):
    ```bash
    pixi install -e ota
    ```

2.  **Set your API Key**:
    ```bash
    export OPENROUTER_API_KEY="your_api_key_here"
    ```

3.  **Run the debugger**:
    ```bash
    pixi run ota
    ```

## Learning Points

- **Observe**: Capture raw state/feedback from the environment.
- **Think**: Use an LLM to reason about the delta between current state and desired state.
- **Act**: Apply the change and verify.
