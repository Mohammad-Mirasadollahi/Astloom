"""Tiny sample module for graph ingest fixtures."""


def greet(name: str) -> str:
    return f"hello {name}"


def main() -> None:
    print(greet("astloom"))


if __name__ == "__main__":
    main()
