import serial
import time
import datetime

BAUD_RATE = 9600

virtual_com_port_input = input("Digite a porta COM virtual para ouvir (ex: COM11): ")
VIRTUAL_COM_PORT = virtual_com_port_input.strip().upper()

print(f"[*] Tentando ouvir na porta {VIRTUAL_COM_PORT} a {BAUD_RATE} baud...")

try:
    ser = serial.Serial(
        port=VIRTUAL_COM_PORT,
        baudrate=BAUD_RATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )
    print(f"[*] Ouvindo em {ser.name}. Aguardando dados...")
    print("-" * 30)

    received_data = b""
    while True:
        try:
            bytes_waiting = ser.in_waiting
            if bytes_waiting > 0:
                data = ser.read(bytes_waiting)
                received_data += data
                try:
                    print(data.decode('utf-8', errors='ignore'), end='', flush=True)
                except Exception:
                    print(f"[Raw Bytes: {data}]", end='', flush=True)

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[*] Interrupção pelo usuário.")
            break
        except serial.SerialException as e:
            print(f"\n[!] Erro na porta serial: {e}")
            break
        except Exception as e:
            print(f"\n[!] Erro inesperado: {e}")
            break

    ser.close()
    print("-" * 30)
    print("[*] Porta fechada.")

    if received_data:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"received_zpl_{timestamp}.zpl"
        try:
            with open(filename, "wb") as f:
                f.write(received_data)
            print(f"[*] Dados brutos salvos em: {filename}")
        except Exception as e:
            print(f"[!] Erro ao salvar arquivo: {e}")
    else:
        print("[*] Nenhum dado recebido para salvar.")


except serial.SerialException as e:
    print(f"[!] Falha ao abrir a porta {VIRTUAL_COM_PORT}: {e}")
    print("[!] Verifique se a porta existe, não está em uso e se o software de COM virtual está rodando.")
except Exception as e:
    print(f"[!] Erro inesperado ao iniciar: {e}")

input("Pressione Enter para sair.")