import json
import os
import logging
import sys
from typing import Dict, List, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import PROCESSED_DATA_FILE

class DataManager:
    """
    Gerencia o armazenamento e recuperação de dados processados para evitar duplicações.
    Agora salva agrupado por empresa/título (ex: FB ADS, G ADS) em arrays.
    """
    
    def __init__(self, storage_file: str = PROCESSED_DATA_FILE):
        self.storage_file = storage_file
        self._ensure_storage_file()
        
    def _ensure_storage_file(self) -> None:
        """Garante que o arquivo de armazenamento existe."""
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w') as f:
                json.dump({}, f)
    
    def get_processed_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Recupera os dados já processados, agrupados por empresa/título."""
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    grouped = {}
                    for rec in data:
                        titulo = rec.get('titulo', 'OUTROS')
                        grouped.setdefault(titulo, []).append(rec)
                    return grouped
                return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Erro ao ler dados processados: {e}")
            return {}
    
    def save_processed_data(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Salva os dados processados agrupados por empresa/título."""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Erro ao salvar dados processados: {e}")
    
    def is_record_processed(self, record: Dict[str, Any], key_field: str) -> bool:
        """
        Verifica se um registro já foi processado com base em um campo chave.
        Agora busca dentro do array do título correspondente.
        """
        processed_data = self.get_processed_data()
        titulo = record.get('titulo', 'OUTROS')
        registros = processed_data.get(titulo, [])
        for processed_record in registros:
            if processed_record.get(key_field) == record.get(key_field):
                return True
        return False
    
    def mark_as_processed(self, record: Dict[str, Any], key_field: str = 'id') -> None:
        """
        Marca um registro como processado, agrupando por título.
        """
        processed_data = self.get_processed_data()
        titulo = record.get('titulo', 'OUTROS')
        if titulo not in processed_data:
            processed_data[titulo] = []
        for existing in processed_data[titulo]:
            if existing.get(key_field) == record.get(key_field):
                return  
        processed_data[titulo].append(record)
        self.save_processed_data(processed_data) 