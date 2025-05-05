import logging
import sys
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
import requests
import time
import pytz
import random
import argparse
import traceback
import schedule
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_sheets_processor import GoogleSheetsProcessor
from db_manager import DBManager
from data_manager import DataManager
from config import (
    GOOGLE_SHEETS_URL,
    LOG_FILE
)

def setup_logging():
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

def clean_value(val):
    if val in [None, '', '#DIV/0!', '#N/A', '#VALUE!', '#REF!', '#NAME?']:
        return '0,00'
    return val

def is_dollar_value(value_str):
    """
    Determina se um valor está em dólar baseado no formato.
    Considera o símbolo $ explicitamente, não apenas na formatação.
    
    Args:
        value_str: String com o valor
        
    Returns:
        True se valor está em dólar, False caso contrário
    """
    value_str = str(value_str).strip()
    return '$' in value_str and 'R$' not in value_str

def extract_titles_and_fields(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Para cada linha de data, extrai os blocos/títulos (FB ADS, G ADS, etc.) com seus MC e ROAS.
    """
    results = []
    data = record.get('Data')
    if record.get('FBADS 01') not in [None, '', 'R$ 0,00']:
        results.append({
            'titulo': 'FB ADS',
            'mc': clean_value(record.get('MC R$')),
            'roas': clean_value(record.get('ROAS')),
            'data': data
        })
    if record.get('GADS') not in [None, '', 'R$ 0,00']:
        results.append({
            'titulo': 'G ADS',
            'mc': clean_value(record.get('MC R$ .2')),
            'roas': clean_value(record.get('ROAS .2')),
            'data': data
        })
    return results


def format_slack_message_empresa(empresa: str, data: str, blocos: list) -> list:
    mensagens = []
    for bloco in blocos:
        roas = bloco.get('roas') or '**'
        mc = bloco.get('mc') or '**'
        if bloco['titulo'] == 'FB ADS':
            titulo_empresa = bloco.get('FBADS 01') or 'FB ADS'
        elif bloco['titulo'] == 'G ADS':
            titulo_empresa = bloco.get('G-ADS') or 'G ADS'
        else:
            titulo_empresa = bloco['titulo']
        msg = f"Atualização {titulo_empresa}\nROAS: {roas}\nMC: {mc}"
        mensagens.append(msg)
    return mensagens

def get_roas_emoji(roas_value):
    """
    Retorna o emoji apropriado com base no valor do ROAS.
    ROAS < 1: :warning:
    ROAS < 1.5: :moneybag:
    ROAS >= 1.5: :money_with_wings:
    """
    try:
        roas_num = float(roas_value.replace(',', '.').replace('R$', '').strip())
        if roas_num < 1:
            return ":warning:"
        elif roas_num < 1.5:
            return ":moneybag:"
        else:
            return ":money_with_wings:"
    except:
        return ""

def get_mc_emoji(mc_value):
    """
    Retorna o emoji apropriado com base no valor monetário do MC.
    MC < 0: :warning: (negativo)
    0 <= MC <= 100: :moneybag:
    100 < MC <= 1000: :star-struck:
    MC > 1000: :money_with_wings:
    """
    try:

        mc_str = str(mc_value).replace('R$', '').strip()
        

        if ',' in mc_str and '.' in mc_str:

            mc_str = mc_str.replace('.', '').replace(',', '.')
        elif ',' in mc_str:

            mc_str = mc_str.replace(',', '.')
            

        is_negative = mc_str.startswith('-')
        if is_negative:
            mc_str = mc_str[1:]
            

        mc_num = float(mc_str)
        if is_negative:
            mc_num = -mc_num
            

        if mc_num < 0:
            return ":warning:"
        elif mc_num <= 100:
            return ":moneybag:"
        elif mc_num <= 1000:
            return ":star-struck:" 
        else:
            return ":money_with_wings:"
    except Exception as e:
        print(f"Erro ao processar MC: {e}, valor: {mc_value}")
        return ""

def send_to_slack(message: str, webhook_url: str) -> bool:
    logging.info(f"Enviando mensagem ao Slack: {message}")
    try:
        response = requests.post(
            webhook_url,
            json={"text": message},
            headers={"Content-type": "application/json"}
        )
        logging.info(f"Resposta do Slack: status={response.status_code}, body={response.text}")
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Exceção ao enviar mensagem ao Slack: {e}")
        return False

def get_current_date_str() -> str:
    """Retorna a data atual no formato DD/MM.""" 
    now = datetime.now()
    return f"{now.day:02d}/{now.month:02d}"

def get_brasilia_time_str():
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)
    return now.strftime('%H:%M')

def to_float(val):
    if not val:
        return 0.0
    val = str(val)
    match = re.search(r'-?\d+[\d.,]*', val.replace('R$', '').replace(' ', ''))
    if not match:
        return 0.0
    num = match.group(0).replace('.', '').replace(',', '.')
    try:
        return float(num)
    except:
        return 0.0

def process_current_date_only(sheets_url: str, site_name: str) -> None:
    sheets_processor = GoogleSheetsProcessor(sheets_url, site_name=site_name)
    current_date = get_current_date_str()
    current_month = datetime.now().month
    current_year = datetime.now().year
    db = DBManager()
    db.connect()
    config = db.get_site_config(site_name)
    print(f"DEBUG: config retornado para {site_name}: {config}")
    print(f"DEBUG: webhook_url para {site_name}: {config.get('slack_webhook_url')}")
    webhook_url = config.get('slack_webhook_url')
    if not webhook_url:
        logging.warning(f"Site '{site_name}' não possui webhook do Slack configurado!")
        return
    sheets = sheets_processor.get_sheet_ids()
    if not sheets:
        return

    for sheet in sheets:
        sheet_id = sheet['id']
        records, summary, actual_name = sheets_processor.read_data(sheet_id)
        if not records:
            continue
        pagina = actual_name or sheet['name']
        
        aba_mes_vigente = False
        for mes in ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]:
            if mes in pagina:
                mes_num = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"].index(mes) + 1
                if mes_num == current_month and str(current_year) in pagina:
                    aba_mes_vigente = True
                break

        if not aba_mes_vigente:
            continue

        current_record = None
        for r in reversed(records):
            if r.get('Data') == current_date:
                current_record = r
                break

        if not current_record:
            logging.warning(f"Nenhum registro encontrado para a data {current_date}")
            continue
        
        print("Data do registro encontrado:", current_record.get('Data'))
        print("MC bruto da planilha:", current_record.get('MC Geral'))
        mc_geral = clean_value(current_record.get('MC Geral', '0,00'))
        print("MC após clean_value:", mc_geral)
        print("MC após to_float:", to_float(mc_geral))
        
        investimento = clean_value(current_record.get('Investimento', '0,00'))
        receita = clean_value(current_record.get('Receita', '0,00'))
        roas_geral = clean_value(current_record.get('ROAS Geral', '0,00'))
        roas_emoji = get_roas_emoji(roas_geral)
        mc_emoji = get_mc_emoji(mc_geral)
            
        hora_atual = get_brasilia_time_str()
        
        msg = f":bar_chart: Atualização {site_name} {roas_emoji} {mc_emoji}\n" \
              f"Investimento: *{investimento}*\n" \
              f"Receita: *{receita}*\n" \
              f"ROAS: *{roas_geral}*\n" \
              f"MC: *{mc_geral}*"
        
        send_to_slack(msg, webhook_url)
        

        try:
            total_investimento = to_float(investimento)
            total_receita = to_float(receita)
            total_mc = to_float(mc_geral)
            roas_site = total_receita / total_investimento if total_investimento > 0 else 0.0
            roas_site_str = f"{roas_site:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            squad_name = config.get('squad_name')
            resumo_title = f"*Resumo da {squad_name}:*" if squad_name else "*Resumo do canal:*"
            resumo_msg = [
                resumo_title,
                f"Investimento total: R$ {total_investimento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + "\n",
                f"Receita total: R$ {total_receita:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + "\n",
                f"ROAS total: {roas_site_str}\n",
                f"MC total: R$ {total_mc:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            ]
            resumo_final = "\n".join(resumo_msg)
            send_to_slack('```========================= RESUMO =========================```', webhook_url)
            send_to_slack(resumo_final, webhook_url)
        except Exception as e:
            logging.error(f"Erro ao calcular/enviar resumo do grupo: {e}")
            send_to_slack(f"Erro ao enviar resumo: {e}", webhook_url)
        
        send_to_slack('<==================================:small_blue_diamond:===============================>', webhook_url)
        
        break 

def run_monitor(sheets_url: str, site_name: str, interval_seconds: int = 10):
    """
    Monitora continuamente a planilha para verificar atualizações na data atual.
    
    Args:
        sheets_url: URL da planilha do Google Sheets
        site_name: Nome do site cadastrado no banco
        interval_seconds: Intervalo entre verificações em segundos
    """
    logging.info(f"Iniciando monitoramento da data atual com intervalo de {interval_seconds} segundos")
    try:
        while True:
            process_current_date_only(sheets_url, site_name)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logging.info("Monitoramento interrompido pelo usuário")
        send_to_slack("Monitoramento interrompido")
    except Exception as e:
        logging.error(f"Erro durante o monitoramento: {e}")
        send_to_slack(f"Erro no monitoramento: {str(e)}")

def process_all_sheets(sheets_url: str, site_name: str) -> Dict[str, int]:
    """
    Processa todas as abas da planilha do Google Sheets e salva registros detalhados por título/bloco.
    Processa um mês inteiro por vez, ao invés de alternar entre abas.
    """
    db = DBManager()
    db.connect()
    sheets_processor = GoogleSheetsProcessor(sheets_url, site_name=site_name)
    data_manager = DataManager()
    stats = {
        'total_sheets': 0,
        'processadas': 0,
        'enviadas': 0,
        'falhas': 0
    }
    sheets = sheets_processor.get_sheet_ids()
    stats['total_sheets'] = len(sheets)
    if not sheets:
        logging.warning("Nenhuma aba encontrada na planilha")
        return stats
    
    for sheet in sheets:
        sheet_id = sheet['id']
        sheet_name = sheet['name']
        logging.info(f"Processando aba: {sheet_name} (ID: {sheet_id})")
        records, summary, actual_name = sheets_processor.read_data(sheet_id)
        if not records:
            logging.warning(f"Não foi possível extrair registros da aba {sheet_name}")
            stats['falhas'] += 1
            continue
        
        pagina = actual_name or sheet_name
        empresa = pagina
        
        registros_por_data = {}
        for record in records:
            if not record.get('Data'):
                logging.debug(f"Linha ignorada (sem Data): {record}")
                continue
            data = record.get('Data')
            blocos = sheets_processor.extract_titles_and_fields(record)
            if not blocos:
                continue
            
            if data not in registros_por_data:
                registros_por_data[data] = []
            
            for bloco in blocos:
                bloco_copy = bloco.copy()
                bloco_copy['pagina'] = pagina
                registros_por_data[data].append(bloco_copy)
        

        config = db.get_site_config(site_name)
        sheet_url = config['sheet_url'] if config and config.get('sheet_url') else None
        webhook_url = config.get('slack_webhook_url')
        print(f"DEBUG: config retornado para {site_name}: {config}")
        print(f"DEBUG: webhook_url para {site_name}: {webhook_url}")
        if not sheet_url:
            logging.warning(f"Site '{site_name}' sem sheet_url cadastrado! Pulando...")
            stats['falhas'] += 1
            continue
        if not webhook_url:
            logging.warning(f"Site '{site_name}' sem webhook do Slack cadastrado! Pulando...")
            stats['falhas'] += 1
            continue

        for data in sorted(registros_por_data.keys()):
            blocos = registros_por_data[data]
            registro_id = f"{empresa}_{data}"
            if data_manager.is_record_processed({'id': registro_id, 'titulo': empresa}, 'id'):
                logging.info(f"Grupo já processado: {registro_id}")
                stats['processadas'] += 1
                continue
            
            mensagens = format_slack_message_empresa(empresa, data, blocos)
            sucesso = True
            for mensagem in mensagens:
                logging.info(f"Preparando para enviar ao Slack: {mensagem}")
                if not send_to_slack(mensagem, webhook_url): 
                    sucesso = False
                    stats['falhas'] += 1
                send_to_slack('<==================================:small_blue_diamond:===============================>', webhook_url)

            try:
                sheets_processor = GoogleSheetsProcessor(sheet_url, site_name=site_name)
                current_date = get_current_date_str()
                current_month = datetime.now().month
                current_year = datetime.now().year
                sheets = sheets_processor.get_sheet_ids()
                if not sheets:
                    continue
                site_investimento = 0.0
                site_receita_real = 0.0
                site_receita_dolar = 0.0
                site_mc = 0.0
                encontrou_registro = False
                roas_lidos = [] 
                for sheet in sheets:
                    sheet_id = sheet['id']
                    records, summary, actual_name = sheets_processor.read_data(sheet_id)
                    if not records:
                        continue
                    pagina = actual_name or sheet['name']
                    aba_mes_vigente = False
                    for mes in ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]:
                        if mes in pagina:
                            mes_num = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"].index(mes) + 1
                            if mes_num == current_month and str(current_year) in pagina:
                                aba_mes_vigente = True
                            break
                    if not aba_mes_vigente:
                        continue
                    print(f"[DEBUG] Datas lidas na aba {pagina}: {[r.get('Data') for r in records]}")
                    current_record = None
                    for r in reversed(records):
                        data_val = r.get('Data')
                        if not data_val:
                            continue
                        data_val_str = str(data_val).strip()
                        matched = False
                        for fmt in ["%d/%m", "%d/%m/%Y", "%d/%m/%y", "%d-%m", "%d-%m-%Y", "%d-%m-%y"]:
                            try:
                                dt_val = datetime.strptime(re.sub(r'\\s+', '', data_val_str), fmt)
                                dt_target = datetime.strptime(current_date, "%d/%m")
                                if dt_val.day == dt_target.day and dt_val.month == dt_target.month:
                                    matched = True
                                    break
                            except Exception:
                                continue
                        if not matched:
                            try:
                                parts = re.split(r'[/-]', data_val_str)
                                if len(parts) >= 2:
                                    d, m = int(parts[0]), int(parts[1])
                                    dt_target = datetime.strptime(current_date, "%d/%m")
                                    if d == dt_target.day and m == dt_target.month:
                                        matched = True
                            except Exception:
                                pass
                        if matched:
                            current_record = r
                            break
                    if not current_record:
                        continue
                    encontrou_registro = True
                    investimento = clean_value(current_record.get('Investimento', '0,00'))
                    receita = clean_value(current_record.get('Receita', '0,00'))
                    roas_geral = clean_value(current_record.get('ROAS Geral', '0,00'))
                    mc_geral = clean_value(current_record.get('MC Geral', '0,00'))
                    print(f"Valores encontrados para {site_name}: Investimento={investimento}, Receita={receita}, ROAS={roas_geral}, MC={mc_geral}")
                    
                    is_dolar = is_dollar_value(receita)
                    print(f"[DEBUG] Receita '{receita}' detectada como {'DÓLAR' if is_dolar else 'REAL'}")
                    
                    site_investimento += to_float(investimento)
                    if is_dolar:
                        site_receita_dolar += to_float(receita)
                    else:
                        site_receita_real += to_float(receita)
                    site_mc += to_float(mc_geral)
                    site_roas = roas_geral 
                    roas_lidos.append(to_float(roas_geral))
                    
                if site_investimento > 0 or site_receita_real > 0 or site_receita_dolar > 0 or encontrou_registro:
                    roas_geral_str = site_roas
                    
                    if not roas_geral_str or roas_geral_str == '0,00':
                        roas_geral_str = '0,00'
                        
                    roas_emoji = get_roas_emoji(roas_geral_str)
                    mc_emoji = get_mc_emoji(str(site_mc))
                    
                    investimento_str = f"R$ {site_investimento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    receita_real_str = f"R$ {site_receita_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if site_receita_real > 0 else "R$ 0,00"
                    receita_dolar_str = f"$ {site_receita_dolar:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if site_receita_dolar > 0 else "$ 0,00"
                    
                    receipts_msg = ""
                    if site_receita_real > 0 and site_receita_dolar > 0:
                        receipts_msg = f"Receita (R$): *{receita_real_str}*\nReceita ($): *{receita_dolar_str}*"
                    elif site_receita_real > 0:
                        receipts_msg = f"Receita: *{receita_real_str}*"
                    elif site_receita_dolar > 0:
                        receipts_msg = f"Receita: *{receita_dolar_str}*"
                    else:
                        receipts_msg = "Receita: *R$ 0,00*"
                        
                    msg = f":bar_chart: Atualização {site_name} {roas_emoji} {mc_emoji}\n" \
                        f"Investimento: *{investimento_str}*\n" \
                        f"{receipts_msg}\n" \
                        f"ROAS: *{roas_geral_str}*\n" \
                        f"MC: *{mc_geral}*"
                    send_to_slack(msg, webhook_url)
                
                try:
                    total_investimento = to_float(site_investimento)
                    total_receita_real = to_float(site_receita_real)
                    total_receita_dolar = to_float(site_receita_dolar)
                    total_mc = to_float(site_mc)
                    total_receita = total_receita_real + total_receita_dolar
                    roas_medio = (total_receita_real + total_receita_dolar) / total_investimento if total_investimento > 0 else 0.0
                    roas_medio_str = f"{roas_medio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    investimento_str = f"R$ {total_investimento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    receita_real_str = f"R$ {total_receita_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    receita_dolar_str = f"$ {total_receita_dolar:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    mc_str = f"R$ {total_mc:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    squad_name = config.get('squad_name')
                    resumo_title = f"*Resumo Squad {squad_name}:*" if squad_name else "*Resumo do canal:*"
                    resumo_msg = [
                        resumo_title,
                        f"Investimento total: {investimento_str}",
                        f"Receita total em reais: {receita_real_str}",
                        f"Receita total em dólares: {receita_dolar_str}",
                        f"ROAS médio: {roas_medio_str}",
                        f"MC total: {mc_str}"
                    ]
                    resumo_final = "\n".join(resumo_msg)
                    send_to_slack('```========================= RESUMO =========================```', webhook_url)
                    send_to_slack(resumo_final, webhook_url)
                except Exception as e:
                    send_to_slack(f"Erro ao enviar resumo: {e}", webhook_url)

            except Exception as e:
                logging.error(f"Erro ao calcular/enviar resumo do grupo: {e}")
                send_to_slack(f"Erro ao enviar resumo: {e}", webhook_url)

            if sucesso:
                data_manager.mark_as_processed({
                    'id': registro_id, 
                    'titulo': empresa, 
                    'data': data, 
                    'blocos': blocos,
                    'data_processamento': datetime.now().isoformat()
                }, key_field='id')
                logging.info(f"Grupo marcado como processado: {registro_id}")
                stats['enviadas'] += 1
    
    logging.info(f"Processamento de todas as abas concluído: {stats}")
    return stats

def exponential_backoff(attempt, max_backoff=60):
    """
    Calcula o tempo de espera para retentativa com backoff exponencial e jitter.
    
    Args:
        attempt: Número da tentativa atual (começa em 1)
        max_backoff: Tempo máximo de espera em segundos
        
    Returns:
        Tempo de espera em segundos
    """
    base_delay = min(2 ** (attempt - 1), max_backoff)
    jitter = random.uniform(0, 0.1 * base_delay)  
    return base_delay + jitter

def main():
    """Função principal do programa."""
    setup_logging()
    os.makedirs('data', exist_ok=True)
    db = DBManager()
    db.connect()


    parser = argparse.ArgumentParser(description='Processa dados do Google Sheets para Slack')
    parser.add_argument('--site', type=str, help='Nome do site a ser processado (opcional)')
    args = parser.parse_args()

    if args.site:
        site_name = args.site
        config = db.get_site_config(site_name)
        sheet_url = config['sheet_url'] if config and config.get('sheet_url') else None
        if not sheet_url:
            print(f"Site '{site_name}' sem sheet_url cadastrado! Abortando...")
            return
        print(f"Processando site: {site_name} ({sheet_url})")
        try:
            process_current_date_only(sheet_url, site_name)
        except Exception as e:
            if 'RATE_LIMIT_EXCEEDED' in str(e) or '429' in str(e):
                print("Limite de requisições atingido. Aguardando 60 segundos antes de tentar novamente...")
                time.sleep(60)
                try:
                    process_current_date_only(sheet_url, site_name)
                except Exception as e2:
                    print(f"Erro ao processar site {site_name} após aguardar: {e2}")
                    print(traceback.format_exc())
            else:
                print(f"Erro ao processar site {site_name}: {e}")
                print(traceback.format_exc())
    else:
        all_sites = db.get_all_sites()
        print(f"\nIniciando processamento da data atual ({get_current_date_str()}) para todos os sites cadastrados...")
        print("Pressione Ctrl+C para interromper o processamento.")
        total_investimento_geral = 0.0
        total_receita_geral = 0.0
        total_receita_dolar_geral = 0.0
        total_mc_geral = 0.0
        first_webhook_url = None

        last_site_processed = False
        last_site = all_sites[-1] if all_sites else None
        
        webhook_to_sites = {}
        for site_name in all_sites:
            config = db.get_site_config(site_name)
            webhook_url = config.get('slack_webhook_url')
            if not webhook_url:
                continue
            webhook_to_sites.setdefault(webhook_url, []).append(site_name)
        
        for webhook_url, sites in webhook_to_sites.items():
            total_investimento = 0.0
            total_receita_real = 0.0
            total_receita_dolar = 0.0
            total_mc = 0.0
            sites_processados = 0
            total_sites = len(sites)
            roas_lidos = [] 
            for site_name in sites:
                retry = True
                retry_count = 0
                max_retries = 5
                while retry and retry_count < max_retries:
                    try:
                        config = db.get_site_config(site_name)
                        sheet_url = config['sheet_url'] if config and config.get('sheet_url') else None
                        print(f"DEBUG: config retornado para {site_name}: {config}")
                        print(f"DEBUG: webhook_url para {site_name}: {webhook_url}")
                        if not sheet_url:
                            print(f"Site '{site_name}' sem sheet_url cadastrado! Pulando...")
                            break
                        print(f"Processando site: {site_name} ({sheet_url})")
                        sheets_processor = GoogleSheetsProcessor(sheet_url, site_name=site_name)

                        current_date = get_current_date_str()
                        current_month = datetime.now().month
                        current_year = datetime.now().year
                        
  
                        sheets = None
                        sheet_retry = 0
                        while sheets is None and sheet_retry < 3:
                            try:
                                sheets = sheets_processor.get_sheet_ids()
                                if not sheets:
                                    print(f"Nenhuma aba encontrada para {site_name}")
                                    break
                            except Exception as e:
                                sheet_retry += 1
                                if 'RATE_LIMIT_EXCEEDED' in str(e) or '429' in str(e):
                                    wait_time = exponential_backoff(sheet_retry)
                                    print(f"Rate limit ao obter abas de {site_name}. Aguardando {wait_time:.2f}s (tentativa {sheet_retry}/3)")
                                    time.sleep(wait_time)
                                else:
                                    raise
                        
                        if not sheets:
                            break
                            
                        site_investimento = 0.0
                        site_receita_real = 0.0
                        site_receita_dolar = 0.0
                        site_mc = 0.0
                        encontrou_registro = False
                        

                        mes_vigente_sheets = []
                        for sheet in sheets:
                            sheet_name = sheet['name']
                            for mes in ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]:
                                if mes in sheet_name:
                                    mes_num = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"].index(mes) + 1
                                    if mes_num == current_month and str(current_year) in sheet_name:
                                        mes_vigente_sheets.append(sheet)
                                    break
                        

                        if not mes_vigente_sheets and sheets:
                            mes_vigente_sheets = [sheets[0]]
                            print(f"Nenhuma aba do mês vigente encontrada para {site_name}. Usando a primeira aba.")
                            
                        for sheet in mes_vigente_sheets:
                            sheet_id = sheet['id']

                            records = None
                            summary = None
                            actual_name = None
                            read_retry = 0
                            while records is None and read_retry < 3:
                                try:
                                    records, summary, actual_name = sheets_processor.read_data(sheet_id)
                                except Exception as e:
                                    read_retry += 1
                                    if 'RATE_LIMIT_EXCEEDED' in str(e) or '429' in str(e):
                                        wait_time = exponential_backoff(read_retry, max_backoff=30)
                                        print(f"Rate limit ao ler dados de {site_name}, aba {sheet['name']}. Aguardando {wait_time:.2f}s (tentativa {read_retry}/3)")
                                        time.sleep(wait_time)
                                    else:
                                        logging.error(f"Erro ao ler dados de {site_name}, aba {sheet['name']}: {e}")
                                        break
                            
                            if not records:
                                print(f"Nenhum registro encontrado na aba {sheet['name']} de {site_name}")
                                continue
                                
                            pagina = actual_name or sheet['name']
                            aba_mes_vigente = True
                            
                            print(f"[DEBUG] Datas lidas na aba {pagina}: {[r.get('Data') for r in records]}")
                            current_record = None
                            for r in reversed(records):
                                data_val = r.get('Data')
                                if not data_val:
                                    continue
                                data_val_str = str(data_val).strip()
                                matched = False
                                if data_val_str == current_date:
                                    matched = True
                                else:
                                    for fmt in ["%d/%m", "%d/%m/%Y", "%d/%m/%y", "%d-%m", "%d-%m-%Y", "%d-%m-%y"]:
                                        try:
                                            dt_val = datetime.strptime(re.sub(r'\s+', '', data_val_str), fmt)
                                            dt_target = datetime.strptime(current_date, "%d/%m")
                                            if dt_val.day == dt_target.day and dt_val.month == dt_target.month:
                                                matched = True
                                                break
                                        except Exception:
                                            continue
                                    if not matched:
                                        try:
                                            parts = re.split(r'[/-]', data_val_str)
                                            if len(parts) >= 2:
                                                d, m = int(parts[0]), int(parts[1])
                                                dt_target = datetime.strptime(current_date, "%d/%m")
                                                if d == dt_target.day and m == dt_target.month:
                                                    matched = True
                                        except Exception:
                                            pass
                                if matched:
                                    current_record = r
                                    print(f"Encontrou registro para {current_date} em {site_name}, aba {pagina}: {current_record}")
                                    break
                            if not current_record:
                                print(f"Nenhum registro encontrado para data {current_date} na aba {pagina} de {site_name}")
                                continue
                            encontrou_registro = True
                            investimento = clean_value(current_record.get('Investimento', '0,00'))
                            receita = clean_value(current_record.get('Receita', '0,00'))
                            roas_geral = clean_value(current_record.get('ROAS Geral', '0,00'))
                            mc_geral = clean_value(current_record.get('MC Geral', '0,00'))
                            print(f"Valores encontrados para {site_name}: Investimento={investimento}, Receita={receita}, ROAS={roas_geral}, MC={mc_geral}")
                            

                            is_dolar = is_dollar_value(receita)
                            print(f"[DEBUG] Receita '{receita}' detectada como {'DÓLAR' if is_dolar else 'REAL'}")
                            
                            site_investimento += to_float(investimento)
                            if is_dolar:
                                site_receita_dolar += to_float(receita)
                            else:
                                site_receita_real += to_float(receita)
                            site_mc += to_float(mc_geral)
                            site_roas = roas_geral
                            roas_lidos.append(to_float(roas_geral))
                            
                        if site_investimento > 0 or site_receita_real > 0 or site_receita_dolar > 0 or encontrou_registro:
                            roas_geral_str = site_roas
                            
                            if not roas_geral_str or roas_geral_str == '0,00':
                                roas_geral_str = '0,00'
                                
                            roas_emoji = get_roas_emoji(roas_geral_str)
                            mc_emoji = get_mc_emoji(str(site_mc))
                            
                            investimento_str = f"R$ {site_investimento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            receita_real_str = f"R$ {site_receita_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if site_receita_real > 0 else "R$ 0,00"
                            receita_dolar_str = f"$ {site_receita_dolar:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if site_receita_dolar > 0 else "$ 0,00"
                            
                            receipts_msg = ""
                            if site_receita_real > 0 and site_receita_dolar > 0:
                                receipts_msg = f"Receita (R$): *{receita_real_str}*\nReceita ($): *{receita_dolar_str}*"
                            elif site_receita_real > 0:
                                receipts_msg = f"Receita: *{receita_real_str}*"
                            elif site_receita_dolar > 0:
                                receipts_msg = f"Receita: *{receita_dolar_str}*"
                            else:
                                receipts_msg = "Receita: *R$ 0,00*"
                                
                            msg = f":bar_chart: Atualização {site_name} {roas_emoji} {mc_emoji}\n" \
                                f"Investimento: *{investimento_str}*\n" \
                                f"{receipts_msg}\n" \
                                f"ROAS: *{roas_geral_str}*\n" \
                                f"MC: *{mc_geral}*"
                            send_to_slack(msg, webhook_url)
                        
                        total_investimento += site_investimento
                        total_receita_real += site_receita_real
                        total_receita_dolar += site_receita_dolar
                        total_mc += site_mc
                        
                        if not encontrou_registro:
                            send_to_slack(f":warning: Site {site_name} não teve dados para o dia {current_date}.", webhook_url)
                        
                        sites_processados += 1
                        if sites_processados < total_sites:
                            send_to_slack('<==================================:small_blue_diamond:===============================>', webhook_url)
                        
                        retry = False
                        
                    except Exception as e:
                        retry_count += 1
                        if 'RATE_LIMIT_EXCEEDED' in str(e) or '429' in str(e):
                            wait_time = exponential_backoff(retry_count)
                            print(f"Limite de requisições atingido para {site_name}. Aguardando {wait_time:.2f} segundos antes de tentar novamente...")
                            time.sleep(wait_time)
                        else:
                            print(f"Erro ao processar site {site_name}: {e}")
                            print(traceback.format_exc())
                            retry = False

                wait_between_sites = random.uniform(3, 5)
                print(f"Aguardando {wait_between_sites:.2f}s antes de processar o próximo site...")
                time.sleep(wait_between_sites)

            try:
                roas_medio = (total_receita_real + total_receita_dolar) / total_investimento if total_investimento > 0 else 0.0
                roas_medio_str = f"{roas_medio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                investimento_str = f"R$ {total_investimento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                receita_real_str = f"R$ {total_receita_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                receita_dolar_str = f"$ {total_receita_dolar:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                mc_str = f"R$ {total_mc:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                squad_name = config.get('squad_name')
                resumo_title = f"*Resumo Squad {squad_name}:*" if squad_name else "*Resumo do canal:*"
                resumo_msg = [
                    resumo_title,
                    f"Investimento total: {investimento_str}",
                    f"Receita total em reais: {receita_real_str}",
                    f"Receita total em dólares: {receita_dolar_str}",
                    f"ROAS médio: {roas_medio_str}",
                    f"MC total: {mc_str}"
                ]
                resumo_final = "\n".join(resumo_msg)
                send_to_slack('```========================= RESUMO =========================```', webhook_url)
                send_to_slack(resumo_final, webhook_url)
                send_to_slack('<==================================:small_blue_diamond:===============================>', webhook_url)
            except Exception as e:
                send_to_slack(f"Erro ao enviar resumo do canal: {e}", webhook_url)

if __name__ == "__main__":
    if '--agendador' in sys.argv:
        sys.argv.remove('--agendador')
        import schedule
        import time
        import pytz
        from datetime import datetime

        def job():
            print(f"[Agendador] Executando rotina em {datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')}")
            main()

        print("Agendador: executando às 00:23, 03:23, 06:23, 09:23, 12:23, 15:23, 18:23 e 21:23. Pressione Ctrl+C para sair.")
        for hour in range(0, 24, 3):
            schedule.every().day.at(f"{hour:02d}:23").do(job)
        while True:
            schedule.run_pending()
            time.sleep(5)
    else:
        main() 