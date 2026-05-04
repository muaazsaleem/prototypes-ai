import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

search_func = {
    "name": "search",
    "description": "Searches for factual information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        },
        "required": ["query"]
    }
}

tools = types.Tool(function_declarations=[search_func])
config = types.GenerateContentConfig(tools=[tools], temperature=0.0)

contents = [types.Content(role="user", parts=[types.Part.from_text(text="What is the population of India?")])]

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=contents,
    config=config
)

if response.candidates[0].content.parts[0].function_call:
    fc = response.candidates[0].content.parts[0].function_call
    print(f"Function called: {fc.name}")
    print(f"Args: {fc.args}")
    
    # Append model's tool call
    contents.append(response.candidates[0].content)
    
    # Try creating a function response
    try:
        fr_part = types.Part.from_function_response(
            name=fc.name,
            response={"result": "1.44 billion"}
        )
        contents.append(types.Content(role="user", parts=[fr_part]))
        print("Successfully created FunctionResponse part.")
        
        response2 = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=config
        )
        print("Response 2:", response2.text)
    except Exception as e:
        print("Error creating function response:", e)
