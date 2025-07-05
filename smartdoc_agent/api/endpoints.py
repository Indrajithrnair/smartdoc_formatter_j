
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import shutil
import os
import uuid
from typing import Dict, List, Any
import datetime
import asyncio
import json # For process_document_agent_task's result parsing
import traceback

from .models import FileUploadResponse, ProcessingRequest, JobStatus, WebSocketMessage, FinalProcessingResult, FinalProcessingResultData
from smartdoc_agent.core.agent import DocumentFormattingAgent
from ..config import get_groq_api_key
from .websocket_manager import manager

# --- In-Memory Job Store ---
jobs_db: Dict[str, Dict] = {}

# --- Agent Processing Function (to be run in background) ---
def process_document_agent_task(job_id: str, user_goal: str):
    # Simulate getting the current event loop for this background task context
    try:
        loop = asyncio.get_running_loop()
        if manager.main_event_loop is None : # Set it if manager could not get it at startup
            manager.main_event_loop = loop
            print(f"Agent Task for {job_id}: Main event loop captured for manager.")
    except RuntimeError:
        print(f"Agent Task for {job_id}: No running event loop, WebSocket broadcasts from thread might fail.")
        # manager.main_event_loop might remain None if this task is run very early by FastAPI

    job_info = jobs_db.get(job_id)
    if not job_info or job_info["status"] != "queued": # Expecting "queued" now
        error_message = f"Job {job_id} not found or not in 'queued' state for processing. Current state: {job_info.get('status') if job_info else 'N/A'}"
        print(error_message)
        if job_info:
            job_info["status"] = "error"
            job_info["current_step_details"] = error_message
            final_error_result = FinalProcessingResult(
                job_id=job_id, status="error", message=error_message, error_details=error_message
            )
            job_info["final_result_data"] = final_error_result.model_dump()
            ws_err_msg = WebSocketMessage(job_id=job_id, type="job_error", message=error_message, timestamp="")
            manager.broadcast_to_job_from_thread(job_id, ws_err_msg)
        return

    job_info["status"] = "processing"
    job_info["current_step_details"] = "Initializing agent..."
    initial_progress_msg = WebSocketMessage(job_id=job_id, type="status_update", event="processing_start", message="Initializing agent...", timestamp="")
    manager.broadcast_to_job_from_thread(job_id, initial_progress_msg)

    def progress_callback_for_job(data: dict):
        # data is what agent's _emit_progress sends
        ws_message = WebSocketMessage(
            job_id=job_id,
            type=data.get("type", "agent_progress"),
            event=data.get("event"), name=data.get("name"), purpose=data.get("purpose"),
            input_preview=data.get("input_preview"), observation_preview=data.get("observation_preview"),
            variable=data.get("variable"), length=data.get("length"), message=data.get("message"),
            details=data.get("details"), final_answer=data.get("final_answer"),
            duration_seconds=data.get("duration_seconds"), timestamp=""
        )
        manager.broadcast_to_job_from_thread(job_id, ws_message)

    try:
        agent = DocumentFormattingAgent(progress_callback=progress_callback_for_job)

        original_doc_path = job_info["original_file_path"]
        # Use a job-specific output directory
        job_output_dir = os.path.join(TEMP_UPLOAD_DIR, job_id, "formatted")
        os.makedirs(job_output_dir, exist_ok=True)
        # Keep original filename for the formatted version too for user convenience
        output_doc_filename = job_info.get("original_file_name", "formatted_document.docx")
        base_name, ext_name = os.path.splitext(output_doc_filename)
        output_doc_path = os.path.join(job_output_dir, f"{base_name}_formatted{ext_name}")

        job_info["output_file_path"] = output_doc_path

        final_agent_response_str = agent.run(
            user_query=user_goal,
            document_path=original_doc_path,
            output_document_path=output_doc_path
        )

        # Prepare FinalProcessingResultData
        original_analysis_summary, modified_analysis_summary, plan_actions_count, validation_summary_dict = None, None, None, {}

        if agent.full_original_analysis_json:
            try: original_analysis_summary = json.loads(agent.full_original_analysis_json).get("summary")
            except: pass

        if agent.full_modified_analysis_json: # This should be populated if agent ran full cycle
            try: modified_analysis_summary = json.loads(agent.full_modified_analysis_json).get("summary")
            except: pass

        if agent.current_formatting_plan_json:
            try: plan_actions_count = len(json.loads(agent.current_formatting_plan_json))
            except: pass

        # Try to parse the agent's final response if it's a JSON validation report
        # This assumes the last step was validation and it returned its JSON report as the final answer string
        if "AgentFinish:" in final_agent_response_str: # From the agent's own logging of AgentFinish
            final_answer_content = final_agent_response_str.split("AgentFinish:", 1)[-1].strip()
            try:
                # If validate_formatting_result returns JSON as string, it needs parsing
                validation_output = json.loads(final_answer_content)
                if isinstance(validation_output, dict) and "overall_assessment" in validation_output : # check for key field
                    validation_summary_dict = validation_output
                else: # It's not the expected validation JSON, use raw
                    validation_summary_dict = {"raw_final_answer": final_answer_content}
            except json.JSONDecodeError: # Not JSON
                 validation_summary_dict = {"raw_final_answer": final_agent_response_str} # Use the full string if not JSON
        else: # Not an AgentFinish with expected structure
            validation_summary_dict = {"raw_final_answer": final_agent_response_str}


        result_data_obj = FinalProcessingResultData(
            original_doc_path=original_doc_path,
            formatted_doc_path=output_doc_path if os.path.exists(output_doc_path) else None,
            analysis_summary_original=original_analysis_summary,
            analysis_summary_modified=modified_analysis_summary,
            formatting_plan_actions_count=plan_actions_count,
            validation_report_summary=validation_summary_dict,
            agent_final_answer=final_agent_response_str
        )

        final_status_message = "Processing complete."
        if not os.path.exists(output_doc_path):
            final_status_message = "Processing completed, but output file was not generated."

        jobs_db[job_id].update({
            "status": "completed",
            "current_step_details": final_status_message,
            "final_result_data": result_data_obj.dict()
        })
        final_ws_msg = WebSocketMessage(job_id=job_id, type="job_completed", message=final_status_message, data=result_data_obj.dict(), timestamp="")
        manager.broadcast_to_job_from_thread(job_id, final_ws_msg)

    except Exception as e:
        print(f"Error during agent processing for job {job_id}: {e}")
        detailed_error = traceback.format_exc()
        error_message_for_user = f"Agent processing error: {str(e)}"
        jobs_db[job_id].update({
            "status": "error",
            "current_step_details": error_message_for_user,
            "final_result_data": FinalProcessingResultData(
                original_doc_path=jobs_db[job_id].get("original_file_path", "N/A"), # Try to get original path
                agent_final_answer=f"Error: {str(e)}",
                # No other summaries available on error typically
            ).dict(exclude_none=True), # Store as dict
            "error_details_for_log": detailed_error # For server logs, not necessarily for user
        })
        final_ws_err_msg = WebSocketMessage(job_id=job_id, type="job_error", message=error_message_for_user, details=detailed_error, timestamp="")
        manager.broadcast_to_job_from_thread(job_id, final_ws_err_msg)


