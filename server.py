import time
import threading
import logging
import socket
import select
import os

import config_manager
import crypto_utils
import network_utils
import serial_utils

log = logging.getLogger(__name__)


server_state = {
    "server_socket": None,
    "serial_port": None,
    "clients": {},
    "stop_event": threading.Event(),
    "config": {},
    "server_private_key": None,
    "server_public_key": None,
    "listener_thread": None,
    "log_file_path": None
}


def ensure_serial_open():
    """Tenta abrir/reabrir a porta serial se necessário."""
    if server_state["serial_port"] and server_state["serial_port"].is_open:
        return True

    config = server_state["config"]
    log.info(f"Tentando abrir porta serial {config['serial_port']}...")
    server_state["serial_port"] = serial_utils.open_serial_port(
        config['serial_port'],
        config['baud_rate'],
        timeout=0.1,
        write_timeout=config.get('serial_timeout', 1.0)
    )
    if server_state["serial_port"]:
        log.info(f"Porta serial {config['serial_port']} aberta.")
        return True
    else:
        log.error(f"Falha ao abrir porta serial {config['serial_port']}. Tentará novamente mais tarde.")
        return False

def close_client_connection(conn, addr):
    """Fecha a conexão com um cliente específico."""
    client_info = server_state["clients"].pop(conn, None)
    if client_info:
        log.info(f"Fechando conexão com cliente {addr}...")
        client_info["stop_event"].set()
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        try:
            conn.close()
        except OSError: pass


        log.info(f"Conexão com cliente {addr} fechada.")
    else:

        try:
            conn.close()
        except Exception: pass



def handle_client_thread(conn, addr, stop_event):
    """Thread para lidar com um cliente individual."""
    log.info(f"Thread iniciada para cliente {addr}.")
    config = server_state["config"]
    client_public_key = None
    buffer_size = config.get('buffer_size', 1024)
    serial_ok = False
    last_serial_check = 0
    serial_check_interval = 5.0

    try:

        log.info(f"[{addr}] Aguardando chave pública do cliente...")
        client_pub_key_bytes = network_utils.receive_data(conn, timeout=10.0)
        if client_pub_key_bytes is None or client_pub_key_bytes == b'':
             log.error(f"[{addr}] Cliente desconectou ou timeout ao esperar chave pública.")
             return

        client_public_key = crypto_utils.load_public_key_from_data(client_pub_key_bytes)
        if not client_public_key:
            log.error(f"[{addr}] Falha ao carregar/validar chave pública do cliente.")
            return

        log.info(f"[{addr}] Chave pública do cliente recebida e carregada.")

        if conn in server_state["clients"]:
            server_state["clients"][conn]["public_key"] = client_public_key


        server_pub_key_bytes = crypto_utils.get_public_key_bytes(server_state["server_public_key"])
        if not server_pub_key_bytes or not network_utils.send_data(conn, server_pub_key_bytes):
            log.error(f"[{addr}] Falha ao enviar chave pública do servidor para o cliente.")
            return
        log.info(f"[{addr}] Chave pública do servidor enviada.")


        while not stop_event.is_set() and not server_state["stop_event"].is_set():

            ready_to_read, _, _ = select.select([conn], [], [], 0.1)

            if ready_to_read:
                encrypted_data = network_utils.receive_data(conn, buffer_size)

                if encrypted_data is None:
                    log.info(f"[{addr}] Cliente desconectou.")
                    break
                elif encrypted_data == b'':

                    pass
                else:
                    log.debug(f"[{addr}] Recebidos {len(encrypted_data)} bytes criptografados.")


                    decrypted_data = crypto_utils.decrypt_message(
                        server_state["server_private_key"],
                        encrypted_data
                    )

                    if decrypted_data is None:
                        log.error(f"[{addr}] Falha ao descriptografar dados recebidos. Ignorando.")

                        continue
                    elif decrypted_data == b'':
                         log.warning(f"[{addr}] Descriptografia resultou em dados vazios. Ignorando.")
                         continue

                    log.info(f"[{addr}] Dados descriptografados ({len(decrypted_data)} bytes). Tentando escrever na serial...")


                    now = time.time()
                    if not serial_ok or not server_state["serial_port"] or not server_state["serial_port"].is_open:
                         if now - last_serial_check > serial_check_interval:
                              serial_ok = ensure_serial_open()
                              last_serial_check = now
                         else:
                              serial_ok = False
                    else:
                        serial_ok = True

                    if serial_ok and server_state["serial_port"]:

                        if serial_utils.write_to_serial(server_state["serial_port"], decrypted_data):
                            log.info(f"[{addr}] {len(decrypted_data)} bytes escritos com sucesso na porta serial {config['serial_port']}.")
                        else:
                            log.error(f"[{addr}] Falha ao escrever na porta serial {config['serial_port']}. Dados perdidos.")

                            serial_utils.close_serial_port(server_state["serial_port"])
                            server_state["serial_port"] = None
                            serial_ok = False
                            last_serial_check = 0
                    else:
                        log.error(f"[{addr}] Porta serial não está disponível. Dados perdidos.")
                        last_serial_check = 0
            else:

                 pass

    except ConnectionResetError:
        log.info(f"[{addr}] Conexão redefinida pelo cliente.")
    except socket.timeout:
         log.warning(f"[{addr}] Timeout na operação de socket.")
    except Exception as e:
        log.error(f"[{addr}] Erro inesperado na thread do cliente: {e}", exc_info=True)
    finally:
        log.info(f"Encerrando thread para cliente {addr}.")
        close_client_connection(conn, addr)


