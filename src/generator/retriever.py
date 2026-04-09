from __future__ import annotations

from collections.abc import Sequence

from core import pinecone_client

from .schemas import RetrievedTemplate, TemplateMetadata


def _to_str_list(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    return []


def _to_float(value: object, default: float = 1.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _to_retrieved_template(
    document: dict[str, object],
    *,
    source: str,
) -> RetrievedTemplate | None:
    metadata_raw = document.get("metadata")
    if not isinstance(metadata_raw, dict):
        return None
    metadata = TemplateMetadata(
        bundle=str(metadata_raw.get("bundle", "")),
        industry_hint=str(metadata_raw.get("industry_hint", "")),
        modules=_to_str_list(metadata_raw.get("modules", [])),
        required_slots=_to_str_list(metadata_raw.get("required_slots", [])),
        version=str(metadata_raw.get("version", "1.0")),
        content=str(metadata_raw.get("content", document.get("page_content", ""))),
    )
    return RetrievedTemplate(
        metadata=metadata,
        content=str(document.get("page_content", metadata.content)),
        score=_to_float(document.get("score", 1.0)),
        source=source,
    )


async def retrieve_template(
    bundle: str,
    industry_hint: str | None = None,
) -> list[RetrievedTemplate]:
    target_industry = (industry_hint or "base").strip() or "base"
    fetch_ids = [
        f"{bundle}__{target_industry}",
        f"{bundle}__base",
        "generic__base",
    ]
    fetched_docs = await pinecone_client.fetch_documents(
        fetch_ids,
        namespace="templates",
    )
    fetched = [
        template
        for document in fetched_docs
        if (template := _to_retrieved_template(document, source="fetch")) is not None
    ]

    has_bundle_specific = any(item.metadata.bundle == bundle for item in fetched)
    if has_bundle_specific:
        return fetched

    query = f"bundle={bundle}; industry={target_industry}"
    search_docs = await pinecone_client.search(query, top_k=3, namespace="templates")
    searched = [
        template
        for document in search_docs
        if (template := _to_retrieved_template(document, source="search")) is not None
    ]
    if searched:
        return searched
    return fetched
