import os
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN', 'seu_token_slack_aqui')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL', 'seu_canal_slack_aqui')

GOOGLE_SHEETS_URL = os.getenv('GOOGLE_SHEETS_URL', 'https://docs.google.com/spreadsheets/d/1tE7ZBhvsfUqcZNa4UnrrALrXOwRlc185a7iVPh_iv7g/edit?gid=1046712131')

PROCESSED_DATA_FILE = 'data/processed_records.json'

LOG_FILE = 'logs/excel_to_slack.log' 