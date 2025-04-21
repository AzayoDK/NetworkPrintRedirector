import time
import threading
import logging
import socket
import os
import struct

import config_manager
import crypto_utils
import network_utils
import serial_utils

log = logging.getLogger(__name__)


client_state = {
    "serial_port": None,
    "server_connection": None,
    "stop_event": threading.Event(),
    "config": {},
    "client_private_key": None,
    "client_public_key": None,
    "server_public_key": None,
    "main_thread": None,
    "log_file_path": None
}


def ensure_serial_open():
    """Tenta abrir/reabrir a porta serial se necessário."""
    if client_state["serial_port"] and client_state["serial_port"].is_open:
        return True

    config = client_state["config"]
    log.info(f"Tentando abrir porta serial {config['serial_port']}...")
    client_state["serial_port"] = serial_utils.open_serial_port(
        config['serial_port'],
        config['baud_rate'],
        timeout=0.1,
    )
    if client_state["serial_port"]:
        log.info(f"Porta serial {config['serial_port']} aberta.")
        return True
    else:
        log.error(f"Falha ao abrir porta serial {config['serial_port']}. Tentará novamente mais tarde.")
        return False

def ensure_server_connection():
    """Tenta conectar/reconectar ao servidor se necessário e realiza troca de chaves."""
    if client_state["server_connection"]:
        try:
            pass
            return True
        except (OSError, ConnectionResetError) as e:
            log.warning(f"Erro ao verificar conexão existente: {e}. Tentando reconectar.")
            close_server_connection()

    config = client_state["config"]
    log.info("Tentando conectar ao servidor...")
    conn = network_utils.connect_to_server(
        config['server_ip'],
        config['server_port'],
        retry_interval=config.get('retry_interval', 5.0) / 2,
        max_retries=1
    )

    if conn:
        log.info("Conexão com servidor estabelecida. Iniciando troca de chaves...")
        client_pub_key_bytes = crypto_utils.get_public_key_bytes(client_state["client_public_key"])
        if not client_pub_key_bytes or not network_utils.send_data(conn, client_pub_key_bytes):
            log.error("Falha ao enviar chave pública do cliente para o servidor. Desconectando.")
            try:
                conn.close()
            except Exception: pass
            return False

        log.info("Chave pública do cliente enviada. Aguardando chave pública do servidor...")

        server_pub_key_bytes = network_utils.receive_data(conn, timeout=10.0)
        if server_pub_key_bytes is None:
            log.error("Servidor desconectou ou erro ao receber chave pública do servidor.")
            try:
                conn.close()
            except Exception: pass
            return False
        elif server_pub_key_bytes == b'':
            log.error("Timeout ao esperar chave pública do servidor.")
            try:
                conn.close()
            except Exception: pass
            return False

        server_pub_key = crypto_utils.load_public_key_from_data(server_pub_key_bytes)
        if not server_pub_key:
            log.error("Falha ao carregar/validar chave pública recebida do servidor. Desconectando.")
            try:
                conn.close()
            except Exception: pass
            return False

        log.info("Chave pública do servidor recebida e carregada com sucesso.")
        client_state["server_public_key"] = server_pub_key
        client_state["server_connection"] = conn
        return True
    else:
        log.warning("Falha ao conectar ao servidor nesta tentativa.")
        client_state["server_connection"] = None
        client_state["server_public_key"] = None
        return False

def close_server_connection():
    """Fecha a conexão com o servidor."""
    conn = client_state.get("server_connection")
    if conn:
        log.info("Fechando conexão com o servidor...")
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        try:
            conn.close()
        except OSError as e:
            log.warning(f"Erro ao fechar conexão com servidor: {e}")
        finally:
            client_state["server_connection"] = None
            client_state["server_public_key"] = None



