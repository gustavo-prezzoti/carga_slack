"""
Script para configurar a execução agendada do job Excel para Slack.
Esse script configura o job para executar periodicamente usando o agendador do sistema operacional.
"""

import os
import sys
import platform
import subprocess
import argparse
from pathlib import Path

def get_absolute_path():
    """Obtém o caminho absoluto do diretório atual."""
    return os.path.abspath(os.path.dirname(__file__))

def setup_windows_task(interval_minutes=60):
    """Configura uma tarefa agendada no Windows Task Scheduler."""
    script_path = get_absolute_path()
    python_path = sys.executable
    main_script = os.path.join(script_path, "src", "main.py")
    
    task_name = "ExcelToSlackJob"
    
    command = f'"{python_path}" "{main_script}"'
    
    task_cmd = (
        f'schtasks /create /tn "{task_name}" /tr "{command}" '
        f'/sc minute /mo {interval_minutes} /f'
    )
    
    print(f"Configurando tarefa agendada no Windows Task Scheduler...")
    print(f"Comando: {task_cmd}")
    
    try:
        result = subprocess.run(task_cmd, shell=True, check=True, capture_output=True, text=True)
        print("Tarefa configurada com sucesso!")
        print(f"A tarefa '{task_name}' será executada a cada {interval_minutes} minutos.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erro ao configurar a tarefa: {e}")
        print(f"Saída: {e.stdout}")
        print(f"Erro: {e.stderr}")
        return False

def setup_crontab(interval_minutes=60):
    """Configura um job cron no Linux/macOS."""
    script_path = get_absolute_path()
    python_path = sys.executable
    main_script = os.path.join(script_path, "src", "main.py")
    
    cron_schedule = f"*/{interval_minutes} * * * *"
    cron_entry = f'{cron_schedule} {python_path} {main_script} >> {script_path}/logs/cron.log 2>&1'
    
    print(f"Configurando job no crontab...")
    print(f"Entrada: {cron_entry}")
    
    try:
        current_crontab = subprocess.check_output('crontab -l', shell=True, text=True)
    except subprocess.CalledProcessError:
        current_crontab = ""
    
    if main_script not in current_crontab:
        new_crontab = current_crontab + cron_entry + "\n"
        
        try:
            process = subprocess.Popen('crontab -', stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_crontab)
            
            if process.returncode == 0:
                print("Job configurado com sucesso no crontab!")
                print(f"O job será executado a cada {interval_minutes} minutos.")
                return True
            else:
                print(f"Erro ao configurar o crontab. Código de retorno: {process.returncode}")
                return False
        except Exception as e:
            print(f"Erro ao configurar o crontab: {e}")
            return False
    else:
        print("A entrada já existe no crontab.")
        return True

def main():
    parser = argparse.ArgumentParser(description='Configurar job para processar Excel para Slack')
    parser.add_argument('--interval', type=int, default=60, 
                        help='Intervalo em minutos para execução do job (padrão: 60)')
    args = parser.parse_args()
    
    system = platform.system()
    
    if system == "Windows":
        setup_windows_task(args.interval)
    elif system in ["Linux", "Darwin"]:  
        setup_crontab(args.interval)
    else:
        print(f"Sistema operacional não suportado: {system}")
        print("Por favor, configure o job manualmente para o seu sistema.")

if __name__ == "__main__":
    main() 