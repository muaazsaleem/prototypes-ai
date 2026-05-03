import json
import os
from typing import List, Dict
from google import genai

# Initialize the Gemini Client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_batch(batch_size: int, domain: str) -> List[Dict]:
    """Generates a batch of query/answer/context triples using Gemini.

    Sends a structured prompt to the Gemini model to generate synthetic RAG data
    in JSON format. Handles Markdown cleaning and JSON parsing.
    """
    prompt = f"""
    Generate {batch_size} realistic RAG (Retrieval-Augmented Generation) evaluation samples for the domain: {domain}.
    Each sample must be a JSON object with:
    - "question": A specific user query.
    - "ground_truth": The ideal correct answer.
    - "contexts": A list of 3-5 short relevant documentation snippets that contain the answer.

    Return ONLY a JSON list of objects.
    """

    # Using the new google-genai SDK method
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    try:
        # Clean the response to ensure it's valid JSON
        text = response.text.strip()
        # Remove Markdown code block markers if present
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return []


def main():
    """Orchestrates the generation of a 100-sample dataset.

    Batches requests to the Gemini API and saves the final consolidated list
    to 'dataset.json'.
    """
    domain = "AWS Cloud Infrastructure and DevOps Support"
    total_samples = 100
    batch_size = 10
    dataset = []

    print(f"Generating {total_samples} samples for {domain}...")

    while len(dataset) < total_samples:
        needed = total_samples - len(dataset)
        # Calculate the size for the current batch
        current_batch = min(batch_size, needed)
        batch = generate_batch(current_batch, domain)
        dataset.extend(batch)
        print(f"Progress: {len(dataset)}/{total_samples}")

    # Save only up to the requested total samples
    with open("dataset.json", "w") as f:
        json.dump(dataset[:total_samples], f, indent=4)


if __name__ == "__main__":
    main()
