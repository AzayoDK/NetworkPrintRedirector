import json
import os
import logging
import sys
from collections.abc import MutableMapping
import ctypes

log = logging.getLogger(__name__)

CONFIG_VERSION = "v2"
CLIENT_CONFIG_FILE = f"client_config_{CONFIG_VERSION}.json"
SERVER_CONFIG_FILE = f"server_config_{CONFIG_VERSION}.json"

DEFAULT_CONFIGS = {
    'client': {
        'server_ip': {'type': str, 'default': '127.0.0.1', 'prompt': "Digite o valor para 'server_ip' (IP do servidor)"},
        'server_port': {'type': int, 'default': 8000, 'prompt': "Digite o valor para 'server_port' (Porta TCP do servidor)"},
        'retry_interval': {'type': float, 'default': 5.0, 'prompt': "Digite o valor para 'retry_interval' (Segundos entre tentativas de reconexão)"},
        'serial_port': {'type': str, 'default': 'COM1', 'prompt': "Digite o valor para 'serial_port' (Porta serial local para LER)"},
        'baud_rate': {'type': int, 'default': 9600, 'prompt': "Digite o valor para 'baud_rate' (Velocidade da porta serial)"},
        'buffer_size': {'type': int, 'default': 1024, 'prompt': "Digite o valor para 'buffer_size' (Tamanho do buffer de leitura/envio em bytes)"},
        'log_level': {'type': str, 'default': 'INFO', 'prompt': "Digite o valor para 'log_level' (DEBUG, INFO, WARNING, ERROR)"},
        'rsa_key_size': {'type': int, 'default': 2048, 'prompt': "Digite o valor para 'rsa_key_size' (Tamanho da chave RSA)"},
        'run_in_background': {'type': bool, 'default': False, 'prompt': 'Iniciar minimizado na bandeja do sistema? (true/false)'}
    },
    'server': {
        'listen_ip': {'type': str, 'default': '0.0.0.0', 'prompt': "Digite o valor para 'listen_ip' (IP para ESCUTAR conexões, 0.0.0.0 para todos)"},
        'listen_port': {'type': int, 'default': 8000, 'prompt': "Digite o valor para 'listen_port' (Porta TCP para ESCUTAR)"},
        'max_clients': {'type': int, 'default': 5, 'prompt': "Digite o valor para 'max_clients' (Número máximo de clientes simultâneos)"},
        'serial_port': {'type': str, 'default': 'COM3', 'prompt': "Digite o valor para 'serial_port' (Porta serial local para ESCREVER)"},
        'baud_rate': {'type': int, 'default': 9600, 'prompt': "Digite o valor para 'baud_rate' (Velocidade da porta serial)"},
        'buffer_size': {'type': int, 'default': 1024, 'prompt': "Digite o valor para 'buffer_size' (Tamanho do buffer de recebimento/escrita em bytes)"},
        'log_level': {'type': str, 'default': 'INFO', 'prompt': "Digite o valor para 'log_level' (DEBUG, INFO, WARNING, ERROR)"},
        'rsa_key_size': {'type': int, 'default': 2048, 'prompt': "Digite o valor para 'rsa_key_size' (Tamanho da chave RSA)"},
        'run_in_background': {'type': bool, 'default': False, 'prompt': 'Iniciar minimizado na bandeja do sistema? (true/false)'}
    }
}

def get_base_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path(mode):
    base_dir = get_base_dir()
    if mode == 'client':
        filename = CLIENT_CONFIG_FILE
    elif mode == 'server':
        filename = SERVER_CONFIG_FILE
    else:
        log.error(f"Modo inválido solicitado para get_config_path: {mode}")
        return None
    config_path = os.path.join(base_dir, filename)
    return config_path

def load_config(mode):
    config_path = get_config_path(mode)
    if not config_path:
        log.warning(f"Não foi possível determinar o caminho da configuração para o modo '{mode}'.")
        return None
    if not os.path.exists(config_path):
        log.info(f"Arquivo de configuração '{os.path.basename(config_path)}' não encontrado.")
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        log.info(f"Configuração carregada de '{os.path.basename(config_path)}'.")
        return config
    except json.JSONDecodeError:
        log.error(f"Erro ao decodificar JSON no arquivo '{os.path.basename(config_path)}'. Verifique a sintaxe.")
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao carregar configuração de '{os.path.basename(config_path)}': {e}", exc_info=True)
        return None

