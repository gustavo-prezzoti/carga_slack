import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import logging

from db_manager import DBManager

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSheetsProcessor:
    """
    Classe para processar dados do Google Sheets usando a API oficial (gspread).
    """
    def __init__(self, spreadsheet_url: str, site_name: str, creds_path: str = 'google_service_account.json'):
        """
        Inicializa o processador com a URL da planilha e as credenciais de serviço.
        
        Args:
            spreadsheet_url: URL da planilha do Google Sheets
            site_name: Nome do site para obter a configuração de índices
            creds_path: Caminho para o arquivo de credenciais JSON
        """
        self.spreadsheet_url = spreadsheet_url
        self.creds_path = creds_path
        self.site_name = site_name
        self.db_manager = DBManager()
        self.db_manager.connect()
        self.site_config = self.db_manager.get_site_config(site_name)
        
        try:
            self.creds = Credentials.from_service_account_file(
                self.creds_path, 
                scopes=SCOPES
            )
            self.gc = gspread.authorize(self.creds)
            self.spreadsheet = self.gc.open_by_url(self.spreadsheet_url)
            logging.info(f"Conexão com a planilha estabelecida: {self.spreadsheet.title}")
        except Exception as e:
            import traceback
            logging.error(f"Erro ao conectar à planilha: {e}\n{traceback.format_exc()}")
            print(f"Erro ao conectar à planilha: {e}\n{traceback.format_exc()}")
            raise

    def get_sheet_ids(self) -> List[Dict[str, str]]:
        """
        Obtém lista de abas disponíveis na planilha (nome e GID).
        
        Returns:
            Lista com informações das abas (nome e ID)
        """
        try:
            sheets = []
            for ws in self.spreadsheet.worksheets():
                sheets.append({
                    'name': ws.title,
                    'id': str(ws.id)
                })
            logging.info(f"Abas encontradas via API: {sheets}")
            return sheets
        except Exception as e:
            logging.error(f"Erro ao obter lista de abas: {e}")
            return []

    def read_data(self, sheet_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
        """
        Lê os dados da aba pelo GID usando gspread e retorna lista de dicionários.
        
        Args:
            sheet_id: ID da aba da planilha
            
        Returns:
            Tupla com lista de registros, dados de resumo e nome da aba
        """
        try:
            ws = None
            for worksheet in self.spreadsheet.worksheets():
                if str(worksheet.id) == str(sheet_id):
                    ws = worksheet
                    break
                    
            if ws is None:
                logging.warning(f"Aba com GID {sheet_id} não encontrada.")
                return [], {}, ""
            
            data = ws.get_all_values()
            if not data:
                logging.warning(f"Nenhum dado encontrado na aba {ws.title}")
                return [], {}, ws.title
                
            header_row_index = None
            for i, row in enumerate(data):
                if row and (row[0] == "Data" or "Data" in row):
                    header_row_index = i
                    break
            

            if header_row_index is None:
                header_row_index = 0
            
            # Extrai o cabeçalho e os dados
            headers = data[header_row_index]
            print("Cabeçalho lido:", headers)
            # Busca os índices das colunas pelo nome apenas para ROAS e MC
            indices = self.site_config['indices']
            investimento_idx = indices['investimento']
            receita_idx = indices['receita']
            try:
                roas_idx = headers.index("ROAS")
            except ValueError:
                roas_idx = indices['roas']
            try:
                mc_idx = headers.index("MC")
            except ValueError:
                mc_idx = indices['mc']
            
            rows = data[header_row_index + 1:]
            
            rows = [row for row in rows if any(cell.strip() for cell in row)]
            
            records = []
            for row in rows:
                if len(row) > max(investimento_idx, receita_idx, roas_idx, mc_idx):  
                    print(f"Linha lida: Data={row[0]}, Investimento={row[investimento_idx] if len(row) > investimento_idx else 'N/A'}, Receita={row[receita_idx] if len(row) > receita_idx else 'N/A'}, ROAS={row[roas_idx] if len(row) > roas_idx else 'N/A'}, MC={row[mc_idx] if len(row) > mc_idx else 'N/A'}")
                    
                    new_record = {
                        'Data': row[0],
                        'Investimento': row[investimento_idx] if len(row) > investimento_idx else '',
                        'Receita': row[receita_idx] if len(row) > receita_idx else '',
                        'ROAS Geral': row[roas_idx] if len(row) > roas_idx else '',
                        'MC Geral': row[mc_idx] if len(row) > mc_idx else '',
                    }
                    records.append(new_record)
            
            cleaned_records = self._map_column_names(records)
            
            summary = self._extract_summary_data(records)
            
            logging.info(f"Dados lidos com sucesso da aba '{ws.title}': {len(cleaned_records)} registros")
            return cleaned_records, summary, ws.title
            
        except Exception as e:
            logging.error(f"Erro ao ler dados da aba: {e}")
            return [], {}, ""
    
    def _map_column_names(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mapeia os nomes das colunas para nomes mais amigáveis.
        
        Args:
            records: Lista de registros com nomes de colunas originais
            
        Returns:
            Lista de registros com nomes de colunas mapeados
        """
        if not records:
            return []
        
        data_rows = []
        for record in records:
            if 'Data' in record:
                new_record = {
                    'Data': record.get('Data'),
                    'Investimento': record.get('Investimento'),
                    'Receita': record.get('Receita'),
                    'ROAS Geral': record.get('ROAS Geral'),
                    'MC Geral': record.get('MC Geral'),
                }
                data_rows.append(new_record)
        
        return data_rows
    
    def _extract_summary_data(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extrai dados de resumo da planilha (total, médias, etc.)
        
        Args:
            records: Lista de registros originais
            
        Returns:
            Dicionário com dados de resumo
        """
        summary = {}
        
        for record in records:
            first_column = next(iter(record.values())) if record else None
            if first_column == 'Total':
                keys = list(record.keys())
                if len(keys) >= 1:
                    summary['Total FBADS'] = record.get(keys[1])
                if len(keys) >= 6:
                    summary['Total GADS'] = record.get(keys[6])
                if len(keys) >= 7:
                    summary['Total ADS'] = record.get(keys[7])
                if len(keys) >= 9:
                    summary['Total ADX (R$)'] = record.get(keys[9])
                if len(keys) >= 12:
                    summary['ROAS Médio'] = record.get(keys[12])
                if len(keys) >= 16:
                    summary['MC Total'] = record.get(keys[16])
                break
                
        return summary 

    def extract_titles_and_fields(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        print("Registro recebido para extração:", record)
        results = []
        data = record.get('Data')
        
        if record.get('FB ROAS') not in [None, '', 'R$ 0,00']:
            results.append({
                'titulo': 'FB ADS',
                'mc': self.clean_value(record.get('FB MC')),
                'roas': self.clean_value(record.get('FB ROAS')),
                'data': data
            })
            
        if 'GADS ROAS' in record and 'GADS MC' in record:
            results.append({
                'titulo': 'G ADS',
                'mc': self.clean_value(record.get('GADS MC')),
                'roas': self.clean_value(record.get('GADS ROAS')),
                'data': data
            })
            
        if record.get('ROAS Geral') not in [None, '', 'R$ 0,00']:
            results.append({
                'titulo': 'Tech Pra Todos',
                'mc': self.clean_value(record.get('MC Geral')),
                'roas': self.clean_value(record.get('ROAS Geral')),
                'data': data
            })
            
        print("Blocos extraídos:", results)
        return results
        
    def clean_value(self, val):
        if val in [None, '', '#DIV/0!', '#N/A', '#VALUE!', '#REF!', '#NAME?']:
            return '0,00'
        return val 