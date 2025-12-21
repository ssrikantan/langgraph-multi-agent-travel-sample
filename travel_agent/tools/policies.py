import re
import requests
import numpy as np
import openai
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from langchain_core.tools import tool

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)


# client = OpenAI(api_key="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")
aoai_client = AzureOpenAI(
    azure_endpoint="https://aoai-gpt4-001.openai.azure.com",
    azure_ad_token_provider=token_provider,
    api_version="2024-12-01-preview",
)

response = requests.get(
    "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md"
)
response.raise_for_status()
faq_text = response.text

docs = [{"page_content": txt} for txt in re.split(r"(?=\n##)", faq_text)]


class VectorStoreRetriever:
    def __init__(self, docs: list, vectors: list, oai_client):
        self._arr = np.array(vectors)
        self._docs = docs
        self._client = oai_client

    @classmethod
    def from_docs(cls, docs, oai_client):
        embeddings = oai_client.embeddings.create(
            model="text-embedding-3-small", input=[doc["page_content"] for doc in docs]
        )
        vectors = [emb.embedding for emb in embeddings.data]
        return cls(docs, vectors, oai_client)

    def query(self, query: str, k: int = 5) -> list[dict]:
        embed = self._client.embeddings.create(
            model="text-embedding-3-small", input=[query]
        )
        # "@" is just a matrix multiplication in python
        scores = np.array(embed.data[0].embedding) @ self._arr.T
        top_k_idx = np.argpartition(scores, -k)[-k:]
        top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]
        return [
            {**self._docs[idx], "similarity": scores[idx]} for idx in top_k_idx_sorted
        ]


retriever = VectorStoreRetriever.from_docs(docs, aoai_client)


@tool
def lookup_policy(query: str) -> str:
    """Consult the company policies to check whether certain options are permitted.
    Use this before making any flight changes performing other 'write' events."""
    docs = retriever.query(query, k=2)
    return "\n\n".join([doc["page_content"] for doc in docs])