import sys
import argparse
import logging
import threading
import time
import os
import logging.handlers

try:
    from PIL import Image, ImageDraw
    import pystray
    HAS_TRAY_LIBS = True
except ImportError:
    HAS_TRAY_LIBS = False


APP_NAME = "Network Print Redirector"
APP_VERSION = "1.0"


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)


parser = argparse.ArgumentParser(
    description=f'{APP_NAME} v{APP_VERSION} - Redirecionador de Impressão Serial via Rede.\nCreated By AzayoDK'
)
parser.add_argument('mode', choices=['client', 'server'], help='Modo de operação: client ou server.')
parser.add_argument('--reconfigure', action='store_true', help='Força a reconfiguração interativa.')
parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Sobrescreve o nível de log da configuração.')
args = parser.parse_args()


log_file_path = None
try:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    log_filename = f"{args.mode}_activity.log"
    log_file_path = os.path.join(base_dir, log_filename)

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)

    initial_log_level = getattr(logging, (args.log_level or "INFO").upper(), logging.INFO)
    file_handler.setLevel(initial_log_level)


    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(initial_log_level)

    log.info(f"--- Iniciando {APP_NAME} v{APP_VERSION} ({args.mode}) ---")
    log.info(f"Logging em arquivo configurado para: {log_file_path}")

except Exception as log_setup_err:
    log.exception("Erro crítico ao configurar logging em arquivo!")

    if getattr(sys, 'frozen', False) and sys.stdin is None:
         try:
             import ctypes
             ctypes.windll.user32.MessageBoxW(0, f"Erro ao configurar logging em arquivo:\n{log_setup_err}", "Logging Error", 0x10)
         except: pass



import config_manager
import client
import server



tray_icon = None
core_logic_thread = None

