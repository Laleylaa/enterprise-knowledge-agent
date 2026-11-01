"""Shared explicit preparation for both CLIs; never calls a main model."""

from pathlib import Path

from knowledge_agent.document_loader import load_documents, SourceManifest
from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.factory import build_index
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot, prepare_documents, save_prepared
from knowledge_agent.retrieval.tokenizer import BgeTokenizer, download_tokenizer


def prepare_knowledge(settings, *, download=False):
    corpus = settings.corpus_path.resolve()
    if corpus.is_dir():
        corpus = corpus / 'manifest.json'
    if settings.prepared_path is None:
        raise ValueError('prepare 需要 --prepared 输出路径，或 KA_PREPARED_PATH。')
    destination = settings.prepared_path.resolve()
    documents = load_documents(corpus)
    metadata = SourceManifest.model_validate_json(corpus.read_bytes())
    protected = {corpus, settings.tokenizer_path.resolve()}
    protected.update((corpus.parent / d.source_path).resolve() for d in metadata.documents)
    if destination in protected or destination.is_relative_to(settings.embedding_model_path.resolve()):
        raise ValueError('派生块输出不能覆盖原文、清单、tokenizer 或模型资产。')
    retrieval = settings.selected_retrieval
    if download and retrieval in {'vector', 'hybrid'}:
        from knowledge_agent.retrieval.model_assets import download_model
        download_model(settings.embedding_model_path)
    if retrieval in {'vector', 'hybrid'} and 'tokenizer_path' not in settings.model_fields_set:
        candidate = settings.embedding_model_path / 'tokenizer.json'
        if candidate.is_file():
            settings = settings.model_copy(update={'tokenizer_path': candidate})
    if download:
        try:
            BgeTokenizer(settings.tokenizer_path)
        except CorpusError:
            download_tokenizer(settings.tokenizer_path)
    bundle = prepare_documents(documents, settings)
    # Build from exactly the prepared in-memory snapshot; never reread changing sources.
    snapshot = RetrievalSnapshot(documents, bundle, settings)
    index = build_index(snapshot, settings, retrieval)
    try:
        errors = list(getattr(index, 'startup_errors', ()))
        save_prepared(bundle, destination)
        return {'status': 'partial' if errors else 'prepared', 'corpus_hash': bundle.corpus_hash,
                'chunks_hash': bundle.chunks_hash, 'chunks': len(bundle.chunks),
                'corpus': str(corpus), 'prepared': str(destination), 'retrieval': retrieval,
                'index_hash': index.index_hash, 'cache_status': getattr(index, 'cache_status', None),
                'effective_branches': list(index.backends) if retrieval == 'hybrid' else [retrieval],
                'errors': errors, 'model_calls': 0}
    finally:
        close = getattr(index, 'close', None)
        if close is not None:
            close()
