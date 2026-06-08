import time

from langchain_ollama import ChatOllama

print("Creating model...")
llm = ChatOllama(model="qwen3:8b", temperature=0)

print("Sending request...")
start = time.time()

response = llm.invoke("What is 2+2?")

print("Done in", time.time() - start, "seconds")
print(response.content)
