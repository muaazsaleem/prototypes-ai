import os

def list_files(directory):
    """Lists all files in a directory."""
    return os.listdir(directory)

def get_file_size(filepath):
    """Returns the size of a file in bytes."""
    return os.path.getsize(filepath)
