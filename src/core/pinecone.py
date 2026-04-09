from __future__ import annotations


class PineconeClient:
    """Small client facade with async-safe no-op defaults for tests/dev."""

    def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def fetch_documents(
        self,
        ids: list[str],
        namespace: str,
    ) -> list[dict[str, object]]:
        _ = (ids, namespace)
        return []

    async def search(
        self,
        query: str,
        top_k: int,
        namespace: str,
    ) -> list[dict[str, object]]:
        _ = (query, top_k, namespace)
        return []


pinecone_client = PineconeClient()
