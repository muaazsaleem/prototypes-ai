import os

MODEL_NAME = "gemini-2.5-flash"

# How many independent LLM calls to make per claim before taking the majority verdict.
# Higher values raise confidence reliability but multiply API cost linearly.
VOTING_ROUNDS = 5

# Lower temperature = more deterministic; higher = more diverse outputs.
TEMPERATURE_DECOMPOSE = 0.2  # deterministic: consistent claim extraction across runs
TEMPERATURE_EVIDENCE = 0.3  # slight variance: allows different evidence angles
TEMPERATURE_VOTE = 0.8  # high variance: stress-tests self-consistency across rounds

VERDICTS = ["TRUE", "FALSE", "UNVERIFIABLE"]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SAMPLE_PASSAGE = (
    "Albert Einstein was born in 1879 in Ulm, Germany. "
    "He published his special theory of relativity in 1905 while working as a patent clerk in Bern. "
    "Einstein won the Nobel Prize in Physics in 1921 for his work on the theory of relativity. "
    "He emigrated to the United States in 1933, where he joined the faculty at Harvard University. "
    "Einstein's famous equation E=mc² fundamentally changed our understanding of "
    "the relationship between mass and energy."
)
