import os
import json
from typing import List, Dict
from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

# Initialize Console for terminal styling
console = Console()

def extract_text(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    return "\n\n".join([doc.page_content for doc in docs])

def generate_queries(text: str, num_queries: int = 30) -> List[Dict]:
    """Generates evaluation queries based on the text using Gemini."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_id = "gemini-2.5-flash"

    prompt = f"""
    You are an expert in RAG evaluation. I am providing you with a technical document.
    Please generate {num_queries} diverse questions that can be answered using this document.
    For each question, provide:
    1. The question itself.
    2. A concise answer.
    3. A snippet of the source context from the document that contains the answer.

    Format the output as a JSON list of objects:
    [
      {{"question": "...", "answer": "...", "context": "..."}},
      ...
    ]
    
    Document snippet (first 30000 characters):
    {text[:30000]}
    
    Document snippet (middle 30000 characters):
    {text[len(text)//2 : len(text)//2 + 30000]}
    
    Document snippet (last 30000 characters):
    {text[-30000:]}
    """

    console.print(Panel("[bold blue]LLM Input:[/bold blue]\nGenerating 30 evaluation queries from the document...", title="Gemini Request"))
    
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    # Extract JSON from response
    try:
        queries = response.parsed
        if not queries:
            # Fallback for non-parsed response
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            queries = json.loads(content)
        
        console.print(Panel(f"[bold green]LLM Response:[/bold green]\nSuccessfully generated {len(queries)} queries.", title="Gemini Response"))
        return queries
    except Exception as e:
        console.print(f"[bold red]Error parsing LLM response:[/bold red] {e}")
        console.print(response.text)
        return []

if __name__ == "__main__":
    pdf_path = "technical_doc.pdf"
    
    with Progress() as progress:
        task1 = progress.add_task("[cyan]Extracting text...", total=100)
        text = extract_text(pdf_path)
        progress.update(task1, completed=100)
        
        task2 = progress.add_task("[magenta]Generating queries...", total=100)
        queries = generate_queries(text)
        progress.update(task2, completed=100)
    
    with open("eval_queries.json", "w") as f:
        json.dump(queries, f, indent=2)
    
    console.print(f"\n[bold green]Saved {len(queries)} queries to eval_queries.json[/bold green]")
