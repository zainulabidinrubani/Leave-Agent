import os
import uuid
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    model="open-mistral-7b",      
    model_provider="mistralai",
    max_tokens=300,
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

    if action == "approve":
        new_balance = update_leave_balance.invoke({
            "employee_id": record["employee_id"],
            "days_deducted": record["total_days"],
        })
        supabase.table("leave_requests").update({"status": "approved"}).eq("request_id", request_id).execute()
        return {"message": f"Leave request {request_id} approved. New balance: {new_balance} days."}

    # action == "reject": no balance change, since nothing was deducted at submission
    supabase.table("leave_requests").update({"status": "rejected"}).eq("request_id", request_id).execute()
    return {"message": f"Leave request {request_id} rejected. No leave days were deducted."}


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug-email")
def debug_email():
    import smtplib
    addr = os.getenv("GMAIL_USER")
    pwd = os.getenv("GMAIL_PASS")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(addr, pwd)
        return {"status": "connected and logged in successfully"}
    except Exception as e:
        return {"status": "failed", "error": str(e), "type": type(e).__name__}
