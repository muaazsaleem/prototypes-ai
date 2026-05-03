from ragas.metrics import ContextPrecision, Faithfulness
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from datasets import Dataset
import os

eval_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=os.environ["GEMINI_API_KEY"])

class FixedGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

eval_embeddings = FixedGoogleEmbeddings(model="models/gemini-embedding-2", google_api_key=os.environ["GEMINI_API_KEY"])

ds = Dataset.from_list([
    {
        "user_input": "hello",
        "response": "hi",
        "retrieved_contexts": ["hello"],
        "reference": "hello"
    }
])

score = evaluate(
    dataset=ds,
    metrics=[ContextPrecision(), Faithfulness()],
    llm=eval_llm,
    embeddings=eval_embeddings,
    show_progress=False
)
print(score)
