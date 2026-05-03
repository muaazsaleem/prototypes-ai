```python
import uuid
import random
import os
import json

# Define constants
CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
DEFAULT_REPLICAS = 3

class GFSChunkServer:
    """
    Simulates a GFS Chunkserver. Stores chunks on a local 'disk' (dictionary).
    """
    def __init__(self, id):
        self.id = id
        self.chunks = {}  # chunk_handle -> data
        print(f"ChunkServer {self.id} initialized.")

    def store_chunk(self, chunk_handle, data):
        """Stores a chunk of data."""
        self.chunks[chunk_handle] = data
        print(f"ChunkServer {self.id}: Stored chunk {chunk_handle}")
        return True

    def get_chunk(self, chunk_handle):
        """Retrieves a chunk of data."""
        if chunk_handle in self.chunks:
            print(f"ChunkServer {self.id}: Retrieved chunk {chunk_handle}")
            return self.chunks[chunk_handle]
        print(f"ChunkServer {self.id}: Chunk {chunk_handle} not found.")
        return None

    def has_chunk(self, chunk_handle):
        """Checks if the chunkserver has a specific chunk."""
        return chunk_handle in self.chunks

class GFSMaster:
    """
    Simulates a GFS Master. Manages file system metadata.
    """
    def __init__(self, chunk_servers):
        self.files = {}  # file_path -> list of chunk_handles
        self.chunk_locations = {}  # chunk_handle -> list of chunkserver_ids
        self.chunk_handles_counter = 0
        self.chunk_servers = chunk_servers  # List of GFSChunkServer objects
        print("Master initialized.")

    def _generate_chunk_handle(self):
        """Generates a unique 64-bit chunk handle."""
        self.chunk_handles_counter += 1
        return f"chunk-{self.chunk_handles_counter}-{uuid.uuid4().hex[:8]}"

    def create_file(self, file_path):
        """Creates a new file in the GFS."""
        if file_path in self.files:
            print(f"Master: File {file_path} already exists.")
            return False
        self.files[file_path] = []
        print(f"Master: Created file {file_path}")
        return True

    def get_file_info(self, file_path):
        """Returns the list of chunk handles for a given file."""
        return self.files.get(file_path)

    def get_chunk_locations(self, chunk_handle):
        """Returns the chunkserver IDs where a chunk is replicated."""
        return self.chunk_locations.get(chunk_handle, [])

    def allocate_chunk(self, file_path):
        """
        Allocates a new chunk for a file and determines its initial placement.
        Returns the chunk handle and the list of chunkserver IDs for replication.
        """
        if file_path not in self.files:
            print(f"Master: File {file_path} does not exist.")
            return None, []

        chunk_handle = self._generate_chunk_handle()
        self.files[file_path].append(chunk_handle)

        # Select chunkservers for replication (simplified: random selection)
        if len(self.chunk_servers) < DEFAULT_REPLICAS:
            print("Warning: Not enough chunkservers for default replication factor.")
            selected_servers = random.sample(self.chunk_servers, len(self.chunk_servers))
        else:
            selected_servers = random.sample(self.chunk_servers, DEFAULT_REPLICAS)

        server_ids = [cs.id for cs in selected_servers]
        self.chunk_locations[chunk_handle] = server_ids
        print(f"Master: Allocated chunk {chunk_handle} for {file_path} on servers: {server_ids}")
        return chunk_handle, server_ids

    def update_chunk_location(self, chunk_handle, chunkserver_id):
        """Updates the master with a new chunk location (e.g., after replication)."""
        if chunk_handle not in self.chunk_locations:
            self.chunk_locations[chunk_handle] = []
        if chunkserver_id not in self.chunk_locations[chunk_handle]:
            self.chunk_locations[chunk_handle].append(chunkserver_id)
            print(f"Master: Updated location for chunk {chunk_handle} to include {chunkserver_id}")

    def delete_file(self, file_path):
        """Deletes a file and its associated chunks."""
        if file_path not in self.files:
            print(f"Master: File {file_path} not found for deletion.")
            return False

        chunk_handles_to_delete = self.files.pop(file_path)
        for chunk_handle in chunk_handles_to_delete:
            # In a real GFS, this would involve marking chunks for garbage collection
            # and eventually instructing chunkservers to delete them.
            # Here, we'll just remove from master's metadata.
            if chunk_handle in self.chunk_locations:
                del self.chunk_locations[chunk_handle]
            print(f"Master: Marked chunk {chunk_handle} for deletion (removed from metadata).")
        print(f"Master: Deleted file {file_path}")
        return True


class GFSClient:
    """
    Simulates a GFS Client. Interacts with the Master and Chunkservers.
    """
    def __init__(self, master, chunk_servers):
        self.master = master
        self.chunk_servers = {cs.id: cs for cs in chunk_servers}
        print("Client initialized.")

    def _get_chunkserver_by_id(self, cs_id):
        """Helper to get a ChunkServer object by its ID."""
        return self.chunk_servers.get(cs_id)

    def write_file(self, file_path, data):
        """Writes data to a file in GFS."""
        print(f"\nClient: Attempting to write file {file_path} with {len(data)} bytes.")
        if not self.master.create_file(file_path):
            # If file already exists, clear its chunks for overwrite (simplified)
            file_chunks = self.master.get_file_info(file_path)
            if file_chunks:
                for chunk_handle in list(file_chunks): # Iterate over a copy
                    self.master.delete_file(file_path) # Simplified: delete and recreate
                    self.master.create_file(file_path)
            else:
                print(f"Client: Could not create file {file_path}.")
                return False

        chunks_data = [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]
        written_chunks = []

        for i, chunk_data in enumerate(chunks_data):
            chunk_handle, target_chunkservers_ids = self.master.allocate_chunk(file_path)
            if not chunk_handle:
                print(f"Client: Failed to allocate chunk for {file_path}.")
                return False

            # Simulate data flow: client pushes to primary, which pushes to secondaries
            # For simplicity, client directly writes to all target chunkservers here.
            successful_writes = 0
            for cs_id in target_chunkservers_ids:
                chunk_server = self._get_chunkserver_by_id(cs_id)
                if chunk_server and chunk_server.store_chunk(chunk_handle, chunk_data):
                    successful_writes += 1
                else:
                    print(f"Client: Failed to write chunk {chunk_handle} to ChunkServer {cs_id}")

            if successful_writes < DEFAULT_REPLICAS:
                print(f"Client: Warning: Chunk {chunk_handle} written to only {successful_writes} servers (expected {DEFAULT_REPLICAS}).")
            written_chunks.append(chunk_handle)

        print(f"Client: Successfully wrote {len(written_chunks)} chunks to file {file_path}.")
        return True

    def read_file(self, file_path):
        """Reads data from a file in GFS."""
        print(f"\nClient: Attempting to read file {file_path}.")
        file_chunks = self.master.get_file_info(file_path)
        if not file_chunks:
            print(f"Client: File {file_path} not found.")
            return None

        full_data = b""
        for chunk_handle in file_chunks:
            chunk_locations = self.master.get_chunk_locations(chunk_handle)
            if not chunk_locations:
                print(f"Client: No locations found for chunk {chunk_handle}. Data might be lost.")
                return None

            # Try to read from any available replica
            chunk_data = None
            for cs_id in chunk_locations:
                chunk_server = self._get_chunkserver_by_id(cs_id)
                if chunk_server:
                    chunk_data = chunk_server.get_chunk(chunk_handle)
                    if chunk_data:
                        full_data += chunk_data
                        break
            if chunk_data is None:
                print(f"Client: Failed to retrieve chunk {chunk_handle} from any available chunkserver.")
                return None

        print(f"Client: Successfully read {len(full_data)} bytes from file {file_path}.")
        return full_data

    def delete_file(self, file_path):
        """Deletes a file from GFS."""
        print(f"\nClient: Attempting to delete file {file_path}.")
        return self.master.delete_file(file_path)


if __name__ == "__main__":
    print("--- GFS Simulation Demo ---")

    # 1. Initialize Chunkservers
    cs1 = GFSChunkServer("cs-1")
    cs2 = GFSChunkServer("cs-2")
    cs3 = GFSChunkServer("cs-3")
    cs4 = GFSChunkServer("cs-4") # An extra chunkserver for more robust replication
    chunk_servers = [cs1, cs2, cs3, cs4]

    # 2. Initialize Master
    master = GFSMaster(chunk_servers)

    # 3. Initialize Client
    client = GFSClient(master, chunk_servers)

    # --- Demo Operations ---

    # Test 1: Write a small file
    file_path_1 = "/user/data/report.txt"
    file_content_1 = b"This is a short report for the GFS demo. It should fit in one chunk."
    client.write_file(file_path_1, file_content_1)

    # Test 2: Read the small file
    read_content_1 = client.read_file(file_path_1)
    if read_content_1 == file_content_1:
        print(f"Demo: Read content matches original for {file_path_1}.")
    else:
        print(f"Demo: Read content MISMATCH for {file_path_1}.")

    # Test 3: Write a larger file (will span multiple chunks)
    file_path_2 = "/user/logs/application.log"
    # Create content that is larger than CHUNK_SIZE
    file_content_2 = b"A" * (CHUNK_SIZE + 100) + b"B" * (CHUNK_SIZE // 2)
    client.write_file(file_path_2, file_content_2)

    # Test 4: Read the larger file
    read_content_2 = client.read_file(file_path_2)
    if read_content_2 == file_content_2:
        print(f"Demo: Read content matches original for {file_path_2}.")
    else:
        print(f"Demo: Read content MISMATCH for {file_path_2}.")
        print(f"Expected length: {len(file_content_2)}, Actual length: {len(read_content_2) if read_content_2 else 'None'}")


    # Test 5: Overwrite an existing file
    print("\n--- Overwriting file_path_1 ---")
    new_content_1 = b"This is the NEW content for the report file."
    client.write_file(file_path_1, new_content_1)
    read_new_content_1 = client.read_file(file_path_1)
    if read_new_content_1 == new_content_1:
        print(f"Demo: Overwritten content matches original for {file_path_1}.")
    else:
        print(f"Demo: Overwritten content MISMATCH for {file_path_1}.")

    # Test 6: Delete a file
    client.delete_file(file_path_1)
    # Try to read the deleted file
    read_deleted_content = client.read_file(file_path_1)
    if read_deleted_content is None:
        print(f"Demo: Successfully confirmed {file_path_1} is deleted.")
    else:
        print(f"Demo: Failed to delete {file_path_1}.")

    # Test 7: Attempt to read a non-existent file
    print("\n--- Attempting to read a non-existent file ---")
    non_existent_file = "/non/existent/file.txt"
    read_non_existent = client.read_file(non_existent_file)
    if read_non_existent is None:
        print(f"Demo: Correctly reported that {non_existent_file} does not exist.")
    else:
        print(f"Demo: Incorrectly read content from {non_existent_file}.")

    print("\n--- GFS Simulation Demo End ---")
```