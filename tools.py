import os
import time
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from supabase import create_client
from langchain.tools import tool

load_dotenv(override=True)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


@tool
def get_emp_info(query: str):
    "When user enter employee_id, first_name,department_id use this tool the full information index()"
    res = supabase.table("employees").select("employee_id, first_name, last_name,department_id,annual_leave_balance").execute()
    if query in [item['employee_id'] for item in res.data]:
        return [item for item in res.data if item['employee_id'] == query]
    elif query in [item['first_name'] for item in res.data]:
        return [item for item in res.data if item['first_name'] == query]
    else:
        return "Employee not found"


@tool
def get_leave_balance(query: int):
    "when user give you annual_leave balance then comprare the and tell is he is eliglbe for leave or not"
    if query > 0:
        return "You are eligible for leave"
    else:
        return "You are not eligible for leave"


@tool
def current_date():
    "Use this this tool to find current date and time"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


@tool
def check_leave_entires():
    """Retrieve all leave request entries from the database."""
    res = supabase.table("leave_requests").select("*").execute()
    return res.data if res.data else "No leave requests found."


@tool
def leave_request(request_id: int, employee_id: str, start_date: str, end_date: str, total_days: str, reason: str):
    "When user Leave elliglble for leave this tools for add leave request"
    res = supabase.table("leave_requests").insert({
        "request_id": request_id,
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "status": "pending",
        "reason": reason,
        "request_date": f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
    }).execute()
    return res.data[0]["request_id"]


@tool
def update_leave_balance(employee_id: str, days_deducted: int):
    "Update employee's leave balance after approval"
    res = supabase.table("employees").select("annual_leave_balance").eq("employee_id", employee_id).execute()
    current_balance = res.data[0]["annual_leave_balance"]
    new_balance = current_balance - days_deducted
    supabase.table("employees").update({"annual_leave_balance": new_balance}).eq("employee_id", employee_id).execute()
    return new_balance


@tool
def update_leave_balance_after_rejection(employee_id: str, days_deducted: int):
    "Update employee's leave balance after rejection"
    res = supabase.table("employees").select("annual_leave_balance").eq("employee_id", employee_id).execute()
    current_balance = res.data[0]["annual_leave_balance"]
    new_balance = current_balance + days_deducted
    supabase.table("employees").update({"annual_leave_balance": new_balance}).eq("employee_id", employee_id).execute()
    return new_balance


@tool
def inform_manger(request_id: int, query: str) -> str:
    "Use this for sending emial and informing the manager, with approve/reject links for the given request_id"
    addr = os.getenv("GMAIL_USER")
    pwd = os.getenv("GMAIL_PASS")

    approve_link = f"{PUBLIC_BASE_URL}/leave/action?request_id={request_id}&action=approve"
    reject_link = f"{PUBLIC_BASE_URL}/leave/action?request_id={request_id}&action=reject"

    msg = EmailMessage()
    msg["From"] = addr
    msg["To"] = "fiverrzain03@gmail.com"
    msg["Subject"] = "New Leave request"
    msg.set_content(f"{query}\n\nApprove: {approve_link}\nReject: {reject_link}")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(addr, pwd)
        smtp.send_message(msg)
    return "Email sent to manager"


ALL_TOOLS = [
    get_emp_info,
    get_leave_balance,
    current_date,
    check_leave_entires,
    leave_request,
    update_leave_balance,
    inform_manger,
    update_leave_balance_after_rejection,
]
