# Cross-Encoder vs Bi-Encoder Prototype

This prototype demonstrates why Cross-Encoders are essential for high-precision ranking tasks, even though Bi-Encoders are faster for initial retrieval.

## Comparative Scenarios

The application demonstrates model performance across three classic semantic search challenges where Bi-Encoders frequently struggle.

### Scenario 1: Lexical and Semantic Ambiguity

Query: `apple computer`

- Concept: Bi-encoders are biased by keyword overlap. When searching for a tech brand, documents containing the word apple (like apple pie) align strongly in vector space. Cross-encoders use joint attention to recognize that computer restricts the meaning of apple to technology.

### Scenario 2: Logical Relation and Negation

Query: `Does aspirin treat headaches?`

- Concept: Bi-encoders struggle with semantic relationships (causes vs. treats) and negation because they compress sentences into a single vector, losing syntactical directionality. Cross-encoders maintain token-to-token interactions, accurately resolving complex logic.

### Scenario 3: Asymmetric Directional Search

Query: `flight from Boston to New York`

- Concept: Directional queries are difficult for bi-encoders. Since the vocabulary of Boston to New York and New York to Boston is identical, their dense embeddings are nearly identical. Cross-encoders capture precise sequence order and prepositions.

## System Architecture

1. Bi-Encoders:
  - Process the query and document independently.
  - Compute cosine similarity between query and document vectors.
  - Highly efficient for indexing and retrieving from millions of documents.
2. Cross-Encoders:
  - Process the query and document simultaneously using self-attention.
  - Produce a classification score representing relevance.
  - Highly precise but computationally intensive, making them ideal for re-ranking the top results.

## Setup and Usage

Follow these steps to run the prototype.

### Installation

Install the required dependencies.

```bash
pip install -r requirements.txt
```

### Running Scenarios

Run all scenarios in sequence.

```bash
python3 main.py --scenario all
```

Run a specific scenario (1, 2, or 3).

```bash
python3 main.py --scenario 1
```

### Custom Evaluation

Run a custom query with a list of candidate documents.

```bash
python3 main.py --query "your query here" --docs "doc 1" "doc 2" "doc 3"
```

Alternatively, run the script without arguments in a terminal for an interactive menu.

```bash
python3 main.py
```
