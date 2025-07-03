from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class JobIDs(BaseModel):
    job_ids: List[str]

class FileUploadResponse(BaseModel):
    job_id: str
    file_name: str
    status: str
    message: Optional[str] = None

class ProcessingRequest(BaseModel):
    user_goal: str
    # file_path: Optional[str] = None # If job_id is primary way to identify file
    # output_doc_path: Optional[str] = None # Determined by server or default

class JobStatus(BaseModel):
    job_id: str
    status: str # e.g., "queued", "analyzing", "planning", "applying", "validating", "completed", "error"
    current_step: Optional[str] = None # e.g., "Analyzing document", "Tool: create_formatting_plan"
    details: Optional[str] = None # More info, or error message
    progress_percentage: Optional[int] = None # Overall progress estimate if possible
    output_doc_url: Optional[str] = None # URL to download formatted doc when ready
    original_doc_url: Optional[str] = None # URL to download original doc
    # Can add timestamps, etc.

class WebSocketMessage(BaseModel):
    type: str # e.g., "lifecycle", "llm_call_start", "llm_call_end", "tool_start", "tool_end", "data_store", "agent_finish", "error", "info", "warning", "debug"
    event: Optional[str] = None # For lifecycle type, e.g. "agent_init_start", "agent_run_start"
    job_id: Optional[str] = None # To associate message with a job if sent over general WS
    name: Optional[str] = None # For tool_start/tool_end, the tool name
    purpose: Optional[str] = None # For llm_call_start, e.g. "action_planning"
    input_preview: Optional[str] = None
    observation_preview: Optional[str] = None
    variable: Optional[str] = None # For data_store type
    length: Optional[int] = None # For data_store type
    message: Optional[str] = None # General message for info, warning, error, debug
    details: Optional[Any] = None # For error details or other structured data
    final_answer: Optional[str] = None # For agent_finish
    duration_seconds: Optional[float] = None # For llm_call_end
    timestamp: str # ISO format timestamp, added when message is sent

# For the final result of the agent's processing
class FinalProcessingResultData(BaseModel):
    original_doc_path: str # Path on server
    formatted_doc_path: Optional[str] = None # Path on server
    analysis_summary_original: Optional[Dict[str, Any]] = None # e.g. the 'summary' part of analyze_document_structure
    analysis_summary_modified: Optional[Dict[str, Any]] = None
    formatting_plan_actions_count: Optional[int] = None
    validation_report_summary: Optional[Dict[str, Any]] = None # Key fields from validation_result tool's output
    agent_final_answer: str

class FinalProcessingResult(BaseModel):
    job_id: str
    status: str # Should be "completed" or "error"
    message: str
    data: Optional[FinalProcessingResultData] = None
    error_details: Optional[str] = None


# Example of a more detailed change summary if needed later
# class DocumentChange(BaseModel):
#     action_type: str
#     details: Dict[str, Any]
#     status: str # "applied", "skipped", "error"
#     reason: Optional[str] = None

# Example of a more detailed validation result if needed later
# class ValidationResultDetail(BaseModel):
#     goal_achieved: bool
#     confidence_score: Optional[float] = None
#     issues_found: List[str] = []
#     recommendations: List[str] = []
#     assessment: str
