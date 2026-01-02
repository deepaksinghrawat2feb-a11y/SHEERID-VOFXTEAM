Veterans Verification Telegram Bot 🤖

Telegram bot that automates the ChatGPT Plus verification process for US Veterans using SheerID.

✨ Features

· ✅ Automated Verification - Fully automated SheerID verification process
· 📊 Real-time Updates - Live progress updates in Telegram
· 👑 Admin Panel - Complete management dashboard
· 📁 File Upload - Bulk import veteran data via .txt files
· 🔄 Background Processing - Non-blocking verification jobs
· 📈 Statistics - Detailed analytics and reports
· ⚡ Proxy Support - Built-in proxy rotation
· 🛡️ Security - User authentication and rate limiting

🚀 Quick Setup

1. Prerequisites

· Python 3.10 or higher
· Telegram Bot Token (from @BotFather)
· ChatGPT account with accessToken
· Email account for verification (Gmail recommended)

2. Clone Repository

```bash
git clone https://github.com/VOFxTeam/veterans-verification-bot.git
cd veterans-verification-bot
```

3. Install Dependencies

```bash
pip install -r requirements.txt
```

4. Configuration

A. Create Environment File

```bash
cp .env.example .env
```

B. Edit .env File

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite:///bot.db
MAX_USERS_PER_DAY=5
VERIFICATION_TIMEOUT=300
```

C. Get Telegram Bot Token

1. Open Telegram, search for @BotFather
2. Send /newbot command
3. Choose bot name
4. Copy the token and paste in .env

D. Get Your Telegram ID

1. Open Telegram, search for @userinfobot
2. Send /start
3. Copy your ID and add to ADMIN_IDS in .env

5. Setup Original Verification Tool

Create config.json

```json
{
    "accessToken": "your_chatgpt_access_token_here",
    "programId": "690415d58971e73ca187d8c9",
    "email": {
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "email_address": "your_email@gmail.com",
        "email_password": "your_app_password",
        "use_ssl": true
    }
}
```

How to Get ChatGPT accessToken

1. Login to chatgpt.com
2. Open Developer Tools (F12) → Console
3. Visit: https://chatgpt.com/api/auth/session
4. Copy the accessToken value

How to Get Gmail App Password

1. Go to Google Account Security
2. Enable 2-Step Verification
3. Go to App passwords
4. Select Mail → Other (name it "Verification Bot")
5. Copy the 16-character password

6. Create Data Files

```bash
# Create data.txt for veteran data
echo "JOHN|SMITH|Army|1990-05-15|2025-06-01" > data.txt
echo "DAVID|JOHNSON|Marine Corps|1988-12-20|2025-03-15" >> data.txt

# Create used.txt (track used data)
touch used.txt

# Create proxy.txt (optional)
touch proxy.txt
```

7. Run the Bot

```bash
# Start the bot
python bot.py

# Or run in background
nohup python bot.py > bot.log 2>&1 &
```

📱 Bot Commands

For Users

Command Description
/start Start the bot
/help Show instructions
/verify Start verification
/status Check verification history

For Admins

Command Description
/add_data Add veteran data
/stats View statistics
/broadcast Send message to all users
/users List all users

📊 Adding Veteran Data

Format

```
FirstName|LastName|Branch|BirthDate|DischargeDate
```

Example

```
JOHN|SMITH|Army|1990-05-15|2025-06-01
DAVID|JOHNSON|Marine Corps|1988-12-20|2025-03-15
MICHAEL|WILLIAMS|Navy|1992-08-10|2025-01-30
```

Supported Branches

· Army, Navy, Air Force
· Marine Corps, Coast Guard, Space Force
· Army National Guard, Army Reserve
· Air National Guard, Air Force Reserve
· Navy Reserve, Marine Corps Reserve, Coast Guard Reserve

Date Format: YYYY-MM-DD

🐳 Docker Deployment

```bash
# Using Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop bot
docker-compose down
```

📁 Project Structure

```
veterans-verification-bot/
├── bot.py                 # Main bot file
├── database.py           # Database models
├── utils.py              # Utility functions
├── config.py             # Configuration
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── config.json          # ChatGPT configuration
├── data.txt             # Veteran data
├── used.txt             # Used data tracking
├── proxy.txt            # Proxy list
├── Dockerfile           # Docker configuration
└── docker-compose.yml   # Docker compose
```

🔧 Troubleshooting

Common Issues

1. Bot not starting
   · Check BOT_TOKEN in .env
   · Ensure Python 3.10+ installed
   · Check all dependencies installed
2. Verification errors
   · Check accessToken in config.json
   · Verify email credentials
   · Ensure veteran data is valid
3. Email connection failed
   · Enable IMAP in email settings
   · Use App Password for Gmail
   · Check firewall settings

Logs

```bash
# View bot logs
tail -f bot.log

# View error logs
tail -f error.log
```

🤝 Support

· Create an issue on GitHub
· Check existing issues for solutions
· Contact admin through Telegram

📝 License

This project is for educational purposes only. Use at your own risk.

⭐ Credits

Developed with ❤️ by VOFxTeam

---

Disclaimer: This tool is for educational purposes only. Users are responsible for complying with all applicable laws and terms of service.
