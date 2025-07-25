from celery.utils.log import get_task_logger

from database.repositories.collection.sync import CollectionRepositorySync
from database.repositories.file.sync import FileRepositorySync
from schemas.file import FileStatus
from utils.doc_processor import markitdown_converter, split_markdown
from utils.embeddings import get_embedding_model_by_provider_name
from vector_database.pgvector.model.factory import DocumentEmbeddingStatus
from vector_database.pgvector.repositories.sync import PgVectorRepositorySync

from .celery import Session, app

logger = get_task_logger(__name__)


def check_file_status(file_id: str, table_name: str):
    """
    Check the status of a file.
    """

    with Session() as session:
        file = FileRepositorySync(session).get_by_id(id=file_id)
        docs = PgVectorRepositorySync(session).get_documents(
            table_name=table_name, file_id=file_id
        )
        new_status = FileStatus.EMBEDDING

        if all(doc.status == DocumentEmbeddingStatus.SUCCESS for doc in docs):
            new_status = FileStatus.SUCCESS
        elif any(doc.status == DocumentEmbeddingStatus.FAILED for doc in docs):
            new_status = FileStatus.EMBEDDING_PARTIAL_FAILED

        if file.status != new_status:
            file.status = new_status
            session.commit()


@app.task(name="tasks.embed_document")
def embed_document(
    table_name: str,
    doc_id: str,
):
    """
    Embed a document using the specified provider and model.
    """

    with Session() as session:
        try:
            doc = PgVectorRepositorySync(session).get_document_by_id(
                table_name=table_name, id=doc_id
            )
            file = FileRepositorySync(session).get_by_id(id=doc.file_id)
            collection = CollectionRepositorySync(session).get_by_id(
                id=file.collection_id
            )
            embedding_model = get_embedding_model_by_provider_name(
                provider_name=collection.embedding_model_provider,
                model_name=collection.embedding_model,
                metadata=collection.embedding_model_metadata,
            )

            doc.embedding = embedding_model.embed_query(doc.text)
            doc.status = DocumentEmbeddingStatus.SUCCESS
            session.commit()
        except Exception:
            doc.status = DocumentEmbeddingStatus.FAILED
            session.commit()
            raise

        finally:
            # TODO: This can be optimized to avoid re-querying the file
            # Check the status of the file after embedding the document
            check_file_status(file_id=doc.file_id, table_name=table_name)


@app.task(name="tasks.embed_documents")
def embed_documents(file_id: str, table_name: str):
    with Session() as session:
        docs = PgVectorRepositorySync(session).get_documents(
            table_name=table_name, embedding_filter=False, file_id=file_id
        )

    for doc in docs:
        embed_document.apply_async(kwargs={"table_name": table_name, "doc_id": doc.id})


@app.task(name="tasks.extract_file")
def extract_file(file_id: str, table_name: str):
    """
    Extract content from a file and split it into documents.

    ### Args:
    - file_id: The ID of the file to process.
    - table_name: The name of the table to store documents.
    """
    with Session() as session:
        try:
            file = FileRepositorySync(session).get_by_id(id=file_id)
            result = markitdown_converter(source=file.path)
            docs = split_markdown(result.markdown)
            vector_repository = PgVectorRepositorySync(session)

            for doc in docs:
                vector_repository.stage_add_document(
                    table_name=table_name,
                    text=doc.page_content,
                    file_id=file.id,
                    status=DocumentEmbeddingStatus.PENDING,
                    meta={**doc.metadata},
                )

            file.status = FileStatus.CHUNKED
            session.commit()

            # Embed the documents
            embed_documents.apply_async(
                kwargs={"file_id": file.id, "table_name": table_name}
            )

        except Exception as e:
            file.status = FileStatus.CHUNK_FAILED
            session.commit()
            raise e


@app.task(name="tasks.process_file")
def process_file(file_id: str, table_name: str):
    """
    Process a file by extracting its content and embedding it.
    """
    extract_file.apply_async(kwargs={"file_id": file_id, "table_name": table_name})
