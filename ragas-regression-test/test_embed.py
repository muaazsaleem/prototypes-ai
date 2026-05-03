import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class FixedGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

emb = FixedGoogleEmbeddings(model="models/gemini-embedding-2")
res = emb.embed_documents(["hello", "world"])
print(len(res), len(res[0]))
