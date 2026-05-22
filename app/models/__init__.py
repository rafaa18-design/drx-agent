"""Models — AgentBench Pydantic schemas + SQLAlchemy CRM DRX Advogados."""

# AgentBench Pydantic models (usados pelos routers existentes)
from app.models.agentbench import (
    ActionTaken,
    Capabilities,
    DebugMetrics,
    DynamicPromptMapping,
    DynamicPrompts,
    FinalOutput,
    InputItem,
    InputTypes,
    LLMCall,
    MetadataResponse,
    Metrics,
    Pipeline,
    PipelineStage,
    PromptDebug,
    RunDebugResponse,
    RunRequest,
    RunResponse,
    ToolExposed,
    TrajectoryStage,
)

# CRM SQLAlchemy models
from app.models.appointment import Appointment
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message

__all__ = [
    # AgentBench
    "ActionTaken", "Capabilities", "DebugMetrics", "DynamicPromptMapping",
    "DynamicPrompts", "FinalOutput", "InputItem", "InputTypes", "LLMCall",
    "MetadataResponse", "Metrics", "Pipeline", "PipelineStage", "PromptDebug",
    "RunDebugResponse", "RunRequest", "RunResponse", "ToolExposed", "TrajectoryStage",
    # CRM
    "Lead", "Conversation", "Message", "Appointment",
]
