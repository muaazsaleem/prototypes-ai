import asyncio
from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

# Import our existing models and logic
from models import Workflow, WorkflowNode, NodeType
from nodes import run_node

# Since we are in a workflow, we must use activities for side effects (like calling Gemini or Fetching APIs)
@workflow.defn
class NaturalLanguageWorkflow:
    @workflow.run
    async def run(self, workflow_data: dict) -> dict:
        # Convert dict back to Pydantic model
        wf = Workflow.model_validate(workflow_data)
        results: Dict[str, str] = {}
        
        # We use a simple wave-based execution similar to our local executor,
        # but orchestrated by Temporal.
        from executor import _build_execution_waves
        waves = _build_execution_waves(wf)
        
        for wave in waves:
            # Execute all nodes in the wave in parallel using Temporal activities
            tasks = []
            for node in wave:
                inputs = {dep: results[dep] for dep in node.depends_on}
                tasks.append(
                    workflow.execute_activity(
                        "run_node_activity",
                        [node.model_dump(), inputs],
                        start_to_close_timeout=timedelta(minutes=5),
                    )
                )
            
            wave_results = await asyncio.gather(*tasks)
            for node, result in zip(wave, wave_results):
                results[node.id] = result
                
        return results

async def run_node_activity(node_data: dict, inputs: dict) -> str:
    """Temporal activity that wraps our existing run_node logic."""
    from google import genai
    import os
    from cache import PromptCacheManager
    from models import WorkflowNode
    
    node = WorkflowNode.model_validate(node_data)
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    # Note: Prompt caching might need careful handling in distributed activities
    cache_manager = PromptCacheManager(client, os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    
    chunks = []
    async for chunk in run_node(node, inputs, client, cache_manager):
        chunks.append(chunk)
    return "".join(chunks)

async def main():
    # This is a placeholder for how one would start the worker
    # In a real app, this runs in a separate process
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="nl-workflow-queue",
        workflows=[NaturalLanguageWorkflow],
        activities=[run_node_activity],
    )
    print("Temporal Worker started...")
    await worker.run()

if __name__ == "__main__":
    # To actually run this, you'd need a Temporal server running
    # asyncio.run(main())
    pass
