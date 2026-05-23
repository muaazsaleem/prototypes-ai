from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Enumeration of supported operation types in a workflow."""

    FETCH = "fetch"
    SUMMARIZE = "summarize"
    TRANSLATE = "translate"
    EMAIL = "email"
    TRANSFORM = "transform"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    TEMPORAL_HITL = "temporal_hitl"


class WorkflowNode(BaseModel):
    """Represents a single executable unit within a workflow DAG.

    Contains all metadata needed to route execution, handle dependencies,
    and configure the specific operation through the params dictionary.
    """

    id: str = Field(description="Unique snake_case identifier for the node")
    type: NodeType = Field(description="The kind of operation this node performs")
    description: str = Field(
        description="Human-readable explanation of what this node does"
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Operation-specific parameters, e.g. "
            "{'target_language': 'Spanish'} or {'url': 'https://...'}"
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of nodes whose output this node needs as input; empty = runs immediately",
    )


class Workflow(BaseModel):
    """A complete Directed Acyclic Graph (DAG) defining an automated workflow.

    The engine uses this model to plan execution waves based on the
    dependency structure defined in the nodes.
    """

    name: str = Field(description="Short, descriptive name for the workflow")
    description: str = Field(
        description="One-sentence summary of what the workflow accomplishes"
    )
    nodes: list[WorkflowNode] = Field(
        description=(
            "All nodes in the DAG. "
            "Ordering in this list does not matter — "
            "execution order is determined by depends_on edges."
        )
    )
