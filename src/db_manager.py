"""
Gerenciador de banco de dados MySQL para armazenar configurações de sites.
Conecta-se ao MySQL através do XAMPP (localhost).
"""

import mysql.connector
from mysql.connector import Error
import logging
from typing import Dict, Any, List, Optional, Tuple

class DBManager:
    """Classe para gerenciar conexões e operações no banco de dados MySQL."""
    
    def __init__(self, host="212.85.10.1", port=3306, user="slackuser", password="Cap0199**", database="carga_slack_db"):
        """
        Inicializa o gerenciador de banco de dados.
        
        Args:
            host: Endereço do servidor MySQL (padrão: localhost para XAMPP)
            port: Porta do servidor MySQL (padrão: 3306)
            user: Usuário do MySQL (padrão: root para XAMPP)
            password: Senha do usuário (padrão: vazio para XAMPP)
            database: Nome do banco de dados
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        
    def connect(self) -> bool:
        """
        Estabelece conexão com o banco de dados.
        
        Returns:
            True se a conexão foi estabelecida com sucesso, False caso contrário
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            if self.connection.is_connected():
                
                logging.info(f"Conectado ao MySQL: {self.host}:{self.port}, banco de dados: {self.database}")
                return True
                
        except Error as e:
            logging.error(f"Erro ao conectar ao MySQL: {e}")
            return False
            
    def disconnect(self) -> None:
        """Fecha a conexão com o banco de dados."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logging.info("Conexão com o MySQL fechada")
            
    def _create_tables(self) -> None:
        """Cria as tabelas necessárias se não existirem."""
        cursor = self.connection.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            sheet_url VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS column_indices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id INT NOT NULL,
            investimento_idx INT NOT NULL,
            receita_idx INT NOT NULL,
            roas_idx INT NOT NULL,
            mc_idx INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
        )
        """)
        
        self.connection.commit()
        
    def add_site(self, name: str, sheet_url: str, investimento_idx: int, 
                receita_idx: int, roas_idx: int, mc_idx: int) -> bool:
        """
        Adiciona ou atualiza um site e suas configurações.
        
        Args:
            name: Nome do site
            sheet_url: URL da planilha do Google Sheets
            investimento_idx: Índice da coluna de investimento
            receita_idx: Índice da coluna de receita
            roas_idx: Índice da coluna de ROAS
            mc_idx: Índice da coluna de MC
            
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
                
            cursor = self.connection.cursor()
            
            cursor.execute("SELECT id FROM sites WHERE name = %s", (name,))
            result = cursor.fetchone()
            
            if result:
                site_id = result[0]
                cursor.execute("""
                UPDATE sites SET sheet_url = %s WHERE id = %s
                """, (sheet_url, site_id))
                
                cursor.execute("""
                UPDATE column_indices SET 
                investimento_idx = %s, receita_idx = %s, roas_idx = %s, mc_idx = %s
                WHERE site_id = %s
                """, (investimento_idx, receita_idx, roas_idx, mc_idx, site_id))
            else:
                cursor.execute("""
                INSERT INTO sites (name, sheet_url) VALUES (%s, %s)
                """, (name, sheet_url))
                site_id = cursor.lastrowid
                

                cursor.execute("""
                INSERT INTO column_indices 
                (site_id, investimento_idx, receita_idx, roas_idx, mc_idx)
                VALUES (%s, %s, %s, %s, %s)
                """, (site_id, investimento_idx, receita_idx, roas_idx, mc_idx))
            
            self.connection.commit()
            logging.info(f"Site '{name}' adicionado/atualizado com sucesso")
            return True
            
        except Error as e:
            logging.error(f"Erro ao adicionar/atualizar site: {e}")
            return False
    
    def get_site_config(self, name: str) -> Dict[str, Any]:
        """
        Obtém a configuração de um site pelo nome.
        Agora também retorna o webhook_url do canal associado, se houver.
        """
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
                
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute("""
            SELECT s.name, s.sheet_url, c.investimento_idx, c.receita_idx, c.roas_idx, c.mc_idx, ch.webhook_url, ch.name as squad_name
            FROM sites s
            JOIN column_indices c ON s.id = c.site_id
            LEFT JOIN slack_channels ch ON s.slack_channel_id = ch.id
            WHERE s.name = %s
            """, (name,))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    "sheet_url": result["sheet_url"],
                    "indices": {
                        "investimento": result["investimento_idx"],
                        "receita": result["receita_idx"],
                        "roas": result["roas_idx"],
                        "mc": result["mc_idx"]
                    },
                    "slack_webhook_url": result["webhook_url"],
                    "squad_name": result.get("squad_name")
                }
            
            return self.get_default_config()
            
        except Error as e:
            logging.error(f"Erro ao buscar configuração do site: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        Retorna a configuração padrão para o site "Tech Pra Todos".
        
        Returns:
            Dicionário com a configuração padrão
        """
        return {
            "sheet_url": "https://docs.google.com/spreadsheets/d/1tE7ZBhvsfUqcZNa4UnrrALrXOwRlc185a7iVPh_iv7g/edit?gid=1046712131",
            "indices": {
                "investimento": 7,  
                "receita": 8,     
                "roas": 12,       
                "mc": 16,       
            }
        }
    
    def get_all_sites(self) -> List[str]:
        """
        Retorna a lista de todos os sites cadastrados.
        
        Returns:
            Lista com os nomes dos sites
        """
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
                
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sites")
            results = cursor.fetchall()
            
            return [row[0] for row in results]
            
        except Error as e:
            logging.error(f"Erro ao listar sites: {e}")
            return []
    
    def delete_site(self, name: str) -> bool:
        """
        Remove um site do banco de dados.
        
        Args:
            name: Nome do site a ser removido
            
        Returns:
            True se o site foi removido com sucesso, False caso contrário
        """
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
                
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM sites WHERE name = %s", (name,))
            self.connection.commit()
            
            affected_rows = cursor.rowcount
            return affected_rows > 0
            
        except Error as e:
            logging.error(f"Erro ao remover site: {e}")
            return False 