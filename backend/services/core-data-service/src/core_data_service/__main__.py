import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "core_data_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_CORE_DATA_PORT", "32110")),
    )
