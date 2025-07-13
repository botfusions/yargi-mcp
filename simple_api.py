from fastapi import FastAPI

app = FastAPI(title="Yargi MCP API Test", version="1.0.0")

@app.get("/")
def root():
    return {
        "message": "Yargi MCP API Test Working!", 
        "status": "online",
        "version": "1.0.0"
    }

@app.get("/search")  
def search():
    return {
        "result": "Test search working", 
        "data": ["Karar 1", "Karar 2", "Karar 3"],
        "count": 3
    }

@app.get("/health")
def health():
    return {"status": "healthy", "api": "working"}