import os
from typing import cast

from fastapi import UploadFile

from schemas.file import ValidatedUploadFile
from settings import PROJECT_ROOT_DIR

SAVE_DIR = "docs"


def validate_upload_file(file: UploadFile):
    """
    Validate the uploaded file.

    Returns a ValidatedUploadFile if the file is valid, otherwise returns an UploadErrorMessage.
    """
    if not file.filename:
        raise ValueError("Uploaded file must have a filename.")

    if not file.size:
        raise ValueError("Uploaded file must have a size.")

    if not file.content_type:
        raise ValueError("Uploaded file must have a content type.")

    return cast(ValidatedUploadFile, file)


def save_file(file: UploadFile):
    save_absolute_dir = os.path.join(PROJECT_ROOT_DIR, SAVE_DIR)

    if not os.path.exists(save_absolute_dir):
        os.makedirs(save_absolute_dir)

    if not file.filename:
        raise ValueError("Uploaded file must have a filename.")

    file_path = os.path.join(save_absolute_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return file_path


def delete_file(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")

    os.remove(file_path)
    return f"File {file_path} deleted successfully."
