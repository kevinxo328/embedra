"""
Document Processor Module

This module provides a simple document processing pipeline using MarkItDown for document conversion
and LangChain's MarkdownTextSplitter for text chunking. This is a basic implementation that serves
as a foundation for more complex document processing workflows.

Current Implementation:
- Uses MarkItDown to convert various document formats to Markdown
- Applies text splitting on the converted Markdown content
- Simple approach without advanced metadata extraction

Future Enhancements (to be discussed):
- Advanced image processing and OCR integration
- Table structure preservation and extraction
- Document metadata extraction (author, creation date, etc.)
- Multi-modal content handling (images, charts, diagrams)
- Custom chunking strategies based on document structure
- Support for complex document layouts and formatting
"""

from pathlib import Path
from typing import BinaryIO, Optional, Union

import requests
from langchain.text_splitter import MarkdownTextSplitter
from markitdown import MarkItDown

from settings import env

# Initialize MarkItDown converter with plugins disabled for simplicity
# TODO: Consider enabling plugins for enhanced document processing capabilities
md = MarkItDown(enable_plugins=False)


def markitdown_converter(
    source: Union[str, BinaryIO, requests.Response, Path],
    verify: Optional[bool] = None,
    **kwargs,
):
    """
    Convert various document formats to Markdown using MarkItDown.

    This is a simple wrapper around MarkItDown's convert method that handles
    multiple document formats including PDF, DOCX, PPTX, etc.

    #### Args:
    - source (Union[str, BinaryIO, requests.Response, Path]): The source file to convert.
    - verify (Optional[bool]): Whether to verify SSL certificates when fetching remote files.
      Defaults to None, which uses the `APP_ENVIRONMENT` setting from the environment.
      If `APP_ENVIRONMENT` is "production", SSL verification is enabled.
    - **kwargs: Additional keyword arguments passed to MarkItDown's convert method.

    Note:
        This is a basic implementation. Future versions may include:
        - Pre-processing for better text extraction
        - Custom handling for images and tables
        - Metadata preservation from source documents
    """

    # Determine SSL verification based on environment settings
    if verify == False or (env.APP_ENVIRONMENT != "production" and verify is None):
        if isinstance(source, str) and (
            source.startswith("http") or source.startswith("https")
        ):

            source = requests.get(source, verify=False)

    return md.convert(source, **kwargs)


def split_markdown(
    markdown: str, chunk_size: int = 300, chunk_overlap: int = 50, **kwargs
):
    """
    Split Markdown text into chunks using LangChain's MarkdownTextSplitter.

    This function takes Markdown content and splits it into smaller, manageable chunks
    while preserving the document structure and formatting.

    Args:
        markdown (str): The Markdown content to be split
        **kwargs: Arguments passed to MarkdownTextSplitter()
                 Common arguments include:
                 - chunk_size: Maximum size of each chunk
                 - chunk_overlap: Number of characters to overlap between chunks
                 - length_function: Function to calculate chunk length

    Returns:
        List[Document]: List of LangChain Document objects containing the split content

    Note:
        Current implementation uses basic Markdown splitting. Future enhancements may include:
        - Semantic chunking based on document structure
        - Preservation of table and image references
        - Custom splitting strategies for different document types
        - Integration with document metadata for better context preservation
    """
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs
    )
    return splitter.create_documents([markdown])
