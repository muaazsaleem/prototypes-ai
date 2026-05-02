# Low-Level Design: Fact-Checking Agent

## Context
Verifying factual claims in a text passage is a manual, error-prone task. Traditional LLM-based verification often suffers from hallucinations or lack of nuance. This system provides a structured, multi-stage pipeline to decompose prose into verifiable units and apply self-consistency voting to produce a high-confidence fact-check report using only a model's parametric knowledge.

## Goals
1. Decompose an arbitrary text passage into atomic, independently verifiable factual claims.
2. Gather supporting and contradicting evidence for each claim from the model's internal knowledge.
3. Apply self-consistency voting (N rounds at high temperature) to aggregate multiple independent verdicts into a single, calibrated confidence score.
4. Generate a human-readable terminal report with per-claim evidence and an overall credibility score.

## Non-Goals
*   **External Search**: This design does not use web search or RAG (Retrieval-Augmented Generation); it relies purely on the LLM's parametric knowledge.
*   **Source Attribution**: No external links or specific citations are provided for the gathered evidence.
*   **Sentence-Level Tracking**: The system decomposes the passage into *claims*, which may not map 1:1 to original sentences.

## Design Overview
The system follows a linear pipeline: **Decomposition → Evidence Gathering → Self-Consistency Voting → Reporting**. 

1.  **Orchestrator**: `main.py` coordinates the flow between components.
2.  **Decomposer**: Extracts atomic claims as JSON objects.
3.  **Evidence Gatherer**: For each claim, it retrieves both `supporting` and `contradicting` facts.
4.  **Judge (Voter)**: Evaluates the claim against the gathered evidence. It uses "Self-Consistency" (sampling the LLM multiple times at high temperature) to simulate a panel of judges, taking the majority verdict as the final answer.
5.  **Reporter**: Uses the `rich` library to assemble and display a visual summary.

**Data Flow**:
`Passage (str)` → `[Claim (dataclass)]` → `[Evidence (dataclass)]` → `[VoteResult (dataclass)]` → `FactCheckReport (dataclass)`.

## Execution Flow
1.  **Initialize**: Load `GEMINI_API_KEY`, initialize `genai.Client`.
2.  **Decompose**: Call `decompose_passage` with `TEMPERATURE_DECOMPOSE` (0.2). Receive a list of atomic claims.
3.  **Gather Evidence**: For each claim, call `gather_evidence` with `TEMPERATURE_EVIDENCE` (0.3). Retrieve supporting/contradicting evidence.
4.  **Vote (Self-Consistency)**: For each claim + its evidence:
    *   Iterate `VOTING_ROUNDS` (5) times.
    *   In each round, call `_single_vote` with `TEMPERATURE_VOTE` (0.8).
    *   Collect all verdicts (`TRUE`, `FALSE`, `UNVERIFIABLE`).
5.  **Aggregate**: Calculate the majority verdict and confidence score (`majority_count / total_rounds`).
6.  **Report**: Calculate overall credibility and render the results using `rich` panels and tables.

## Detailed Design

### Data Model
*   **Claim**: `index: int`, `text: str`.
*   **Evidence**: `claim: str`, `supporting: list[str]`, `contradicting: list[str]`.
*   **VoteResult**: `claim: str`, `individual_votes: list[str]`, `final_verdict: Literal["TRUE", "FALSE", "UNVERIFIABLE"]`, `confidence: float`, `reasoning: str`.
*   **FactCheckReport**: `passage: str`, `total_claims: int`, `results: list[VoteResult]`, `overall_credibility_score: float`.

### Core Logic and Algorithms
#### 1. Decomposition (Temperature 0.2)
The model is prompted to extract only "atomic" and "verifiable" claims. Lower temperature ensures high reproducibility and consistency in claim extraction.

#### 2. Evidence Gathering (Temperature 0.3)
The model is instructed to recall facts. The low-to-medium temperature allows for some breadth in recalled evidence while maintaining factual grounding.

#### 3. Self-Consistency Voting (Temperature 0.8)
This is the core reliability mechanism.
*   The model receives the claim and all gathered evidence.
*   It is prompted to decide `TRUE`, `FALSE`, or `UNVERIFIABLE`.
*   This process runs 5 times independently.
*   High temperature (0.8) introduces variance; if the model is "unsure", the votes will split.
*   **Confidence Calculation**: `winning_vote_count / total_rounds`.

#### 4. Credibility Scoring
`Overall Score = Count(TRUE claims) / Total Claims`.

### Error Handling
*   **JSON Parsing**: The system uses `response_mime_type="application/json"`. If parsing fails, it defaults to empty lists for claims/evidence or `UNVERIFIABLE` for verdicts.
*   **API Failures**: Handled via the `google-genai` library (raises exceptions).
*   **Missing API Key**: Checked at startup in `main.py`.

### Edge Cases
*   **Empty Passage**: Results in 0 claims and an overall credibility of 0.0 (guarded against division by zero in `reporter.py`).
*   **Ambiguous Claims**: Often lead to split votes (e.g., 3 TRUE, 2 FALSE), resulting in a lower confidence score (60%) and potentially an `UNVERIFIABLE` verdict if that becomes the majority.
*   **Hallucinated Evidence**: Since no external search is used, the "evidence" is as reliable as the model's training data. This is mitigated by the voting step which forces the model to judge the claim *given* that evidence.

### Alternatives Considered
*   **Single-Shot Verification**: Directly asking "is this passage true?". Rejected because it lacks transparency, cannot handle nuanced mixed-truth passages, and doesn't provide granular evidence.
*   **Search-Based Verification**: Using Google Search/Serper. Rejected to keep the system "purely parametric" and reduce external dependencies/latency.

---

