import os
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
response = client.models.embed_content(model="gemini-embedding-2", contents="Hello world")
print(type(response.embeddings))
print(type(response.embeddings[0].values))
print(len(response.embeddings[0].values))
