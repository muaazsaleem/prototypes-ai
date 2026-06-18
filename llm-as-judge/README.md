# LLM-as-a-Judge Evaluation Framework

This repository implements a production-ready demonstration of the LLM-as-a-Judge evaluation pattern using Gemini 2.5 Flash. The system evaluates natural language model responses against predefined rubrics or reference answers to provide reliable, automated quality assurance.

## Core Capabilities

The framework demonstrates two distinct evaluation methodologies.

### Fixed Rubric Evaluation

This methodology assesses model-generated responses against explicit, multidimensional grading criteria. It evaluates customer support agent responses using the following rubrics:

- Empathy and Tone: Scores responses on a 1-5 scale based on the level of empathy and professionalism.
- Accuracy and Correctness: Scores responses on a 1-5 scale to verify factuality and prevent hallucinations.
- Actionability: Scores responses on a 1-5 scale based on the clarity of next steps provided to the customer.

The application leverages a `RubricEvaluation` Pydantic model to enforce structured output, ensuring each score is accompanied by a qualitative justification.

### Golden Answer Comparison

This methodology measures how closely a candidate answer aligns with a reference standard of excellence, known as the golden answer. It evaluates technical database retention policy answers based on:

- Closeness Score: A metric from 0 to 100 representing semantic correctness and completeness.
- Detailed Justification: A granular breakdown of matching concepts, differences, and errors.

The application utilizes a `GoldenAnswerEvaluation` Pydantic model to parse the structured comparison.

## Architecture and Design

The framework is built using a lightweight, type-safe stack.

- Google GenAI SDK: Integrates with Gemini 2.5 Flash using the modern `google` package.
- Pydantic: Defines and enforces strict schemas for the evaluation outputs, enabling direct deserialization into Python objects.
- Rich: Generates structured, color-coded CLI output and comparative tables directly in the terminal.

## Getting Started

Follow these steps to configure the environment and run the demonstration.

### Prerequisites

Verify that Python 3.10 or higher is installed on your system.

### Installation

1. Clone this repository to your local machine.
2. Create and activate a virtual environment.
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

The evaluation framework requires a Gemini API key. Set the `GEMINI_API_KEY` environment variable in your terminal:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

### Execution

Run the demonstration script to execute both evaluation scenarios and view the comparison tables:

```bash
python main.py
```