def accept_connections_thread():
    """Thread para aceitar novas conexões de clientes."""
    log.info("Thread de escuta iniciada. Aguardando conexões...")
    config = server_state["config"]
    max_clients = config.get('max_clients', 5)

    while not server_state["stop_event"].is_set():
        try:

            ready_to_read, _, _ = select.select([server_state["server_socket"]], [], [], 1.0)

            if ready_to_read:
                conn, addr = server_state["server_socket"].accept()
                log.info(f"Nova conexão recebida de {addr}.")

                if len(server_state["clients"]) >= max_clients:
                    log.warning(f"Número máximo de clientes ({max_clients}) atingido. Rejeitando {addr}.")
                    try:

                        conn.sendall(b"ERRO: Servidor cheio.\n")
                    except Exception: pass
                    conn.close()
                    continue


                client_stop_event = threading.Event()
                client_thread = threading.Thread(
                    target=handle_client_thread,
                    args=(conn, addr, client_stop_event),
                    name=f"ClientThread-{addr}"
                )
                server_state["clients"][conn] = {
                    "addr": addr,
                    "thread": client_thread,
                    "stop_event": client_stop_event,
                    "public_key": None
                }
                client_thread.start()
                log.info(f"Cliente {addr} adicionado. Clientes conectados: {len(server_state['clients'])}")

        except socket.timeout:
             continue
        except OSError as e:

             if server_state["stop_event"].is_set():
                  log.info("Socket do servidor fechado. Encerrando thread de escuta.")
                  break
             else:
                  log.error(f"Erro no accept: {e}. Tentando continuar...", exc_info=True)
                  time.sleep(1)
        except Exception as e:
            if server_state["stop_event"].is_set():
                log.info("Parada solicitada durante accept/select.")
                break
            log.error(f"Erro inesperado ao aceitar conexões: {e}", exc_info=True)
            time.sleep(1)

    log.info("Thread de escuta finalizada.")


def show_connected_clients():
    """Mostra informações sobre os clientes conectados."""
    print("\n--- Clientes Conectados ---")
    if not server_state["clients"]:
        print("Nenhum cliente conectado.")
    else:
        print(f"Total: {len(server_state['clients'])}")
        i = 1

        clients_copy = dict(server_state["clients"])
        for conn, info in clients_copy.items():
            addr = info.get('addr', 'N/A')

            key_info = "Sim" if info.get('public_key') else "Não (Aguardando)"
            print(f"{i}. Endereço: {addr}, Chave Pública Recebida: {key_info}")
            i += 1
    print("--------------------------\n")

def reconfigure_server():
    """Inicia a reconfiguração interativa do servidor."""
    print("\n--- Reconfigurar Servidor ---")
    config = server_state.get("config", {})
    new_config = config_manager.configure_interactively('server', current_config=config)
    if new_config:
        server_state["config"] = new_config
        print("\n[ATENÇÃO] Configuração atualizada. É necessário reiniciar o servidor para aplicar todas as alterações.")


    else:
        print("Reconfiguração cancelada ou falhou.")
    print("---------------------------\n")

