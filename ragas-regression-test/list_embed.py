import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
for m in client.models.list():
    if 'embedContent' in m.supported_actions:
        print(m.name)
