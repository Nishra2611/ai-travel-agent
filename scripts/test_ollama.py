import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url=os.getenv("OLLAMA_BASE_URL"),
)

response = llm.invoke("Say hello in JSON format")

print(response.content)
print("✓ Ollama working")
