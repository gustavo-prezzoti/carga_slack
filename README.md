# Google Sheets para Slack - Job Automatizado

Este projeto consiste em um job automatizado que lê dados de uma planilha do Google Sheets e os envia para um canal do Slack, controlando quais registros já foram processados para evitar duplicações.

## Funcionalidades

- Leitura de dados do Google Sheets
- Envio de mensagens formatadas para o Slack
- Controle de registros já processados para evitar duplicidades
- Agendamento automático como tarefa periódica
- Logs detalhados para monitoramento

## Requisitos

- Python 3.7+
- Dependências listadas em `requirements.txt`
- Token de bot do Slack com permissões para enviar mensagens
- Credenciais do Google API para acessar o Google Sheets
- Acesso à planilha do Google Sheets (compartilhada com a conta de serviço)

## Instalação

1. Clone ou baixe este repositório
2. Instale as dependências:

```
pip install -r requirements.txt
```

3. Configure as credenciais do Google:

```
python setup_google_creds.py
```

4. Configure as variáveis de ambiente (ou modifique `config.py`):
   - `SLACK_BOT_TOKEN`: Token do bot do Slack
   - `SLACK_CHANNEL`: Canal do Slack para envio das mensagens
   - `GOOGLE_SHEETS_ID`: ID da planilha do Google Sheets (já configurado para a planilha "Tech Pra Todos")
   - `GOOGLE_SHEET_NAME`: Nome da planilha específica dentro do arquivo

## Estrutura de Diretórios

```
.
├── config.py                      # Configurações do projeto
├── credentials.json               # Arquivo de credenciais do Google API
├── data/                          # Diretório para armazenar dados processados
├── logs/                          # Logs do sistema
├── requirements.txt               # Dependências do projeto
├── setup_google_creds.py          # Script para configurar credenciais do Google
├── setup_job.py                   # Script para configurar o job como tarefa agendada
└── src/                           # Código-fonte
    ├── data_manager.py            # Gerenciamento de dados processados
    ├── excel_processor.py         # Processamento de arquivos Excel (legado)
    ├── google_sheets_processor.py # Processamento de planilhas do Google Sheets
    ├── main.py                    # Script principal
    └── slack_client.py            # Cliente para interação com o Slack
```

## Uso

### Configuração de Credenciais

Antes de executar o programa, configure as credenciais do Google Sheets:

```
python setup_google_creds.py
```

Este script irá guiá-lo através do processo de criação e configuração de credenciais.

### Execução Manual

Para executar o job manualmente:

```
python src/main.py
```

### Configuração como Tarefa Agendada

Para configurar o job como uma tarefa agendada (executa a cada 60 minutos por padrão):

```
python setup_job.py
```

Para alterar o intervalo de execução (por exemplo, a cada 30 minutos):

```
python setup_job.py --interval 30
```

## Personalização

### Formato das Mensagens

Para personalizar o formato das mensagens enviadas ao Slack, edite a variável `message_template` no arquivo `src/main.py`. 

Exemplo:
```python
message_template = """
*Dados Tech Pra Todos - {Data}*
FB ADS: {FBADS 01}
TikTok ADS: {TKADS}
Google ADS: {GADS}
ADX (R$): {ADX (R$)}
ROAS: {ROAS}
"""
```

### Campo Chave para Identificação

Por padrão, o sistema usa o campo `Data` para identificar registros únicos. Você pode alterar isso na função `process_google_sheets_to_slack` em `src/main.py`:

```python
key_field='Data'  # Campo chave para identificar registros únicos
```

## Planilha atual

O projeto está configurado para acessar a planilha "Tech Pra Todos" no seguinte URL:
[https://docs.google.com/spreadsheets/d/1tE7ZBhvsfUqcZNa4UnrrALrXOwRlc185a7iVPh_iv7g/edit?gid=1046712131](https://docs.google.com/spreadsheets/d/1tE7ZBhvsfUqcZNa4UnrrALrXOwRlc185a7iVPh_iv7g/edit?gid=1046712131)

## Solução de Problemas

- **Arquivo de logs**: Verifique `logs/excel_to_slack.log` para informações detalhadas sobre a execução
- **Registros processados**: Os registros já processados são armazenados em `data/processed_records.json`
- **Problemas de autenticação**: Certifique-se de que:
  1. O arquivo `credentials.json` existe e é válido
  2. A planilha do Google Sheets foi compartilhada com o email da conta de serviço
  3. As APIs do Google Sheets e Google Drive estão habilitadas no projeto

## Licença

Este projeto está licenciado sob a licença MIT. 