def save_config(mode, config):
    config_path = get_config_path(mode)
    if not config_path:
        log.error(f"Modo inválido ou erro ao obter caminho para salvar configuração '{mode}'.")
        return False
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        log.info(f"Configuração salva em '{os.path.basename(config_path)}' no diretório '{os.path.dirname(config_path)}'.")
        return True
    except PermissionError:
        log.critical(f"Erro de permissão ao tentar salvar configuração em '{config_path}'. Verifique as permissões de escrita.")
        return False
    except Exception as e:
        log.error(f"Erro ao salvar configuração em '{config_path}': {e}", exc_info=True)
        return False

def configure_interactively(mode, current_config=None):
    print(f"\n--- Configuração Interativa ({mode.capitalize()}) ---")
    defaults = DEFAULT_CONFIGS.get(mode)
    if not defaults:
        log.error(f"Modo de configuração desconhecido: {mode}.")
        return None

    config = current_config if isinstance(current_config, MutableMapping) else {}
    new_config_data = {}
    updated = False

    for key, settings in defaults.items():
        prompt_text = settings['prompt']
        default_value_to_show = config.get(key, settings['default'])
        prompt_text += f" (padrão: {default_value_to_show}): "

        while True:
            user_input = input(prompt_text).strip()
            if not user_input:
                value = default_value_to_show
                break
            else:
                try:
                    target_type = settings['type']
                    if target_type == int: value = int(user_input)
                    elif target_type == float: value = float(user_input)
                    elif target_type == bool:
                        if user_input.lower() in ['true', 't', 'sim', 's', '1', 'yes', 'y']: value = True
                        elif user_input.lower() in ['false', 'f', 'nao', 'n', '0', 'no']: value = False
                        else: raise ValueError("Entrada booleana inválida. Use true/false, sim/nao, 1/0.")
                    else:
                        if key == 'log_level' and user_input.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                             raise ValueError("Nível de log inválido.")
                        value = str(user_input)
                    break
                except ValueError as e:
                    print(f"Entrada inválida: {e}. Por favor, tente novamente.")

        new_config_data[key] = value
        if key not in config or config.get(key) != value:
            updated = True

    for key, settings in defaults.items():
        if key not in new_config_data:
            new_config_data[key] = settings['default']
            updated = True

    if updated:
        if save_config(mode, new_config_data):
            print("Configuração salva com sucesso.")
            return new_config_data
        else:
            print("Erro crítico: Falha ao salvar a configuração.")
            return None
    else:
        print("Nenhuma configuração alterada.")
        return new_config_data

def get_config(mode, reconfigure=False):
    """Obtém a configuração, carregando ou iniciando a configuração interativa."""
    config = load_config(mode)
    config_needed = reconfigure or not config

    if config_needed:
        is_windowed_likely = getattr(sys, 'frozen', False) and sys.stdin is None

        if is_windowed_likely:
            error_title = f"{mode.capitalize()} Configuration Error"
            error_message = (
                f"Arquivo de configuração '{os.path.basename(get_config_path(mode))}' não encontrado ou reconfiguração solicitada.\n\n"
                "Não é possível executar a configuração interativa no modo janela (sem console).\n\n"
                f"Por favor, execute o programa a partir de um terminal primeiro para criar o arquivo:\n"
                f"> NetworkRedirector.exe {mode} --reconfigure"
            )
            log.critical(error_message.replace('\n\n', ' ').replace('\n', ' '))

            try:
                ctypes.windll.user32.MessageBoxW(0, error_message, error_title, 0x10 | 0x1000)
            except Exception as mb_error:
                log.error(f"Falha ao exibir MessageBox: {mb_error}")

            sys.exit(1)

        if not config:
            log.info(f"Configuração para '{mode}' não encontrada ou inválida.")
        else:
            log.info(f"Opção '--reconfigure' usada para '{mode}'.")
        print(f"Iniciando configuração interativa para {mode}...")

        new_config = configure_interactively(mode, current_config=config)

        if new_config is None:
             log.critical(f"Falha crítica durante a configuração interativa de '{mode}'. Encerrando.")
             if getattr(sys, 'frozen', False): input("Pressione Enter para sair...")
             sys.exit(1)
        config = new_config

    if not isinstance(config, MutableMapping):
        log.critical(f"Erro inesperado: Configuração final para '{mode}' não é um dicionário válido. Encerrando.")
        if getattr(sys, 'frozen', False) and sys.stdin is not None: input("Pressione Enter para sair...")
        sys.exit(1)

    return config