## Visual Representation (Execution & Data Flow)

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [
    { "id": "el1", "type": "rectangle", "x": 100, "y": 100, "width": 120, "height": 60, "strokeColor": "#000", "backgroundColor": "#fff", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 1, "version": 1, "versionNonce": 1, "isDeleted": false, "boundElements": null, "updated": 1, "link": null, "locked": false, "text": "Input Passage" },
    { "id": "el2", "type": "arrow", "x": 220, "y": 130, "width": 80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 2, "version": 2, "versionNonce": 2, "isDeleted": false, "boundElements": null, "updated": 2, "link": null, "locked": false, "points": [[0, 0], [80, 0]] },
    { "id": "el3", "type": "rectangle", "x": 300, "y": 100, "width": 120, "height": 60, "strokeColor": "#1971c2", "backgroundColor": "#e7f5ff", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": { "type": 3 }, "seed": 3, "version": 3, "versionNonce": 3, "isDeleted": false, "boundElements": null, "updated": 3, "link": null, "locked": false, "text": "Decomposer\n(LLM)" },
    { "id": "el4", "type": "arrow", "x": 420, "y": 130, "width": 80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 4, "version": 4, "versionNonce": 4, "isDeleted": false, "boundElements": null, "updated": 4, "link": null, "locked": false, "points": [[0, 0], [80, 0]] },
    { "id": "el5", "type": "diamond", "x": 500, "y": 100, "width": 120, "height": 60, "strokeColor": "#000", "backgroundColor": "#fff", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 5, "version": 5, "versionNonce": 5, "isDeleted": false, "boundElements": null, "updated": 5, "link": null, "locked": false, "text": "List of Claims" },
    { "id": "el6", "type": "arrow", "x": 560, "y": 160, "width": 0, "height": 60, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 6, "version": 6, "versionNonce": 6, "isDeleted": false, "boundElements": null, "updated": 6, "link": null, "locked": false, "points": [[0, 0], [0, 60]] },
    { "id": "el7", "type": "rectangle", "x": 500, "y": 220, "width": 120, "height": 60, "strokeColor": "#1971c2", "backgroundColor": "#e7f5ff", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": { "type": 3 }, "seed": 7, "version": 7, "versionNonce": 7, "isDeleted": false, "boundElements": null, "updated": 7, "link": null, "locked": false, "text": "Evidence\nGatherer" },
    { "id": "el8", "type": "arrow", "x": 500, "y": 250, "width": -80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 8, "version": 8, "versionNonce": 8, "isDeleted": false, "boundElements": null, "updated": 8, "link": null, "locked": false, "points": [[0, 0], [-80, 0]] },
    { "id": "el9", "type": "diamond", "x": 300, "y": 220, "width": 120, "height": 60, "strokeColor": "#000", "backgroundColor": "#fff", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 9, "version": 9, "versionNonce": 9, "isDeleted": false, "boundElements": null, "updated": 9, "link": null, "locked": false, "text": "Claim +\nEvidence" },
    { "id": "el10", "type": "arrow", "x": 300, "y": 250, "width": -80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 10, "version": 10, "versionNonce": 10, "isDeleted": false, "boundElements": null, "updated": 10, "link": null, "locked": false, "points": [[0, 0], [-80, 0]] },
    { "id": "el11", "type": "rectangle", "x": 100, "y": 220, "width": 120, "height": 60, "strokeColor": "#c92a2a", "backgroundColor": "#fff5f5", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": { "type": 3 }, "seed": 11, "version": 11, "versionNonce": 11, "isDeleted": false, "boundElements": null, "updated": 11, "link": null, "locked": false, "text": "Judge (x5)\nSelf-Consistency" },
    { "id": "el12", "type": "arrow", "x": 160, "y": 280, "width": 0, "height": 60, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 12, "version": 12, "versionNonce": 12, "isDeleted": false, "boundElements": null, "updated": 12, "link": null, "locked": false, "points": [[0, 0], [0, 60]] },
    { "id": "el13", "type": "diamond", "x": 100, "y": 340, "width": 120, "height": 60, "strokeColor": "#000", "backgroundColor": "#fff", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 13, "version": 13, "versionNonce": 13, "isDeleted": false, "boundElements": null, "updated": 13, "link": null, "locked": false, "text": "Vote Results\n(Majority)" },
    { "id": "el14", "type": "arrow", "x": 220, "y": 370, "width": 80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 14, "version": 14, "versionNonce": 14, "isDeleted": false, "boundElements": null, "updated": 14, "link": null, "locked": false, "points": [[0, 0], [80, 0]] },
    { "id": "el15", "type": "rectangle", "x": 300, "y": 340, "width": 120, "height": 60, "strokeColor": "#000", "backgroundColor": "#fff", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 15, "version": 15, "versionNonce": 15, "isDeleted": false, "boundElements": null, "updated": 15, "link": null, "locked": false, "text": "Reporter" },
    { "id": "el16", "type": "arrow", "x": 420, "y": 370, "width": 80, "height": 0, "strokeColor": "#000", "backgroundColor": "transparent", "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": null, "seed": 16, "version": 16, "versionNonce": 16, "isDeleted": false, "boundElements": null, "updated": 16, "link": null, "locked": false, "points": [[0, 0], [80, 0]] },
    { "id": "el17", "type": "rectangle", "x": 500, "y": 340, "width": 120, "height": 60, "strokeColor": "#2f9e44", "backgroundColor": "#ebfbee", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "roundness": { "type": 3 }, "seed": 17, "version": 17, "versionNonce": 17, "isDeleted": false, "boundElements": null, "updated": 17, "link": null, "locked": false, "text": "Final Report" }
  ],
  "appState": { "viewBackgroundColor": "#ffffff", "gridSize": 20 }
}
```
