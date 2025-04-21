import serial
import time
import logging

log = logging.getLogger(__name__)

def open_serial_port(port, baudrate, timeout=1.0, **kwargs):
    """
    Abre e retorna um objeto de porta serial.

    Args:
        port (str): Nome da porta serial (e.g., 'COM3' no Windows, '/dev/ttyS0' no Linux).
        baudrate (int): Velocidade da comunicação (e.g., 9600, 115200).
        timeout (float): Timeout de leitura em segundos (0=não bloqueante, None=bloqueante).
        **kwargs: Outros argumentos para serial.Serial (bytesize, parity, stopbits).

    Returns:
        serial.Serial: Objeto da porta serial aberta, ou None em caso de erro.
    """
    log.info(f"Tentando abrir porta serial {port} a {baudrate} baud, timeout={timeout}s")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            bytesize=kwargs.get('bytesize', serial.EIGHTBITS),
            parity=kwargs.get('parity', serial.PARITY_NONE),
            stopbits=kwargs.get('stopbits', serial.STOPBITS_ONE)
        )

        log.info(f"Porta serial {port} aberta com sucesso.")


        return ser
    except serial.SerialException as e:
        log.error(f"Erro ao abrir/configurar porta serial {port}: {e}")
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao tentar abrir porta serial {port}: {e}")
        return None

def read_from_serial(ser, buffer_size=1024):
    """
    Lê dados da porta serial.

    Args:
        ser (serial.Serial): Objeto da porta serial aberta.
        buffer_size (int): Tamanho máximo de bytes a ler de uma vez.

    Returns:
        bytes: Dados lidos. Retorna b'' se nada foi lido (timeout ou sem dados).
               Retorna None em caso de erro grave na porta.
    """
    if not ser or not ser.is_open:
        log.error("Tentativa de leitura em porta serial inválida ou fechada.")
        return None
    try:

        bytes_waiting = ser.in_waiting
        if bytes_waiting > 0:

            read_size = min(bytes_waiting, buffer_size)
            data = ser.read(read_size)
            log.debug(f"Lidos {len(data)} bytes da porta serial {ser.port}")
            return data
        else:



            return b''
    except serial.SerialException as e:

        log.error(f"Erro de SerialException ao ler da porta {ser.port}: {e}")
        return None
    except OSError as e:

         log.error(f"Erro de OSError ao ler da porta {ser.port}: {e}")
         return None
    except Exception as e:
        log.error(f"Erro inesperado ao ler da serial {ser.port}: {e}")
        return None

def write_to_serial(ser, data_bytes):
    """
    Escreve dados (bytes) na porta serial.

    Args:
        ser (serial.Serial): Objeto da porta serial aberta.
        data_bytes (bytes): Dados a serem escritos.

    Returns:
        bool: True se a escrita foi (aparentemente) bem-sucedida, False caso contrário.
    """
    if not ser or not ser.is_open:
        log.error("Tentativa de escrita em porta serial inválida ou fechada.")
        return False
    if not data_bytes:
        log.warning("Tentativa de escrever dados vazios na porta serial.")
        return True

    try:
        bytes_written = ser.write(data_bytes)


        log.debug(f"{bytes_written}/{len(data_bytes)} bytes escritos na porta serial {ser.port}.")
        if bytes_written != len(data_bytes):
             log.warning(f"Escrita incompleta na porta serial {ser.port}: {bytes_written}/{len(data_bytes)} bytes.")




             return False
        return True
    except serial.SerialTimeoutException:

        log.warning(f"Timeout ao escrever na porta serial {ser.port}.")
        return False
    except serial.SerialException as e:
        log.error(f"Erro de SerialException ao escrever na porta {ser.port}: {e}")
        return False
    except OSError as e:
         log.error(f"Erro de OSError ao escrever na porta {ser.port}: {e}")
         return False
    except Exception as e:
        log.error(f"Erro inesperado ao escrever na serial {ser.port}: {e}")
        return False

def close_serial_port(ser):
    """Fecha a porta serial se estiver aberta."""
    if ser and ser.is_open:
        port_name = ser.port
        log.info(f"Fechando porta serial {port_name}...")
        try:
            ser.close()
            log.info(f"Porta serial {port_name} fechada.")
        except serial.SerialException as e:
            log.error(f"Erro ao fechar a porta serial {port_name}: {e}")
        except Exception as e:
            log.error(f"Erro inesperado ao fechar a porta serial {port_name}: {e}")
    elif ser:
         log.debug(f"Porta serial {ser.port} já estava fechada.")
    else:
         log.debug("Nenhum objeto de porta serial para fechar.")



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')




    port1_name = "COM8"
    port2_name = "COM9"
    test_baudrate = 9600
    test_message = b"Teste Serial 123\n"

    print(f"\n--- Teste de Comunicação Serial ---")
    print(f"Usando: {port1_name} <-> {port2_name} @ {test_baudrate} baud")
    print("Certifique-se que as portas estão conectadas (cabo null-modem ou virtual).")


    ser1 = open_serial_port(port1_name, test_baudrate, timeout=0.5, write_timeout=1.0)
    ser2 = open_serial_port(port2_name, test_baudrate, timeout=1.0)

    if ser1 and ser2:
        print("\nAmbas as portas abertas com sucesso.")


        ser1.reset_input_buffer()
        ser1.reset_output_buffer()
        ser2.reset_input_buffer()
        ser2.reset_output_buffer()
        time.sleep(0.1)


        print(f"\nEnviando de {port1_name} para {port2_name}: {test_message}")
        success_write = write_to_serial(ser1, test_message)

        if success_write:
            print("Escrita bem-sucedida (aparentemente). Aguardando leitura...")
            time.sleep(0.5)


            read_data = read_from_serial(ser2, buffer_size=100)

            if read_data is None:
                print(f"Erro ao ler de {port2_name}.")
            elif read_data == b'':
                print(f"Timeout ou nenhum dado lido de {port2_name}.")
            else:
                print(f"Lido de {port2_name}: {read_data}")

                if read_data == test_message:
                    print(">> Verificação: Dados recebidos CORRETOS.")
                else:
                    print(">> Verificação: Dados recebidos DIFERENTES do esperado!")
        else:
            print(f"Falha ao escrever em {port1_name}.")

    else:
        print("\nFalha ao abrir uma ou ambas as portas. Verifique os nomes e permissões.")


    print("\nFechando portas...")
    close_serial_port(ser1)
    close_serial_port(ser2)

    print("\nTeste serial concluído.")