import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_file('google_service_account.json')
gc = gspread.authorize(creds)

SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1tE7ZBhvsfUqcZNa4UnrrALrXOwRlc185a7iVPh_iv7g/edit?pli=1&gid=1261087214#gid=1261087214'

spreadsheet = gc.open_by_url(SPREADSHEET_URL)

print('Abas encontradas:')
for worksheet in spreadsheet.worksheets():
    print(f'Nome: {worksheet.title} | GID: {worksheet.id}') 