"""AgentBench Standard Models.

This module defines the Pydantic models for AgentBench-compliant AI modules.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# =============================================================================
# Input Models
# =============================================================================

# Supported input types for multimodal content
InputType = Literal['text', 'image', 'audio', 'document', 'video']


class InputItem(BaseModel):
    """Multimodal input item for agent requests."""

    type: InputType = Field(
        ..., description='Content type: text, image, audio, document, video'
    )
    content: str = Field(
        ..., description='Plain text or base64 encoded content'
    )
    filename: str | None = Field(
        None, description='Original filename for non-text content'
    )
    mime_type: str | None = Field(
        None, description='MIME type (e.g., image/png)'
    )


class RunRequest(BaseModel):
    """Request for /run and /run_debug endpoints."""

    input: list[InputItem] = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    model: str | None = Field(None, description='Optional model override')


# =============================================================================
# Output Models
# =============================================================================


class ActionTaken(BaseModel):
    """Action executed by the agent."""

    tool: str
    success: bool
    error: str | None = None


class FinalOutput(BaseModel):
    """Final output from the agent."""

    message: str
    state: dict[str, Any] | None = None
    actions_taken: list[ActionTaken] | None = None


class Metrics(BaseModel):
    """Execution metrics."""

    latency_ms: float
    tokens_used: int | None = None
    cost_estimate: float | None = None


class RunResponse(BaseModel):
    """Response for /run endpoint."""

    conversation_id: str
    final_output: FinalOutput
    metrics: Metrics | None = None


# =============================================================================
# Debug Models
# =============================================================================


class LLMCall(BaseModel):
    """LLM invocation details."""

    model: str
    input_tokens: int
    output_tokens: int


class PromptDebug(BaseModel):
    """Debug information for prompts."""

    state_key: str | None = None
    state_value: str | None = None
    base_system_prompt: str | None = None
    final_system_prompt_used: str | None = None


class TrajectoryStage(BaseModel):
    """Single stage in the execution trajectory."""

    stage_id: str
    type: str = Field(
        ..., description='agent, executor, router, memory, custom'
    )
    sequence: int
    prompt_debug: PromptDebug | None = None
    llm_calls: list[LLMCall] | None = None
    output: dict[str, Any] | None = None
    errors: list[str] | None = None
    latency_ms: float


class DebugMetrics(BaseModel):
    """Extended metrics for debug mode."""

    total_latency_ms: float
    total_tokens: dict[str, int] | None = None
    llm_calls: int


class RunDebugResponse(BaseModel):
    """Response for /run_debug endpoint."""

    conversation_id: str
    final_output: FinalOutput
    trajectory: list[TrajectoryStage]
    metrics: DebugMetrics


# =============================================================================
# Metadata Models
# =============================================================================


class Capabilities(BaseModel):
    """Module capabilities declaration."""

    supports_multi_stage: bool = False
    supports_dynamic_system_prompt: bool = False
    supports_cross_model: bool = False
    supports_jailbreak_tests: bool = False


class PipelineStage(BaseModel):
    """Pipeline stage definition."""

    id: str
    type: str = Field(
        ..., description='agent, executor, router, memory, custom'
    )
    model_configurable: bool = False


class Pipeline(BaseModel):
    """Pipeline configuration."""

    is_monolithic: bool = True
    stages: list[PipelineStage]


class DynamicPromptMapping(BaseModel):
    """State-based prompt mapping."""

    state_value: str
    base_system_prompt: str
    expected_context_keys: list[str] | None = None


class DynamicPrompts(BaseModel):
    """Dynamic prompts configuration."""

    state_key: str
    mapping: list[DynamicPromptMapping]


class ToolExposed(BaseModel):
    """Tool exposed by the agent."""

    name: str
    description: str
    parameters_schema: dict[str, str] | None = None


class InputTypes(BaseModel):
    """Multimodal input configuration."""

    supported_types: list[str] = Field(default_factory=lambda: ['text'])
    allowed_formats: dict[str, list[str]] | None = None
    max_file_size: int | None = None


class MetadataResponse(BaseModel):
    """Response for /metadata endpoint."""

    module_id: str
    version: str
    description: str | None = None
    capabilities: Capabilities
    pipeline: Pipeline
    dynamic_prompts: DynamicPrompts | None = None
    tools_exposed: list[ToolExposed] | None = None
    input_types: InputTypes | None = None
    models_supported: list[str] | None = None
