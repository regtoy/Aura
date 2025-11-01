import pytest

from apps.api.response import ResponseCompiler, RetrievedDocument


def build_document(document_id: str, score: float, **metadata):
    return RetrievedDocument(document_id=document_id, score=score, metadata=metadata)


def test_response_compiler_selects_top_three_unique_documents():
    documents = [
        build_document("doc-1", 0.8, retriever="kb"),
        build_document("doc-2", 0.9, retriever="kb"),
        build_document("doc-3", 0.5, retriever="web"),
        build_document("doc-4", 0.4, retriever="ticket"),
    ]

    compiler = ResponseCompiler(max_citations=3)
    compiled = compiler.compile(answer="test", documents=documents)

    assert [citation.document_id for citation in compiled.citations] == [
        "doc-2",
        "doc-1",
        "doc-3",
    ]


def test_response_compiler_deduplicates_documents_by_id():
    documents = [
        build_document("doc-1", 0.9, retriever="kb"),
        build_document("doc-1", 0.6, retriever="web"),
        build_document("doc-2", 0.5, retriever="web"),
    ]

    compiler = ResponseCompiler(max_citations=3)
    compiled = compiler.compile(answer="test", documents=documents)

    assert len(compiled.citations) == 2
    assert compiled.citations[0].route == "kb"


def test_response_compiler_uses_route_fallback():
    documents = [build_document("doc-1", 0.9, source="vector"), build_document("doc-2", 0.8)]

    compiler = ResponseCompiler(max_citations=2)
    citations = list(compiler.select_citations(documents))

    assert citations[0].route == "vector"
    assert citations[1].route == "unknown"


def test_response_compiler_requires_positive_max_citations():
    with pytest.raises(ValueError):
        ResponseCompiler(max_citations=0)
