import asyncio
from fastapi import WebSocket # Changed from Any to actual WebSocket type
from typing import Dict, List, Any
import datetime
import json

from .models import WebSocketMessage # Assuming models.py is in the same 'api' directory

class ConnectionManager:
    def __init__(self):
        # job_id to list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.main_event_loop = None
        try:
            self.main_event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # This might happen if ConnectionManager is initialized outside an active event loop.
            # We can try to get it later or pass it in. For now, this is a basic setup.
            print("Warning: ConnectionManager initialized outside of a running asyncio event loop.")


    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        print(f"WebSocket connected for job_id {job_id}. Client: {websocket.client}. Total clients for job: {len(self.active_connections[job_id])}")
        # Send a confirmation message
        confirm_msg = WebSocketMessage(
            type="connection_ack",
            job_id=job_id,
            message="WebSocket connection established.",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        await websocket.send_json(confirm_msg.model_dump(exclude_none=True))


    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            try:
                self.active_connections[job_id].remove(websocket)
                if not self.active_connections[job_id]: # If list is empty
                    del self.active_connections[job_id]
                print(f"WebSocket disconnected for job_id {job_id}. Client: {websocket.client}. Remaining for job: {len(self.active_connections.get(job_id, []))}")
            except ValueError:
                # Websocket already removed, log or ignore
                print(f"Warning: WebSocket for job {job_id} already removed during disconnect call.")
        else:
            print(f"Warning: Job ID {job_id} not found in active connections during disconnect.")


    async def _send_json_to_websocket(self, websocket: WebSocket, message_dict: dict):
        """Helper to actually send and handle potential errors for a single websocket."""
        try:
            await websocket.send_json(message_dict)
        except Exception as e:
            # Handle errors, e.g., client disconnected abruptly
            print(f"Error sending WebSocket message to client {websocket.client}: {e}")
            # Attempt to remove this specific problematic websocket from its job_id list
            for job_id, conns in list(self.active_connections.items()): # Iterate over a copy for safe removal
                if websocket in conns:
                    self.disconnect(job_id, websocket) # Mark for removal
                    break


    async def broadcast_to_job_async(self, job_id: str, message_model: WebSocketMessage):
        """Asynchronously broadcasts a message to all clients for a specific job_id."""
        if job_id in self.active_connections:
            message_model.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            message_dict = message_model.model_dump(exclude_none=True)

            print(f"Broadcasting (async) to job {job_id}: {str(message_dict)[:200]}...")
            # Create a list of tasks to send messages concurrently
            # Iterate over a copy of the connections list in case of disconnections during broadcast
            tasks = [self._send_json_to_websocket(websocket, message_dict) for websocket in list(self.active_connections.get(job_id, []))]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True) # return_exceptions to not stop on one failure

    def broadcast_to_job_from_thread(self, job_id: str, message_model: WebSocketMessage):
        """
        Safely broadcasts a message from a synchronous thread (like a background task)
        to WebSockets managed by an asyncio event loop.
        """
        if self.main_event_loop and self.main_event_loop.is_running():
            # Add timestamp to the message before sending
            message_model.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # Schedule the async broadcast function to run in the main event loop
            asyncio.run_coroutine_threadsafe(
                self.broadcast_to_job_async(job_id, message_model),
                self.main_event_loop
            )
            # print(f"Scheduled broadcast from thread for job {job_id}: {message_model.type}")
        else:
            print(f"Error: Cannot broadcast from thread. Main event loop not available or not running. Message for job {job_id}: {message_model.type}")


# Global instance of ConnectionManager
manager = ConnectionManager()
