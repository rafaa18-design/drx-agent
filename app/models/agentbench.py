"""AgentBench Standard Models — movidos de app/models.py para app/models/agentbench.py."""

from typing import Any, Literal

from pydantic import BaseModel, Field

InputType = Literal['text', 'image', 'audio', 'document', 'video']


class InputItem(BaseModel):
    type: InputType = Field(..., description='Content type: text, image, audio, document, video')
    content: str = Field(..., description='Plain text or base64 encoded content')
    filename: str | None = Field(None, description='Original filename for non-text content')
    mime_type: str | None = Field(None, description='MIME type (e.g., image/png)')


class RunRequest(BaseModel):
    input: list[InputItem] = Field(..., min_length=1, max_length=20)
    conversation_id: str = Field(..., min_length=1)
    model: str | None = Field(None, description='Optional model override')
    received_at: float | None = Field(None, description='Unix timestamp when the message was received by the connector')


class ActionTaken(BaseModel):
    tool: str
    success: bool
    error: str | None = None


class FinalOutput(BaseModel):
    message: str
    state: dict[str, Any] | None = None
    actions_taken: list[ActionTaken] | None = None


class Metrics(BaseModel):
    latency_ms: float
    tokens_used: int | None = None
    cost_estimate: float | None = None


class RunResponse(BaseModel):
    conversation_id: str
    final_output: FinalOutput
    metrics: Metrics | None = None


class LLMCall(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int


class PromptDebug(BaseModel):
    state_key: str | None = None
    state_value: str | None = None
    base_system_prompt: str | None = None
    final_system_prompt_used: str | None = None


class TrajectoryStage(BaseModel):
    stage_id: str
    type: str = Field(..., description='agent, executor, router, memory, custom')
    sequence: int
    prompt_debug: PromptDebug | None = None
    llm_calls: list[LLMCall] | None = None
    output: dict[str, Any] | None = None
    errors: list[str] | None = None
    latency_ms: float


class DebugMetrics(BaseModel):
    total_latency_ms: float
    total_tokens: dict[str, int] | None = None
    llm_calls: int


class RunDebugResponse(BaseModel):
    conversation_id: str
    final_output: FinalOutput
    trajectory: list[TrajectoryStage]
    metrics: DebugMetrics


class Capabilities(BaseModel):
    supports_multi_stage: bool = False
    supports_dynamic_system_prompt: bool = False
    supports_cross_model: bool = False
    supports_jailbreak_tests: bool = False


class PipelineStage(BaseModel):
    id: str
    type: str = Field(..., description='agent, executor, router, memory, custom')
    model_configurable: bool = False


class Pipeline(BaseModel):
    is_monolithic: bool = True
    stages: list[PipelineStage]


class DynamicPromptMapping(BaseModel):
    state_value: str
    base_system_prompt: str
    expected_context_keys: list[str] | None = None


class DynamicPrompts(BaseModel):
    state_key: str
    mapping: list[DynamicPromptMapping]


class ToolExposed(BaseModel):
    name: str
    description: str
    parameters_schema: dict[str, str] | None = None


class InputTypes(BaseModel):
    supported_types: list[str] = Field(default_factory=lambda: ['text'])
    allowed_formats: dict[str, list[str]] | None = None
    max_file_size: int | None = None


class MetadataResponse(BaseModel):
    module_id: str
    version: str
    description: str | None = None
    capabilities: Capabilities
    pipeline: Pipeline
    dynamic_prompts: DynamicPrompts | None = None
    tools_exposed: list[ToolExposed] | None = None
    input_types: InputTypes | None = None
    models_supported: list[str] | None = None
