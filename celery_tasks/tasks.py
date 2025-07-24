from celery.utils.log import get_task_logger

from database.models.collection import Collection
from database.models.file import File
from schemas.file import FileStatus
from settings import VectorStore
from utils.doc_processor import markitdown_converter, split_markdown
from utils.embeddings import get_embedding_model_by_provider_name
from utils.vector_store import EmbeddingStatus

from .celery import Session, app

logger = get_task_logger(__name__)


def check_file_status(file_id: str, table_name: str):
    """
    Check the status of a file.
    """

    with Session() as session:
        file = session.query(File).filter(File.id == file_id).one()
        VectorOrm = VectorStore.get_vector_model(table_name=table_name)
        docs = session.query(VectorOrm).filter(VectorOrm.file_id == file_id).all()

        new_status = FileStatus.EMBEDDING

        if all(doc.status == EmbeddingStatus.SUCCESS for doc in docs):
            new_status = FileStatus.SUCCESS
        elif any(doc.status == EmbeddingStatus.FAILED for doc in docs):
            new_status = FileStatus.EMBEDDING_PARTIAL_FAILED

        if file.status != new_status:
            file.status = new_status
            session.commit()


@app.task(name="tasks.embed_doc")
def embed_doc(
    table_name: str,
    doc_id: str,
):
    """
    Embed a document using the specified provider and model.
    """

    VectorOrm = VectorStore.get_vector_model(table_name=table_name)

    if not VectorOrm:
        raise ValueError(f"Vector model for table '{table_name}' not found")

    with Session() as session:
        try:
            doc = session.query(VectorOrm).filter(VectorOrm.id == doc_id).one()
            file = session.query(File).filter(File.id == doc.file_id).one()
            collection = (
                session.query(Collection)
                .filter(Collection.id == file.collection_id)
                .one()
            )

            embedding_model = get_embedding_model_by_provider_name(
                provider_name=collection.embedding_model_provider,
                model_name=collection.embedding_model,
                metadata=collection.embedding_model_metadata,
            )

            doc.embedding = embedding_model.embed_query(doc.text)
            doc.status = EmbeddingStatus.SUCCESS
            session.commit()
        except Exception:
            doc.status = EmbeddingStatus.FAILED
            session.commit()
            raise

        finally:
            # TODO: This can be optimized to avoid re-querying the file
            # Check the status of the file after embedding the document
            check_file_status(file_id=doc.file_id, table_name=table_name)


@app.task(name="tasks.embed_documents")
def embed_documents(file_id: str, table_name: str):
    VectorOrm = VectorStore.get_vector_model(table_name=table_name)

    if not VectorOrm:
        raise ValueError(f"Vector model for table '{table_name}' not found")

    with Session() as session:
        docs = (
            session.query(VectorOrm)
            .filter(VectorOrm.file_id == file_id, VectorOrm.embedding == None)
            .all()
        )

    for doc in docs:
        embed_doc.apply_async(kwargs={"table_name": table_name, "doc_id": doc.id})


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
            file = session.query(File).filter(File.id == file_id).one()

            result = markitdown_converter(source=file.path)
            docs = split_markdown(result.markdown)

            VectorOrm = VectorStore.get_vector_model(table_name=table_name)

            for doc in docs:
                row = VectorOrm(
                    text=doc.page_content,
                    file_id=file.id,
                    meta={
                        **doc.metadata,
                    },
                )
                session.add(row)

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
