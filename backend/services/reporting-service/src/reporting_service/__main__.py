import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "reporting_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_REPORTING_PORT", "32193")),
    )
