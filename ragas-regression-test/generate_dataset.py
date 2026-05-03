import json
import os
import google.generativeai as genai
from typing import List, Dict

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")


def generate_batch(batch_size: int, domain: str) -> List[Dict]:
    """Generates a batch of RAG evaluation samples using the Gemini API.

    Makes a network call to Gemini. Returns a list of dictionaries, each containing
    a question, ground_truth, and a list of contexts. Returns an empty list if
    the response cannot be parsed as valid JSON.
    """
    prompt = f"""
    Generate {batch_size} realistic RAG (Retrieval-Augmented Generation) evaluation samples for the domain: {domain}.
    Each sample must be a JSON object with:
    - "question": A specific user query.
    - "ground_truth": The ideal correct answer.
    - "contexts": A list of 3-5 short relevant documentation snippets that contain the answer.

    Return ONLY a JSON list of objects.
    """

    response = model.generate_content(prompt)
    try:
        # Clean the response to remove Markdown code blocks before parsing
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return []


def main():
    """Orchestrates the dataset generation process in batches.

    Repeatedly calls generate_batch until the total_samples target is met.
    Saves the resulting dataset to 'dataset.json' in the current directory.
    """
    domain = "AWS Cloud Infrastructure and DevOps Support"
    total_samples = 100
    batch_size = 10
    dataset = []

    print(f"Generating {total_samples} samples for {domain}...")

    while len(dataset) < total_samples:
        needed = total_samples - len(dataset)
        # Ensure the last batch doesn't exceed the required total
        current_batch = min(batch_size, needed)
        batch = generate_batch(current_batch, domain)
        dataset.extend(batch)
        print(f"Progress: {len(dataset)}/{total_samples}")

    # Slice the dataset to exactly total_samples in case the model over-generated
    with open("dataset.json", "w") as f:
        json.dump(dataset[:total_samples], f, indent=4)


if __name__ == "__main__":
    main()
