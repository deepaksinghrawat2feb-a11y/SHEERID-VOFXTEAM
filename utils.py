"""
Utility functions for the bot
"""

import re
from datetime import datetime
from typing import Optional, Dict, List
import json

# Branch mapping similar to main.py
BRANCH_ORG_MAP = {
    "Army": {"id": 4070, "name": "Army"},
    "Air Force": {"id": 4073, "name": "Air Force"},
    "Navy": {"id": 4072, "name": "Navy"},
    "Marine Corps": {"id": 4071, "name": "Marine Corps"},
    "Coast Guard": {"id": 4074, "name": "Coast Guard"},
    "Space Force": {"id": 4544268, "name": "Space Force"},
    "Army National Guard": {"id": 4075, "name": "Army National Guard"},
    "Army Reserve": {"id": 4076, "name": "Army Reserve"},
    "Air National Guard": {"id": 4079, "name": "Air National Guard"},
    "Air Force Reserve": {"id": 4080, "name": "Air Force Reserve"},
    "Navy Reserve": {"id": 4078, "name": "Navy Reserve"},
    "Marine Corps Reserve": {"id": 4077, "name": "Marine Corps Forces Reserve"},
    "Coast Guard Reserve": {"id": 4081, "name": "Coast Guard Reserve"},
}


def parse_veteran_line(line: str) -> Optional[Dict]:
    """Parse veteran data line"""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        return None
        
    # Parse branch
    branch = match_branch(parts[2])
    
    # Validate dates
    if not validate_date(parts[3]) or (len(parts) > 4 and not validate_date(parts[4])):
        return None
        
    return {
        "firstName": parts[0],
        "lastName": parts[1],
        "branch": branch,
        "birthDate": parts[3],
        "dischargeDate": parts[4] if len(parts) > 4 else "2025-01-01",
        "organization": BRANCH_ORG_MAP.get(branch, BRANCH_ORG_MAP["Army"])
    }


def match_branch(input_str: str) -> str:
    """Map input string to branch name"""
    normalized = input_str.upper().replace("US ", "").strip()
    
    for branch in BRANCH_ORG_MAP:
        if branch.upper() == normalized:
            return branch
    
    # Fuzzy matching
    if "MARINE" in normalized and "RESERVE" not in normalized:
        return "Marine Corps"
    if "ARMY" in normalized and "NATIONAL" in normalized:
        return "Army National Guard"
    if "ARMY" in normalized and "RESERVE" in normalized:
        return "Army Reserve"
    if "ARMY" in normalized:
        return "Army"
    if "NAVY" in normalized and "RESERVE" in normalized:
        return "Navy Reserve"
    if "NAVY" in normalized:
        return "Navy"
    if "AIR" in normalized and "NATIONAL" in normalized:
        return "Air National Guard"
    if "AIR" in normalized and "RESERVE" in normalized:
        return "Air Force Reserve"
    if "AIR" in normalized:
        return "Air Force"
    if "COAST" in normalized and "RESERVE" in normalized:
        return "Coast Guard Reserve"
    if "COAST" in normalized:
        return "Coast Guard"
    if "SPACE" in normalized:
        return "Space Force"
    
    return "Army"


def validate_date(date_str: str) -> bool:
    """Validate date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def format_veteran_data(veteran: Dict) -> str:
    """Format veteran data for display"""
    return (
        f"*Name:* {veteran['firstName']} {veteran['lastName']}\n"
        f"*Branch:* {veteran['branch']}\n"
        f"*Birth Date:* {veteran['birthDate']}\n"
        f"*Discharge Date:* {veteran['dischargeDate']}"
    )


def generate_report(verifications: List) -> str:
    """Generate verification report"""
    if not verifications:
        return "No verifications found."
        
    report_lines = ["📊 *Verification Report*", ""]
    
    success_count = sum(1 for v in verifications if v.status == "success")
    fail_count = sum(1 for v in verifications if v.status == "failed")
    pending_count = sum(1 for v in verifications if v.status in ["pending", "processing"])
    
    report_lines.extend([
        f"*Total:* {len(verifications)}",
        f"*Success:* {success_count}",
        f"*Failed:* {fail_count}",
        f"*Pending:* {pending_count}",
        ""
    ])
    
    for i, v in enumerate(verifications[:10], 1):
        status_emoji = "✅" if v.status == "success" else "❌" if v.status == "failed" else "🔄"
        report_lines.append(
            f"{i}. {status_emoji} *{v.veteran_name}* - {v.status}"
        )
        
    return "\n".join(report_lines)


def send_log_file(bot, chat_id):
    """Send log file to user"""
    try:
        with open("bot.log", "rb") as f:
            bot.send_document(chat_id=chat_id, document=f, filename="bot_log.txt")
        return True
    except Exception as e:
        print(f"Failed to send log file: {e}")
        return False
