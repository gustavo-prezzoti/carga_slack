import pandas as pd
import logging
from typing import List, Dict, Any, Optional

class ExcelProcessor:
    """
    Classe para processar dados de arquivos Excel.
    """
    
    def __init__(self, file_path: str):
        """
        Inicializa o processador com o caminho do arquivo Excel.
        
        Args:
            file_path: Caminho para o arquivo Excel
        """
        self.file_path = file_path
    
    def read_data(self, sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lê os dados do arquivo Excel e retorna como uma lista de dicionários.
        
        Args:
            sheet_name: Nome da planilha a ser lida (opcional)
            
        Returns:
            Lista de dicionários, onde cada dicionário representa uma linha
        """
        try:
            if sheet_name:
                df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(self.file_path)
            
            # Converte para lista de dicionários
            records = df.to_dict('records')
            
            # Converte valores NaN para None
            clean_records = []
            for record in records:
                clean_record = {}
                for key, value in record.items():
                    if pd.isna(value):
                        clean_record[key] = None
                    else:
                        clean_record[key] = value
                clean_records.append(clean_record)
            
            return clean_records
            
        except Exception as e:
            logging.error(f"Erro ao ler arquivo Excel {self.file_path}: {e}")
            return [] 