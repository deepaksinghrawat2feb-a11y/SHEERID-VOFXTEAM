#!/usr/bin/env python3
"""
Veterans Verification Telegram Bot
Integrates with the existing main.py tool
"""

import os
import sys
import json
import subprocess
import threading
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# Local imports
from config import Config, Messages
from database import Database, User, Verification
from utils import (
    format_veteran_data,
    parse_veteran_line,
    validate_date,
    generate_report,
    send_log_file
)

# Add parent directory to path for importing main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Global bot instance
bot_app = None

class VerificationBot:
    def __init__(self):
        self.db = Database()
        self.active_verifications: Dict[int, Dict] = {}  # user_id -> verification data
        self.data_file = "data.txt"
        self.used_file = "used.txt"
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Register user
        db_user = self.db.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Check if admin
        is_admin = user.id in Config.ADMIN_IDS
        
        keyboard = [
            [InlineKeyboardButton("🔍 Start Verification", callback_data="verify")],
            [InlineKeyboardButton("📊 Check Status", callback_data="status")],
            [InlineKeyboardButton("📋 View Data", callback_data="view_data")],
            [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin")] if is_admin else []
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            Messages.WELCOME,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user = update.effective_user
        if user.id in Config.ADMIN_IDS:
            help_text = Messages.HELP + "\n\n" + Messages.ADMIN_HELP
        else:
            help_text = Messages.HELP
            
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - Start verification process"""
        user_id = update.effective_user.id
        
        # Check daily limit
        today_count = self.db.get_verifications_count_today(user_id)
        if today_count >= Config.MAX_USERS_PER_DAY:
            await update.message.reply_text(
                f"⚠️ *Daily limit reached!*\n\n"
                f"You have used {today_count}/{Config.MAX_USERS_PER_DAY} verifications today.\n"
                f"Please try again tomorrow.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        # Check if already verifying
        if user_id in self.active_verifications:
            await update.message.reply_text(
                "🔄 You already have an active verification in progress.\n"
                "Please wait for it to complete or use /cancel to stop it."
            )
            return
            
        # Load available data
        data = self.load_veteran_data()
        if not data:
            await update.message.reply_text(
                "📭 *No veteran data available!*\n\n"
                "Please add veteran data first using /add_data command.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        # Show available data for selection
        keyboard = []
        for i, vet in enumerate(data[:10]):  # Show first 10
            keyboard.append([
                InlineKeyboardButton(
                    f"{vet['firstName']} {vet['lastName']} ({vet['branch']})",
                    callback_data=f"select_{i}"
                )
            ])
            
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📋 *Select Veteran Data*\n\n"
            f"Found {len(data)} records available.\n"
            f"Select one to start verification:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - Check verification status"""
        user_id = update.effective_user.id
        
        # Get recent verifications
        verifications = self.db.get_user_verifications(user_id, limit=5)
        
        if not verifications:
            await update.message.reply_text(
                "📭 No verification history found.\n"
                "Start your first verification with /verify"
            )
            return
            
        status_text = "📊 *Your Verification History*\n\n"
        for i, v in enumerate(verifications, 1):
            status_emoji = "✅" if v.status == "success" else "❌" if v.status == "failed" else "🔄"
            status_text += (
                f"{i}. *{v.veteran_name}*\n"
                f"   Status: {status_emoji} {v.status.upper()}\n"
                f"   Time: {v.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"   ID: `{v.verification_id[:8] if v.verification_id else 'N/A'}`\n\n"
            )
            
        await update.message.reply_text(
            status_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    async def add_data_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_data command - Add veteran data"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text(
                "⛔ *Access Denied*\n\n"
                "This command is only available for administrators.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        await update.message.reply_text(
            "📥 *Add Veteran Data*\n\n"
            "You can add data in two ways:\n\n"
            "1️⃣ *Send .txt file* with format:\n"
            "`FirstName|LastName|Branch|BirthDate|DischargeDate`\n\n"
            "2️⃣ *Send text message* with same format\n\n"
            "Example: `JOHN|SMITH|Army|1990-05-15|2025-06-01`\n\n"
            "Type /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Set state to wait for data
        context.user_data['waiting_for_data'] = True
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - Show bot statistics"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text(
                "⛔ *Access Denied*\n\n"
                "This command is only available for administrators.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        stats = self.db.get_bot_statistics()
        
        stats_text = (
            "📈 *Bot Statistics*\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"✅ Active Users: {stats['active_users']}\n"
            f"📊 Total Verifications: {stats['total_verifications']}\n"
            f"✅ Successful: {stats['success_count']}\n"
            f"❌ Failed: {stats['failed_count']}\n"
            f"🔄 Pending: {stats['pending_count']}\n"
            f"📅 Today's Verifications: {stats['today_count']}\n\n"
            f"🕐 Bot Uptime: {stats['uptime']}\n"
        )
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command - Send message to all users"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("⛔ Access Denied")
            return
            
        if not context.args:
            await update.message.reply_text(
                "📢 *Broadcast Message*\n\n"
                "Usage: `/broadcast Your message here`\n\n"
                "This will send to all active users.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        message = ' '.join(context.args)
        users = self.db.get_all_active_users()
        
        await update.message.reply_text(
            f"📤 Broadcasting to {len(users)} users...\n"
            f"Message: {message[:50]}..."
        )
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.user_id,
                    text=f"📢 *Broadcast Message*\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                success += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                failed += 1
                
        await update.message.reply_text(
            f"✅ Broadcast complete!\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}"
        )
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if waiting for data input
        if context.user_data.get('waiting_for_data'):
            await self.process_data_input(update, context, text)
            return
            
        # Check if it's veteran data format
        if '|' in text and len(text.split('|')) >= 4:
            await self.process_single_data(update, context, text)
            return
            
        # Default response
        await update.message.reply_text(
            "🤖 *Veterans Verification Bot*\n\n"
            "Use /start to begin\n"
            "Use /help for instructions\n"
            "Use /verify to start verification",
            parse_mode=ParseMode.MARKDOWN
        )
        
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("⛔ Access Denied")
            return
            
        document = update.message.document
        file_name = document.file_name
        
        if not file_name.endswith('.txt'):
            await update.message.reply_text("❌ Please upload a .txt file")
            return
            
        # Download file
        file = await context.bot.get_file(document.file_id)
        temp_path = f"temp_{user_id}_{file_name}"
        
        await file.download_to_drive(temp_path)
        
        # Process file
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        added = self.add_veteran_data_from_text(content)
        
        # Cleanup
        os.remove(temp_path)
        
        await update.message.reply_text(
            f"✅ File processed successfully!\n"
            f"Added {added} new veteran records."
        )
        
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == "verify":
            await self.verify_command(query, context)
        elif data == "status":
            await self.status_command(query, context)
        elif data == "view_data":
            await self.show_data_list(query, context)
        elif data == "admin":
            await self.show_admin_panel(query, context)
        elif data.startswith("select_"):
            index = int(data.split("_")[1])
            await self.start_verification(query, context, index)
        elif data == "cancel":
            await query.edit_message_text("❌ Operation cancelled.")
            
    async def start_verification(self, query, context, data_index):
        """Start verification for selected data"""
        user_id = update.effective_user.id
        
        # Load data
        data = self.load_veteran_data()
        if data_index >= len(data):
            await query.edit_message_text("❌ Invalid selection!")
            return
            
        veteran = data[data_index]
        
        # Store in active verifications
        self.active_verifications[user_id] = {
            'veteran': veteran,
            'message_id': query.message.message_id,
            'start_time': datetime.now(),
            'status': 'starting'
        }
        
        # Create verification record
        verification = self.db.create_verification(
            user_id=user_id,
            veteran_name=f"{veteran['firstName']} {veteran['lastName']}",
            veteran_data=veteran
        )
        
        # Update message
        await query.edit_message_text(
            f"🔄 *Starting Verification*\n\n"
            f"*Name:* {veteran['firstName']} {veteran['lastName']}\n"
            f"*Branch:* {veteran['branch']}\n"
            f"*DOB:* {veteran['birthDate']}\n"
            f"*Discharge:* {veteran['dischargeDate']}\n\n"
            f"⏳ Please wait while we process...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Run verification in background
        asyncio.create_task(
            self.run_verification(user_id, verification.id, context)
        )
        
    async def run_verification(self, user_id, verification_id, context):
        """Run verification process in background"""
        try:
            verification = self.db.get_verification(verification_id)
            veteran = self.active_verifications[user_id]['veteran']
            
            # Update status
            self.db.update_verification_status(verification_id, "processing")
            
            # Create data line for main.py
            data_line = f"{veteran['firstName']}|{veteran['lastName']}|{veteran['branch']}|{veteran['birthDate']}|{veteran['dischargeDate']}"
            
            # Save to temp file
            temp_file = f"temp_{user_id}.txt"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(data_line)
                
            # Run main.py with subprocess
            cmd = [
                sys.executable, "main.py",
                "--no-dedup"  # Disable dedup since we handle it in bot
            ]
            
            # Update status message
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=self.active_verifications[user_id]['message_id'],
                text=(
                    f"🔄 *Verification In Progress*\n\n"
                    f"*Name:* {veteran['firstName']} {veteran['lastName']}\n"
                    f"*Branch:* {veteran['branch']}\n\n"
                    f"📤 Submitting data to SheerID...\n"
                    f"⏳ This may take 1-2 minutes..."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Execute verification
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Read output in real-time
            output_lines = []
            for line in process.stdout:
                output_lines.append(line)
                # Send updates based on output
                if "Creating verification request" in line:
                    await self.send_update(
                        user_id, "Creating verification request...", context
                    )
                elif "Submitting military status" in line:
                    await self.send_update(
                        user_id, "Submitting military status...", context
                    )
                elif "Submitting personal info" in line:
                    await self.send_update(
                        user_id, "Submitting personal information...", context
                    )
                elif "Waiting for verification email" in line:
                    await self.send_update(
                        user_id, "Waiting for verification email...", context
                    )
                elif "SUCCESS" in line:
                    success = True
                    break
                elif "FAIL" in line or "ERROR" in line:
                    success = False
                    break
                    
            process.wait()
            
            # Check result
            output = '\n'.join(output_lines)
            if "SUCCESS" in output:
                self.db.update_verification_status(verification_id, "success")
                result_text = "✅ *Verification Successful!*"
                
                # Mark data as used
                self.mark_data_used(
                    veteran['firstName'],
                    veteran['lastName'],
                    veteran['birthDate']
                )
            else:
                self.db.update_verification_status(verification_id, "failed")
                result_text = "❌ *Verification Failed*"
                
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            # Remove from active
            if user_id in self.active_verifications:
                del self.active_verifications[user_id]
                
            # Send final result
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=self.active_verifications[user_id]['message_id'],
                text=(
                    f"{result_text}\n\n"
                    f"*Name:* {veteran['firstName']} {veteran['lastName']}\n"
                    f"*Branch:* {veteran['branch']}\n"
                    f"*Time:* {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"Use /status to check all verifications."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            print(f"Verification error: {e}")
            self.db.update_verification_status(verification_id, "failed")
            
            if user_id in self.active_verifications:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=self.active_verifications[user_id]['message_id'],
                    text=f"❌ *Error occurred:* {str(e)[:100]}"
                )
                del self.active_verifications[user_id]
                
    async def send_update(self, user_id, message, context):
        """Send real-time update to user"""
        if user_id in self.active_verifications:
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=self.active_verifications[user_id]['message_id'],
                    text=(
                        f"{self.active_verifications[user_id]['message_text']}\n"
                        f"➡️ {message}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass  # Message not modified, ignore
                
    def load_veteran_data(self):
        """Load veteran data from data.txt"""
        data = []
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        vet = parse_veteran_line(line)
                        if vet:
                            # Check if already used
                            if not self.is_data_used(vet['firstName'], vet['lastName'], vet['birthDate']):
                                data.append(vet)
        except FileNotFoundError:
            pass
        return data
        
    def is_data_used(self, first_name, last_name, dob):
        """Check if data is already used"""
        try:
            with open(self.used_file, 'r', encoding='utf-8') as f:
                key = f"{first_name.upper()}|{last_name.upper()}|{dob}"
                for line in f:
                    if key in line:
                        return True
        except FileNotFoundError:
            pass
        return False
        
    def mark_data_used(self, first_name, last_name, dob):
        """Mark data as used"""
        key = f"{first_name.upper()}|{last_name.upper()}|{dob}"
        with open(self.used_file, 'a', encoding='utf-8') as f:
            f.write(key + '\n')
            
    async def process_data_input(self, update, context, text):
        """Process veteran data input"""
        if text == '/cancel':
            context.user_data['waiting_for_data'] = False
            await update.message.reply_text("❌ Data input cancelled.")
            return
            
        # Add data
        added = self.add_veteran_data_from_text(text)
        
        if added > 0:
            await update.message.reply_text(
                f"✅ Added {added} veteran record(s)!\n"
                f"Total records now: {self.count_veteran_data()}"
            )
        else:
            await update.message.reply_text(
                "❌ No valid data found!\n"
                "Format: FirstName|LastName|Branch|BirthDate|DischargeDate"
            )
            
        context.user_data['waiting_for_data'] = False
        
    def add_veteran_data_from_text(self, text):
        """Add veteran data from text"""
        lines = text.strip().split('\n')
        added = 0
        
        with open(self.data_file, 'a', encoding='utf-8') as f:
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    vet = parse_veteran_line(line)
                    if vet:
                        f.write(line + '\n')
                        added += 1
                        
        return added
        
    def count_veteran_data(self):
        """Count total veteran records"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return sum(1 for line in f if line.strip() and not line.startswith('#'))
        except FileNotFoundError:
            return 0
            
    async def show_data_list(self, query, context):
        """Show list of available veteran data"""
        data = self.load_veteran_data()
        
        if not data:
            await query.edit_message_text(
                "📭 *No data available!*\n\n"
                "Add veteran data using /add_data command.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        text = "📋 *Available Veteran Data*\n\n"
        for i, vet in enumerate(data[:15], 1):  # Show first 15
            text += (
                f"{i}. *{vet['firstName']} {vet['lastName']}*\n"
                f"   Branch: {vet['branch']}\n"
                f"   DOB: {vet['birthDate']} | Discharge: {vet['dischargeDate']}\n\n"
            )
            
        if len(data) > 15:
            text += f"... and {len(data) - 15} more records\n\n"
            
        text += f"Total: {len(data)} available records"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    async def show_admin_panel(self, query, context):
        """Show admin panel"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await query.edit_message_text("⛔ Access Denied")
            return
            
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
            [InlineKeyboardButton("📥 Add Data", callback_data="add_data")],
            [InlineKeyboardButton("👥 User List", callback_data="users")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("📋 View Logs", callback_data="logs")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔐 *Admin Panel*\n\n"
            "Select an option below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )


def main():
    """Main function to start the bot"""
    global bot_app
    
    # Check for bot token
    if not Config.BOT_TOKEN:
        print("❌ Error: BOT_TOKEN not found in .env file!")
        print("Please create .env file with BOT_TOKEN=your_token")
        return
        
    # Create bot instance
    bot = VerificationBot()
    
    # Create application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    bot_app = app
    
    # Add handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("verify", bot.verify_command))
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("add_data", bot.add_data_command))
    app.add_handler(CommandHandler("stats", bot.stats_command))
    app.add_handler(CommandHandler("broadcast", bot.broadcast_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    app.add_handler(CallbackQueryHandler(bot.callback_handler))
    
    print("🤖 Veterans Verification Bot is starting...")
    print(f"👑 Admin IDs: {Config.ADMIN_IDS}")
    
    # Start bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
