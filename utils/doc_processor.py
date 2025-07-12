from markitdown import MarkItDown

md = MarkItDown(enable_plugins=False)  # Set to True to enable plugins


def markitdown_converter(**kwargs):
    return md.convert(**kwargs)
