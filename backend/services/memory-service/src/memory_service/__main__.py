import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "memory_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_MEMORY_PORT", "32120")),
    )