router = APIRouter()

TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@router.post("/documents/upload", response_model=FileUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .docx allowed.")

    job_id = str(uuid.uuid4())
    original_file_name = file.filename

    job_dir = os.path.join(TEMP_UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    original_file_path = os.path.join(job_dir, "original.docx")

    try:
        with open(original_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        # Clean up job_dir if save fails?
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")
    finally:
        file.file.close()

    jobs_db[job_id] = {
        "status": "uploaded",
        "original_file_path": original_file_path,
        "original_file_name": original_file_name,
        "output_file_path": None, # Will be set by agent task
        "user_goal": None,
        "current_step_details": "File uploaded successfully. Ready for processing.",
        "final_result_data": None, # Will be populated by agent task
        "error_details_for_log": None
    }

    return FileUploadResponse(
        job_id=job_id,
        file_name=original_file_name,
        status="uploaded",
        message="File uploaded successfully. Ready for processing."
    )

@router.post("/documents/process/{job_id}", status_code=202)
async def process_document_endpoint(job_id: str, request: ProcessingRequest, background_tasks: BackgroundTasks):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    job_info = jobs_db[job_id]
    if job_info["status"] != "uploaded":
        # Allow reprocessing if it was 'completed' or 'error'? For now, require 'uploaded'.
        raise HTTPException(status_code=400, detail=f"Document for job {job_id} is not in 'uploaded' state. Current state: {job_info['status']}")

    job_info["user_goal"] = request.user_goal
    job_info["status"] = "queued"
    job_info["current_step_details"] = "Queued for processing."
    job_info["final_result_data"] = None # Clear previous results if any for reprocessing
    job_info["error_details_for_log"] = None


    background_tasks.add_task(process_document_agent_task, job_id, request.user_goal)

    return {"message": "Document processing initiated.", "job_id": job_id}


@router.get("/documents/{job_id}/status", response_model=JobStatus) # Using JobStatus as response
async def get_job_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    job_info = jobs_db[job_id]

    output_doc_url = None
    # Only provide download URL if job is completed AND output file path exists
    if job_info["status"] == "completed" and job_info.get("output_file_path") and os.path.exists(job_info["output_file_path"]):
        output_doc_url = f"/api/documents/{job_id}/download/formatted"

    original_doc_url = f"/api/documents/{job_id}/download/original" if job_info.get("original_file_path") else None

    # Extract a summary from final_result_data for the 'details' field
    details_summary = job_info.get("current_step_details", "N/A")
    if job_info.get("final_result_data"):
        final_data = job_info["final_result_data"]
        if isinstance(final_data, dict) and "agent_final_answer" in final_data :
             details_summary = final_data["agent_final_answer"]
        elif isinstance(final_data, FinalProcessingResultData): # Should be dict from .model_dump()
             details_summary = final_data.agent_final_answer


    return JobStatus(
        job_id=job_id,
        status=job_info["status"],
        current_step=job_info.get("current_step_details", "N/A"), # More granular step from agent
        details=details_summary, # Main agent message or error
        output_doc_url=output_doc_url,
        original_doc_url=original_doc_url
    )

@router.get("/documents/{job_id}/download/formatted")
async def download_formatted_document(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    job_info = jobs_db[job_id]

    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job {job_id} not completed. Status: {job_info['status']}")

    file_path = job_info.get("output_file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Formatted document file not found or path is missing.")

    base, ext = os.path.splitext(job_info.get("original_file_name", f"{job_id}_formatted.docx"))
    download_filename = f"{base}_formatted_by_agent{ext}" # Make it more distinct

    return FileResponse(path=file_path, filename=download_filename, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

@router.get("/documents/{job_id}/download/original")
async def download_original_document(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    job_info = jobs_db[job_id]

    file_path = job_info.get("original_file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original document file not found or path is missing.")

    return FileResponse(path=file_path, filename=job_info.get("original_file_name", f"{job_id}_original.docx"), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@router.websocket("/ws/processing-updates/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    if manager.main_event_loop is None:
        try:
            manager.main_event_loop = asyncio.get_running_loop()
            print(f"WebSocket Endpoint: Main event loop captured for job {job_id}")
        except RuntimeError:
            print(f"Error: WebSocket Endpoint for job {job_id} could not get running event loop for manager.")
            await websocket.close(code=1011)
            return

    await manager.connect(job_id, websocket)
    try:
        while True:
            # This loop keeps the connection open.
            # For a simple broadcast-only WebSocket, you might just await a long sleep or a disconnect signal.
            # If you need to receive messages from client (e.g. to confirm receipt or send commands like 'pause')
            # data = await websocket.receive_text()
            # print(f"WS received from client for job {job_id}: {data}") # Example
            await asyncio.sleep(3600) # Keep connection alive for an hour, or until disconnect
    except WebSocketDisconnect:
        print(f"Client for job {job_id} disconnected (WebSocketDisconnect).")
    except Exception as e:
        print(f"Exception in WebSocket connection for job {job_id}: {e}")
    finally: # Ensure disconnect is called
        manager.disconnect(job_id, websocket)
        print(f"WebSocket for job {job_id} connection closed and cleaned up.")
