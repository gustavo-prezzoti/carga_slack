"""
Script para ajudar a configurar as credenciais do Google Sheets API.

Este script irá guiar o usuário no processo de obtenção e configuração 
das credenciais necessárias para acessar o Google Sheets.
"""

import os
import json
import sys
from pathlib import Path

def print_colored(text, color):
    """Imprime texto colorido no terminal."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m'
    }
    
    print(f"Tentando imprimir texto colorido: {text}")
    print(f"{colors.get(color, '')}{text}{colors['reset']}")

def main():
    print("Iniciando script de configuração de credenciais...")
    
    print_colored("\n=== Configuração de Credenciais do Google Sheets ===\n", "cyan")
    print("Este assistente irá ajudá-lo a configurar as credenciais para acessar o Google Sheets.")
    print_colored("\nPasso 1: Criar um projeto no Google Cloud e habilitar a API do Google Sheets", "yellow")
    print("1. Acesse https://console.cloud.google.com/")
    print("2. Crie um novo projeto ou selecione um existente")
    print("3. No menu lateral, vá para 'APIs e Serviços' > 'Biblioteca'")
    print("4. Pesquise por 'Google Sheets API' e habilite-a")
    print("5. Faça o mesmo para 'Google Drive API'")
    
    input_continue = input("\nPressione Enter quando concluir este passo...\n")
    
    print_colored("\nPasso 2: Criar credenciais de conta de serviço", "yellow")
    print("1. No menu lateral, vá para 'APIs e Serviços' > 'Credenciais'")
    print("2. Clique em 'Criar Credenciais' > 'Conta de serviço'")
    print("3. Dê um nome para a conta de serviço e clique em 'Criar'")
    print("4. Em 'Conceder a esta conta de serviço acesso ao projeto', selecione 'Editor' e clique em 'Continuar'")
    print("5. Clique em 'Concluído'")
    
    input_continue = input("\nPressione Enter quando concluir este passo...\n")
    
    print_colored("\nPasso 3: Criar e baixar a chave JSON", "yellow")
    print("1. Na lista de contas de serviço, clique na conta que você acabou de criar")
    print("2. Vá para a aba 'Chaves'")
    print("3. Clique em 'Adicionar Chave' > 'Criar nova chave'")
    print("4. Selecione 'JSON' e clique em 'Criar'")
    print("5. O arquivo JSON será baixado automaticamente para o seu computador")
    
    input_continue = input("\nPressione Enter quando concluir este passo...\n")
    
    print_colored("\nPasso 4: Informar o caminho do arquivo de credenciais", "yellow")
    credentials_path = input("Digite o caminho completo para o arquivo JSON de credenciais baixado:\n")
    
    if not os.path.exists(credentials_path):
        print_colored(f"Erro: O arquivo {credentials_path} não existe.", "red")
        return
    
    dest_path = Path("credentials.json")
    try:
        with open(credentials_path, 'r') as source_file:
            credentials_data = json.load(source_file)
        
        with open(dest_path, 'w') as dest_file:
            json.dump(credentials_data, dest_file, indent=2)
        
        print_colored(f"\nCredenciais salvas com sucesso em {dest_path}", "green")
    except Exception as e:
        print_colored(f"Erro ao copiar o arquivo de credenciais: {e}", "red")
        return
    
    print_colored("\nPasso 5: Compartilhar a planilha com a conta de serviço", "yellow")
    print("1. Abra a planilha do Google Sheets que você quer acessar")
    print("2. Clique no botão 'Compartilhar' no canto superior direito")
    print("3. No campo 'Adicionar pessoas e grupos', insira o email da conta de serviço")
    print("   (Você pode encontrar o email no arquivo de credenciais, no campo 'client_email')")
    print("4. Selecione 'Editor' nas permissões e clique em 'Enviar'")
    
    try:
        with open(dest_path, 'r') as f:
            creds = json.load(f)
            client_email = creds.get('client_email', '')
            if client_email:
                print_colored(f"\nEmail da conta de serviço: {client_email}", "cyan")
                print("Copie este email e compartilhe sua planilha com ele.")
    except Exception as e:
        print_colored(f"Não foi possível ler o email da conta de serviço: {e}", "red")
    
    print_colored("\nConfigurações de credenciais concluídas!", "green")
    print("Agora você pode executar o programa para acessar o Google Sheets.")

if __name__ == "__main__":
    main() 