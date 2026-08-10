import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "code_graph_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_CODE_GRAPH_PORT", "32140")),
    )
