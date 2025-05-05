import logging
from typing import Dict, Any, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackClient:
    """
    Cliente para enviar mensagens ao Slack.
    """
    
    def __init__(self, token: str, default_channel: str):
        """
        Inicializa o cliente Slack.
        
        Args:
            token: Token de autenticação do Slack
            default_channel: Canal padrão para envio de mensagens
        """
        self.client = WebClient(token=token)
        self.default_channel = default_channel
    
    def send_message(self, text: str, channel: str = None) -> bool:
        """
        Envia uma mensagem de texto para o Slack.
        
        Args:
            text: Texto da mensagem
            channel: Canal de destino (opcional, usa o padrão se não fornecido)
            
        Returns:
            True se a mensagem foi enviada com sucesso, False caso contrário
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel or self.default_channel,
                text=text
            )
            return True
        except SlackApiError as e:
            logging.error(f"Erro ao enviar mensagem para o Slack: {e}")
            return False
    
    def send_record_as_message(self, record: Dict[str, Any], channel: str = None, 
                               template: str = None) -> bool:
        """
        Envia um registro como mensagem para o Slack.
        
        Args:
            record: Dicionário com os dados a serem enviados
            channel: Canal de destino (opcional)
            template: Template de formatação (opcional)
            
        Returns:
            True se a mensagem foi enviada com sucesso, False caso contrário
        """
        try:
            if not template:
                message_parts = []
                for key, value in record.items():
                    if value is not None:
                        message_parts.append(f"*{key}*: {value}")
                
                message = "\n".join(message_parts)
            else:
                message = template.format(**record)
            
            return self.send_message(message, channel)
            
        except Exception as e:
            logging.error(f"Erro ao formatar e enviar registro para o Slack: {e}")
            return False
            
    def send_batch(self, records: List[Dict[str, Any]], channel: str = None, 
                  template: str = None) -> int:
        """
        Envia múltiplos registros para o Slack.
        
        Args:
            records: Lista de registros a serem enviados
            channel: Canal de destino (opcional)
            template: Template de formatação (opcional)
            
        Returns:
            Número de mensagens enviadas com sucesso
        """
        success_count = 0
        for record in records:
            if self.send_record_as_message(record, channel, template):
                success_count += 1
        
        return success_count 