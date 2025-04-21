import socket
import time
import select
import logging
import struct

log = logging.getLogger(__name__)


MSG_LEN_HEADER_FORMAT = '!I'
MSG_LEN_HEADER_SIZE = struct.calcsize(MSG_LEN_HEADER_FORMAT)

def start_server_socket(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        log.info(f"Servidor TCP iniciado e ouvindo em {host}:{port}")
        return server_socket
    except OSError as e:
        log.error(f"Erro de OS ao iniciar o servidor em {host}:{port}: {e}")
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao iniciar o servidor em {host}:{port}: {e}")
        return None

def connect_to_server(server_ip, server_port, retry_interval=5.0, max_retries=3):
    attempts = 0
    max_retries = max_retries if max_retries is not None and max_retries > 0 else float('inf')

    while attempts < max_retries:
        try:
            log.info(f"Tentando conectar ao servidor {server_ip}:{server_port} (tentativa {attempts + 1})...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(retry_interval)
            client_socket.connect((server_ip, server_port))
            client_socket.settimeout(None)
            log.info(f"Conectado com sucesso ao servidor {server_ip}:{server_port}")
            return client_socket
        except socket.timeout:
            log.warning(f"Timeout ao tentar conectar ao servidor {server_ip}:{server_port}.")
            attempts += 1
        except socket.error as e:
            log.warning(f"Falha ao conectar ao servidor {server_ip}:{server_port}: {e}")
            attempts += 1
        except Exception as e:
            log.error(f"Erro inesperado ao conectar ao servidor: {e}")
            attempts += 1

        if attempts < max_retries:
            log.info(f"Próxima tentativa de conexão em {retry_interval} segundos...")
            time.sleep(retry_interval)

    log.error("Máximo de tentativas de conexão atingido. Desistindo.")
    return None


def send_data(sock, data_bytes):
    if not data_bytes:
        log.warning("Tentativa de enviar dados vazios.")
        return True

    try:
        message_len_header = struct.pack(MSG_LEN_HEADER_FORMAT, len(data_bytes))
        sock.sendall(message_len_header + data_bytes)
        log.debug(f"Enviados {len(message_len_header)} bytes de cabeçalho e {len(data_bytes)} bytes de dados.")
        return True
    except socket.error as e:
        log.error(f"Erro de socket ao enviar dados: {e}")
        return False
    except Exception as e:
        log.error(f"Erro inesperado ao enviar dados: {e}")
        return False

def receive_data(sock, timeout=1.0):
    sock.setblocking(0)
    ready_to_read, _, _ = select.select([sock], [], [], timeout)

    if not ready_to_read:
        return b''

    header_data = b''
    bytes_to_read = MSG_LEN_HEADER_SIZE
    try:
        while len(header_data) < bytes_to_read:
            chunk = sock.recv(bytes_to_read - len(header_data))
            if not chunk:
                log.warning("Conexão fechada pelo outro lado enquanto lia o cabeçalho.")
                return None
            header_data += chunk
        message_len = struct.unpack(MSG_LEN_HEADER_FORMAT, header_data)[0]
        log.debug(f"Cabeçalho recebido indica mensagem de {message_len} bytes.")

        message_data = b''
        bytes_to_read = message_len
        while len(message_data) < bytes_to_read:
            chunk_size = min(bytes_to_read - len(message_data), 4096)
            chunk = sock.recv(chunk_size)
            if not chunk:
                log.warning("Conexão fechada pelo outro lado enquanto lia o corpo da mensagem.")
                return None
            message_data += chunk

        log.debug(f"Recebidos {len(message_data)} bytes de dados.")
        return message_data

    except socket.error as e:
        log.error(f"Erro de socket ao receber dados: {e}")
        return None
    except struct.error as e:
         log.error(f"Erro ao desempacotar cabeçalho de tamanho: {e}")
         return None
    except Exception as e:
        log.error(f"Erro inesperado ao receber dados: {e}")
        return None
    finally:
         pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_host = "127.0.0.1"
    test_port = 19999

    def server_thread_func():
        log.info("[Server Thread] Iniciando...")
        server_sock = start_server_socket(test_host, test_port)
        if not server_sock: return
        try:
            log.info("[Server Thread] Aguardando conexão...")
            client, addr = server_sock.accept()
            log.info(f"[Server Thread] Conexão aceita de {addr}")
            with client:
                data_received = receive_data(client, timeout=5.0)
                if data_received is None:
                    log.info("[Server Thread] Cliente desconectou ou erro ao receber.")
                elif data_received == b'':
                    log.info("[Server Thread] Timeout ao receber dados.")
                else:
                    log.info(f"[Server Thread] Recebido: {data_received.decode()}")
                    log.info("[Server Thread] Enviando eco...")
                    if not send_data(client, b"Eco: " + data_received):
                         log.error("[Server Thread] Falha ao enviar eco.")
        except Exception as e:
            log.error(f"[Server Thread] Erro: {e}")
        finally:
            log.info("[Server Thread] Fechando socket do servidor.")
            server_sock.close()
            log.info("[Server Thread] Encerrado.")

    import threading
    st = threading.Thread(target=server_thread_func, daemon=True)
    st.start()

    time.sleep(1)

    log.info("[Main] Conectando ao servidor de teste...")
    client_sock = connect_to_server(test_host, test_port, retry_interval=1.0, max_retries=3)

    if client_sock:
        log.info("[Main] Conectado. Enviando mensagem de teste...")
        with client_sock:
            message_to_send = b"Ola Servidor!"
            if send_data(client_sock, message_to_send):
                log.info("[Main] Mensagem enviada. Aguardando eco...")
                eco_received = receive_data(client_sock, timeout=5.0)
                if eco_received is None:
                    log.info("[Main] Servidor desconectou ou erro ao receber eco.")
                elif eco_received == b'':
                    log.info("[Main] Timeout ao receber eco.")
                else:
                    log.info(f"[Main] Eco recebido: {eco_received.decode()}")
            else:
                log.error("[Main] Falha ao enviar mensagem.")
    else:
        log.error("[Main] Não foi possível conectar ao servidor de teste.")

    log.info("[Main] Aguardando thread do servidor terminar...")
    st.join(timeout=2.0)
    log.info("[Main] Teste concluído.")
