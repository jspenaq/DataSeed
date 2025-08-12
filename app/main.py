from fastapi import FastAPI

app = FastAPI(title="DataSeed")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