def show_recent_logs(num_lines=20):
    """Mostra as últimas N linhas do arquivo de log."""
    print(f"\n--- Últimas {num_lines} Linhas do Log ---")
    log_path = server_state.get("log_file_path")
    if not log_path or not os.path.exists(log_path):
        print(f"Arquivo de log '{log_path or 'N/A'}' não encontrado.")
        print("---------------------------------\n")
        return

    try:
        with open(log_path, 'r') as f:

            lines = f.readlines()
            for line in lines[-num_lines:]:
                print(line.strip())
    except Exception as e:
        print(f"Erro ao ler arquivo de log: {e}")
    print("---------------------------------\n")



def run_server(start_config=None):
    """Função principal para configurar e iniciar o servidor."""
    if start_config:
        server_state["config"] = start_config
    config = server_state["config"]


    log_level_str = config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "server_activity.log")
    server_state["log_file_path"] = log_file
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level)



    log.addHandler(file_handler)
    logging.getLogger('crypto_utils').addHandler(file_handler)
    logging.getLogger('network_utils').addHandler(file_handler)
    logging.getLogger('serial_utils').addHandler(file_handler)
    logging.getLogger('config_manager').addHandler(file_handler)


    logging.getLogger().setLevel(log_level)
    log.info(f"Nível de log configurado para: {log_level_str}")
    log.info("Logs também estão sendo salvos em: server_activity.log")
    log.info("--- Iniciando Servidor Network Print Redirector v2.0.2 ---")


    priv_key = crypto_utils.load_private_key('server')
    pub_key = crypto_utils.load_public_key_from_file('server')
    if not priv_key or not pub_key:
        log.warning("Chaves RSA do servidor não encontradas ou inválidas. Gerando novo par...")
        key_size = config.get("rsa_key_size", 2048)
        priv_key, pub_key = crypto_utils.generate_keys('server', key_size=key_size)
        if not priv_key or not pub_key:
            log.critical("Falha ao gerar/carregar chaves RSA do servidor. Encerrando.")
            return False
    server_state["server_private_key"] = priv_key
    server_state["server_public_key"] = pub_key
    log.info("Chaves RSA do servidor carregadas/geradas.")



    server_state["serial_port"] = None



    listen_ip = config.get('listen_ip', '0.0.0.0')
    listen_port = config.get('listen_port', 8000)
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((listen_ip, listen_port))
        server_socket.listen(config.get('max_clients', 5))
        server_socket.setblocking(False)
        server_state["server_socket"] = server_socket
        log.info(f"Servidor escutando em {listen_ip}:{listen_port}")
    except Exception as e:
        log.critical(f"Falha ao iniciar o socket do servidor em {listen_ip}:{listen_port}: {e}", exc_info=True)
        return False


    server_state["stop_event"].clear()
    listener_thread = threading.Thread(target=accept_connections_thread, name="ListenerThread")
    server_state["listener_thread"] = listener_thread
    listener_thread.start()


    return True


def stop_server():
    log.info("Solicitando encerramento do servidor...")
    server_state["stop_event"].set()


    server_socket = server_state.get("server_socket")
    if server_socket:
        try:
            server_socket.close()
            log.info("Socket do servidor fechado.")
        except Exception as e:
            log.warning(f"Erro ao fechar socket do servidor: {e}")


    listener_thread = server_state.get("listener_thread")
    if listener_thread and listener_thread.is_alive():
        log.info("Aguardando thread de escuta finalizar...")
        listener_thread.join(timeout=3.0)
        if listener_thread.is_alive():
            log.warning("Thread de escuta não finalizou a tempo.")


    log.info("Fechando conexões de clientes...")

    clients_copy = dict(server_state["clients"])
    threads_to_join = []
    for conn, client_info in clients_copy.items():
         addr = client_info.get('addr', 'N/A')
         close_client_connection(conn, addr)
         thread = client_info.get("thread")
         if thread and thread.is_alive():
              threads_to_join.append(thread)


    if threads_to_join:
         log.info(f"Aguardando {len(threads_to_join)} threads de cliente finalizarem...")
         for thread in threads_to_join:
              thread.join(timeout=1.0)


    serial_utils.close_serial_port(server_state.get("serial_port"))

    log.info("Servidor encerrado.")