def listen_serial_and_send_thread():
    """Thread principal que lê da serial local e envia dados criptografados para o servidor."""
    log.info("Thread principal do cliente iniciada.")
    config = client_state["config"]
    serial_check_interval = 1.0
    connection_check_interval = config.get('retry_interval', 5.0)
    keep_alive_interval = 5.0
    last_activity_time = time.time()
    last_serial_check = 0
    last_connection_check = 0
    data_buffer = b""

    while not client_state["stop_event"].is_set():
        now = time.time()
        serial_ok = False
        connection_ok = False

        if now - last_serial_check > serial_check_interval:
            serial_ok = ensure_serial_open()
            last_serial_check = now
        else:
            serial_ok = client_state["serial_port"] and client_state["serial_port"].is_open

        if now - last_connection_check > connection_check_interval:
             connection_ok = ensure_server_connection()
             if connection_ok:
                 last_activity_time = now
             last_connection_check = now
        else:
             connection_ok = client_state["server_connection"] is not None

        if connection_ok and (now - last_activity_time > keep_alive_interval):
            log.debug(f"Sem atividade por >{keep_alive_interval}s. Enviando keep-alive ping...")
            ping_success = False
            try:
                ping_message = b'\x00\x00\x00\x00'
                if client_state["server_public_key"]:
                    encrypted_ping = crypto_utils.encrypt_message(client_state["server_public_key"], ping_message)
                    if encrypted_ping:
                        if network_utils.send_data(client_state["server_connection"], encrypted_ping):
                            log.debug("Keep-alive ping enviado com sucesso.")
                            last_activity_time = now
                            ping_success = True
                        else:
                            log.warning("Keep-alive ping send falhou (send_data retornou False). Conexão perdida.")
                    else:
                        log.error("Falha ao criptografar keep-alive ping.")
                else:
                    log.warning("Não é possível enviar keep-alive: chave pública do servidor não disponível.")

            except Exception as ping_err:
                log.error(f"Exceção ao enviar keep-alive ping: {ping_err}", exc_info=False)
                ping_success = False

            if not ping_success:
                log.warning("Keep-alive check falhou. Fechando conexão e acionando reconexão.")
                close_server_connection()
                connection_ok = False
                last_connection_check = 0

        if serial_ok and connection_ok:
            try:
                serial_data = serial_utils.read_from_serial(
                    client_state["serial_port"],
                    config.get('buffer_size', 1024)
                )

                if serial_data is None:
                    log.error("Erro grave lendo da porta serial. Fechando porta.")
                    serial_utils.close_serial_port(client_state["serial_port"])
                    client_state["serial_port"] = None
                    serial_ok = False
                    last_serial_check = 0
                    continue
                elif serial_data == b'':
                    pass
                else:
                    log.info(f"Lidos {len(serial_data)} bytes da porta serial {config['serial_port']}.")
                    data_buffer += serial_data

                if data_buffer and client_state["server_connection"] and client_state["server_public_key"]:
                    log.debug(f"Tentando enviar {len(data_buffer)} bytes do buffer para o servidor...")
                    max_chunk_size = 190
                    bytes_to_send = data_buffer
                    data_buffer = b""
                    send_loop_ok = True

                    try:
                        while bytes_to_send:
                            chunk = bytes_to_send[:max_chunk_size]
                            bytes_to_send = bytes_to_send[max_chunk_size:]

                            encrypted_chunk = crypto_utils.encrypt_message(
                                client_state["server_public_key"],
                                chunk
                            )

                            if encrypted_chunk:
                                if not network_utils.send_data(client_state["server_connection"], encrypted_chunk):
                                    log.warning("Falha ao enviar chunk para o servidor (erro de rede). Desconectando.")
                                    close_server_connection()
                                    connection_ok = False
                                    data_buffer = chunk + bytes_to_send
                                    last_connection_check = 0
                                    send_loop_ok = False
                                    break
                                else:
                                     log.debug("Chunk enviado com sucesso.")
                                     last_activity_time = now
                            else:
                                log.error("Falha ao criptografar chunk. Descartando dados restantes no buffer.")
                                data_buffer = b""
                                bytes_to_send = b""
                                send_loop_ok = False
                                break

                        if send_loop_ok and not data_buffer and not bytes_to_send:
                             log.info("Buffer completo enviado com sucesso para o servidor.")

                    except Exception as crypto_send_err:
                         log.error(f"Erro durante chunking/criptografia/envio: {crypto_send_err}", exc_info=True)
                         close_server_connection()
                         connection_ok = False
                         data_buffer = chunk + bytes_to_send if 'chunk' in locals() else bytes_to_send
                         last_connection_check = 0

            except serial_utils.serial.SerialException as ser_err:
                 log.error(f"Erro na porta serial: {ser_err}", exc_info=True)
                 serial_utils.close_serial_port(client_state["serial_port"])
                 client_state["serial_port"] = None
                 serial_ok = False
                 last_serial_check = 0
                 data_buffer = b""
            except Exception as e:
                 log.error(f"Erro inesperado no loop de leitura/envio: {e}", exc_info=True)
                 close_server_connection()
                 serial_utils.close_serial_port(client_state["serial_port"])
                 client_state["serial_port"] = None
                 serial_ok = False
                 connection_ok = False
                 last_serial_check = 0
                 last_connection_check = 0
                 data_buffer = b""
                 time.sleep(config.get('retry_interval', 5.0))

        time.sleep(0.05)

    log.info("Thread principal do cliente encerrando...")
    close_server_connection()
    serial_utils.close_serial_port(client_state.get("serial_port"))
    log.info("Thread principal do cliente finalizada.")



def run_client(start_config=None):
    """Função principal para configurar e iniciar o cliente."""
    if start_config:
        client_state["config"] = start_config
    config = client_state["config"]

    log_level_str = config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "client_activity.log")
    client_state["log_file_path"] = log_file
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
    log.info("Logs também estão sendo salvos em: client_activity.log")
    log.info("--- Iniciando Cliente Network Print Redirector v2.0.2 ---")

    priv_key = crypto_utils.load_private_key('client')
    pub_key = crypto_utils.load_public_key_from_file('client')
    if not priv_key or not pub_key:
        log.warning("Chaves RSA do cliente não encontradas ou inválidas. Gerando novo par...")
        key_size = config.get("rsa_key_size", 2048)
        priv_key, pub_key = crypto_utils.generate_keys('client', key_size=key_size)
        if not priv_key or not pub_key:
            log.critical("Falha ao gerar/carregar chaves RSA do cliente. Encerrando.")
            return False
    client_state["client_private_key"] = priv_key
    client_state["client_public_key"] = pub_key
    log.info("Chaves RSA do cliente carregadas/geradas.")

    client_state["server_public_key"] = None
    client_state["serial_port"] = None

    client_state["stop_event"].clear()
    main_thread = threading.Thread(target=listen_serial_and_send_thread, name="ClientMainThread")
    client_state["main_thread"] = main_thread

    log.info("Iniciando thread principal do cliente...")
    main_thread.start()

    return True

def stop_client():
    log.info("Solicitando encerramento do cliente...")
    client_state["stop_event"].set()
    main_thread = client_state.get("main_thread")
    if main_thread and main_thread.is_alive():
         log.info("Aguardando a thread principal do cliente finalizar...")
         main_thread.join(timeout=5.0)
         if main_thread.is_alive():
              log.warning("Thread principal do cliente não finalizou a tempo.")
    log.info("Cliente encerrado.")