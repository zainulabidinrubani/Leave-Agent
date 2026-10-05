import os
import uuid
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools import ALL_TOOLS, supabase, update_leave_balance
from prompt import SYSTEM_PROMPT

app = FastAPI(title="Leave Agent API")

# Allow the Vercel-hosted frontend (and local dev) to call this API from the browser.
# Replace "*" with your actual Vercel URL once deployed, e.g. "https://leave-desk.vercel.app"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

model = init_chat_model(
    "qwen/qwen3.8-27b",
    model_provider="groq",
    max_tokens=300,
    reasoning_effort=None,
    temperature=0.3,
)

checkpointer = InMemorySaver()
agent = create_agent(model=model, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # pass the same session_id back on each call to continue the conversation


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": payload.message}]},
        config=config,
    )
    reply = result["messages"][-1].content
    return ChatResponse(reply=reply, session_id=session_id)


# 1. Update your imports at the top of main.py to include notify_employee
from tools import ALL_TOOLS, supabase, update_leave_balance, notify_employee

# 2. Replace your existing route with this updated one
@app.get("/leave/action")
def leave_action(request_id: int, action: str):
    if action not in ("approve", "reject"):
        return {"message": "Invalid action."}

    req = supabase.table("leave_requests").select("*").eq("request_id", request_id).execute()
    if not req.data:
        return {"message": f"No leave request found with ID {request_id}."}

    record = req.data[0]

    if record["status"] != "pending":
        return {"message": f"This request was already {record['status']}."}
        
    # --- NEW LOGIC: Fetch employee details to get their email ---
    emp_req = supabase.table("employees").select("first_name, email").eq("employee_id", record["employee_id"]).execute()
    employee_name = "Employee"
    employee_email = "saluman582@gmail.com" # We need a valid email to send this!
    
    if emp_req.data:
        employee_name = emp_req.data[0].get("first_name", "Employee")
        employee_email = emp_req.data[0].get("email", "")

    if action == "approve":
        new_balance = update_leave_balance.invoke({
            "employee_id": record["employee_id"],
            "days_deducted": record["total_days"],
        })
        supabase.table("leave_requests").update({"status": "approved"}).eq("request_id", request_id).execute()
        
        # Send approval email
        if employee_email:
            notify_employee(employee_email, employee_name, "approve", request_id)
            
        return {"message": f"Leave request {request_id} approved. Employee notified. New balance: {new_balance} days."}

    # action == "reject": no balance change
    supabase.table("leave_requests").update({"status": "rejected"}).eq("request_id", request_id).execute()
    
    # Send rejection email
    if employee_email:
        notify_employee(employee_email, employee_name, "reject", request_id)
        
    return {"message": f"Leave request {request_id} rejected. Employee notified."}


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/debug-groq-key")
def debug_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return {"status": "missing", "message": "GROQ_API_KEY is not set at all."}
    return {
        "status": "present",
        "length": len(key),
        "starts_with": key[:6],
        "ends_with": key[-4:],
        "has_leading_or_trailing_whitespace": key != key.strip(),
        "contains_newline": "\n" in key or "\r" in key,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