def create_placeholder_icon(width=64, height=64):
    if not HAS_TRAY_LIBS: return None
    base_dir = config_manager.get_base_dir()
    icon_path = os.path.join(base_dir, "icon.ico")
    if os.path.exists(icon_path):
        try: return Image.open(icon_path)
        except Exception as e: log.warning(f"Erro ao carregar icon.ico: {e}. Usando placeholder.")
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rectangle((10, 10, width-10, height-10), outline='blue', width=3)
    try:

        from PIL import ImageFont
        try:

            font = ImageFont.truetype("arial.ttf", 24)
        except IOError:

             font = ImageFont.load_default()
        d.text((width//4, height//4), "N", fill='blue', font=font)
        d.text((width//2, height//2), "P", fill='red', font=font)
    except ImportError:

         d.text((width//4, height//4), "N", fill='blue')
         d.text((width//2, height//2), "P", fill='red')
    except Exception as font_err:
        log.warning(f"Erro ao desenhar texto no ícone: {font_err}")

        d.line([(15,15), (width-15, height-15)], fill='green', width=5)
        d.line([(15,height-15), (width-15, 15)], fill='green', width=5)
    return image

def show_terminal_action(icon, item):
    log.info("Ação 'Mostrar Info' clicada.")

    log.info("Programa rodando em segundo plano. Verifique os logs para detalhes.")

    if log_file_path and os.path.exists(log_file_path):
        try:
            os.startfile(log_file_path)
        except Exception as e:
            log.error(f"Não foi possível abrir o arquivo de log automaticamente: {e}")

def exit_action(icon, item):
    global core_logic_thread, tray_icon
    log.info("Ação 'Sair' clicada no menu da bandeja.")
    log.info("Sinalizando para a thread de lógica principal parar...")
    if args.mode == 'client': client.stop_client()
    elif args.mode == 'server': server.stop_server()
    else: log.warning("Modo desconhecido ao tentar sair via bandeja.")
    if core_logic_thread and core_logic_thread.is_alive():
        log.info(f"Aguardando a thread '{core_logic_thread.name}' finalizar...")
        core_logic_thread.join(timeout=7.0)
        if core_logic_thread.is_alive(): log.warning(f"Thread '{core_logic_thread.name}' não finalizou a tempo.")
        else: log.info(f"Thread '{core_logic_thread.name}' finalizada.")
    if tray_icon:
        log.info("Parando ícone da bandeja...")
        try:
            tray_icon.stop()
            log.info("Ícone da bandeja parado.")
        except Exception as e: log.error(f"Erro ao parar o ícone da bandeja: {e}", exc_info=True)
    log.info("Processo principal deve encerrar agora.")


def run_admin_list_clients(icon, item):

    log.info("\n--- Executando: Listar Clientes (via menu) ---")
    server.show_connected_clients()

def run_admin_reconfigure(icon, item):
    log.info("\n--- Executando: Reconfigurar Servidor (via menu) ---")


    warn_msg = "A reconfiguração interativa requer um terminal. Use a versão console:\nNetworkRedirector.exe server --reconfigure"
    log.warning(warn_msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, warn_msg, "Reconfiguração", 0x40 | 0x1000)
    except Exception as e:
        log.error(f"Falha ao mostrar aviso de reconfiguração: {e}")


def run_admin_show_logs(icon, item):
    log.info("\n--- Executando: Mostrar Logs Recentes (via menu) ---")

    show_terminal_action(icon, item)



def start_core_logic(mode, config):
    log.info(f"Iniciando lógica principal para modo: {mode} na thread: {threading.current_thread().name}")
    success = False
    try:

        log_level_str = config.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logging.getLogger().setLevel(log_level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(log_level)
        log.info(f"Nível de log final definido para {log_level_str} ({log_level})")


        if log_file_path:
             if mode == 'client': client.client_state["log_file_path"] = log_file_path
             if mode == 'server': server.server_state["log_file_path"] = log_file_path


        if mode == 'client': success = client.run_client(start_config=config)
        elif mode == 'server': success = server.run_server(start_config=config)
        else: log.error(f"Modo desconhecido na thread de lógica: {mode}")

        if not success:
             log.critical(f"Falha ao iniciar a lógica principal do {mode}.")
             if tray_icon:
                 log.info("Tentando parar o tray icon devido à falha na inicialização.")
                 try: tray_icon.stop()
                 except Exception as e: log.error(f"Erro ao parar tray icon na falha: {e}")
        else:
            log.info(f"Lógica principal do {mode} iniciada com sucesso e rodando.")


    except Exception as e:
        log.critical(f"Erro fatal na thread de lógica principal ({mode}): {e}", exc_info=True)
        if tray_icon:
            log.info("Tentando parar o tray icon devido a erro fatal na lógica.")
            try: tray_icon.stop()
            except Exception as e_stop: log.error(f"Erro ao parar tray icon no erro fatal: {e_stop}")
    log.info(f"Thread de lógica principal ({mode}) finalizando.")


def get_main_base_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):

        return os.path.dirname(sys.executable)
    else:

        return os.path.dirname(os.path.abspath(__file__))


if __name__ == "__main__":


    try:
        config = config_manager.get_config(args.mode, args.reconfigure)

    except Exception as config_err:

         log.critical(f"Erro fatal ao obter configuração: {config_err}", exc_info=True)
         if getattr(sys, 'frozen', False) and sys.stdin is None:
             try:
                 import ctypes
                 ctypes.windll.user32.MessageBoxW(0, f"Erro fatal ao obter configuração:\n{config_err}", "Configuration Error", 0x10)
             except: pass
         sys.exit(1)



    if args.log_level:
        log.info(f"Nível de log solicitado via argumento: {args.log_level}.")


    run_bg = config.get('run_in_background', False)
    is_windowed_exe = getattr(sys, 'frozen', False) and sys.stdin is None


    if is_windowed_exe and not run_bg:
        log.warning("Executável compilado como janela (--windowed) mas 'run_in_background' está 'false' na configuração. Executando em modo bandeja.")
        run_bg = True

    if run_bg:

        log.info("Modo 'run_in_background' ativo. Iniciando com ícone na bandeja.")
        if not HAS_TRAY_LIBS:
            err_msg = "Bibliotecas 'pystray' e 'Pillow' não encontradas. Não é possível rodar em background."
            log.critical(err_msg + " Instale com: pip install pystray Pillow")
            if is_windowed_exe:
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(0, err_msg, "Dependency Error", 0x10)
                except: pass
            else: print(err_msg, file=sys.stderr)
            sys.exit(1)


        icon_image = None
        icon_path = os.path.join(get_main_base_dir(), "icon.ico")
        try:
            icon_image = Image.open(icon_path)
            log.info(f"Ícone carregado de: {icon_path}")
        except FileNotFoundError:
            log.warning(f"Arquivo de ícone '{icon_path}' não encontrado. Usando ícone placeholder.")
            icon_image = create_placeholder_icon()
        except Exception as e:
            log.error(f"Erro ao carregar ícone '{icon_path}': {e}. Usando ícone placeholder.")
            icon_image = create_placeholder_icon()

        if not icon_image:

             err_msg = "Falha ao carregar ou criar o ícone da bandeja."
             log.critical(err_msg)
             if is_windowed_exe:
                 try:
                     import ctypes
                     ctypes.windll.user32.MessageBoxW(0, err_msg, "Icon Error", 0x10)
                 except: pass
             sys.exit(1)


        menu_items = [ pystray.MenuItem('Abrir Log', show_terminal_action) ]
        if args.mode == 'server':
             admin_menu = pystray.Menu(
                  pystray.MenuItem('Listar Clientes (Ver Log)', run_admin_list_clients),
                  pystray.MenuItem('Reconfigurar (Use Console)', run_admin_reconfigure),
                  pystray.MenuItem('Mostrar Logs Recentes (Abrir Log)', run_admin_show_logs)
             )
             menu_items.append(pystray.MenuItem('Menu Admin', admin_menu))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem('Sair', exit_action))
        menu = pystray.Menu(*menu_items)

        tray_icon = pystray.Icon(f"{APP_NAME}-{args.mode}", icon_image, f"{APP_NAME} ({args.mode.capitalize()})", menu)

        core_logic_thread = threading.Thread(target=start_core_logic, args=(args.mode, config), name=f"{args.mode.capitalize()}CoreLogic")
        core_logic_thread.daemon = False
        core_logic_thread.start()
        log.info(f"Thread '{core_logic_thread.name}' iniciada. Iniciando loop da bandeja.")

        try:
             tray_icon.run()
             log.info("Loop da bandeja finalizado via stop().")
        except Exception as e:
             log.error(f"Erro inesperado no loop do tray icon: {e}", exc_info=True)
             exit_action(None, None)
        finally:
             log.info("Saindo do bloco try/except/finally do tray_icon.run().")

    else:

        log.info("Rodando em modo normal (terminal interativo).")

        success = False
        main_logic_instance_thread = None
        try:
            if args.mode == 'client':
                if client.run_client(start_config=config):
                     main_logic_instance_thread = client.client_state.get("main_thread")
                     success = True
            elif args.mode == 'server':
                if server.run_server(start_config=config):
                     main_logic_instance_thread = server.server_state.get("listener_thread")
                     success = True

            if success and main_logic_instance_thread:
                 log.info(f"Lógica principal do {args.mode} iniciada. Pressione Ctrl+C para sair.")
                 while main_logic_instance_thread.is_alive():
                      main_logic_instance_thread.join(timeout=1.0)
                 log.info(f"Thread de lógica principal ({main_logic_instance_thread.name}) terminou.")
            elif not success:
                 log.critical(f"Falha ao iniciar {args.mode} em modo normal.")

        except KeyboardInterrupt:
            log.info("Ctrl+C recebido no modo terminal. Solicitando encerramento...")
            if args.mode == 'client': client.stop_client()
            elif args.mode == 'server': server.stop_server()
            if main_logic_instance_thread and main_logic_instance_thread.is_alive():
                 log.info(f"Aguardando thread {main_logic_instance_thread.name} finalizar após Ctrl+C...")
                 main_logic_instance_thread.join(timeout=5.0)
        except Exception as e:
            log.critical(f"Erro não esperado no loop principal de espera do modo terminal: {e}", exc_info=True)
            try:
                if args.mode == 'client': client.stop_client()
                elif args.mode == 'server': server.stop_server()
            except Exception as stop_err: log.error(f"Erro ao tentar parar na exceção principal: {stop_err}")
        finally:
             log.info("Programa principal (modo terminal) finalizado.")
             if getattr(sys, 'frozen', False):

                 if sys.stdin is not None:
                    input("Pressione Enter para fechar esta janela...")
