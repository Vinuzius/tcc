from fastapi import FastAPI

from app.routers.first_example import router as first_example_router
from app.routers.health import router as health_router


app = FastAPI(title="TCC API")
app.include_router(first_example_router)
app.include_router(health_router)


def main() -> None:
    print("Run the API with: uvicorn main:app --reload --app-dir src")


if __name__ == "__main__":
    main()