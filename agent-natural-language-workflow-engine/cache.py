import hashlib

from google import genai
from google.genai import types


class PromptCacheManager:
    """Manages creation and reuse of Gemini context-cache entries for shared system prompts.

    Ensures that identical system prompts are uploaded once and referenced by name
    across multiple nodes, reducing token usage and latency for large instructions.
    """

    def __init__(self, client: genai.Client, model: str):
        """Initialises the cache manager with a Gemini client and specific model ID.

        The model ID must be consistent between the cache creation and the
        generation calls that consume it.
        """
        self._client = client
        self._model = model
        # map sha256 hash of prompt text to the Gemini resource name
        self._store: dict[str, str] = {}

    def get_or_create(self, system_prompt: str) -> str | None:
        """Returns the resource name for a cached prompt, creating it if it doesn't exist.

        Calculates a hash of the prompt for lookup. If the API call to create the
        cache fails (e.g., due to length or region restrictions), returns None
        to signal the caller should use an inline system instruction instead.
        """
        key = hashlib.sha256(system_prompt.encode()).hexdigest()
        if key in self._store:
            return self._store[key]

        try:
            # create a cache resource that expires after 1 hour
            cache = self._client.caches.create(
                model=self._model,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_prompt,
                    ttl="3600s",
                ),
            )
            self._store[key] = cache.name
            return cache.name
        except Exception as exc:
            # failure to cache is non-fatal; the system falls back to inline prompts
            print(
                f"[cache] prompt cache unavailable ({exc}); falling back to inline system prompt"
            )
            return None
