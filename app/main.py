from fastapi import FastAPI

app = FastAPI(title="DataSeed")


@app.get("/api/v1/health")
async def health():
    return {"status": "healthy"}
