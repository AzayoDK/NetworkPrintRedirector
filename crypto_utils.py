import logging
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature, AlreadyFinalized

log = logging.getLogger(__name__)

PRIVATE_KEY_FILE_TPL = "{mode}_private_key.pem"
PUBLIC_KEY_FILE_TPL = "{mode}_public_key.pem"

def get_private_key_path(mode):
    """Retorna o caminho esperado para o arquivo de chave privada."""
    return PRIVATE_KEY_FILE_TPL.format(mode=mode)

def get_public_key_path(mode):
    """Retorna o caminho esperado para o arquivo de chave pública."""
    return PUBLIC_KEY_FILE_TPL.format(mode=mode)

def generate_keys(mode, key_size=2048, private_key_password=None):
    """
    Gera um par de chaves RSA (privada e pública) e salva em arquivos PEM.

    Args:
        mode (str): 'client' or 'server', usado para nomear os arquivos.
        key_size (int): Tamanho da chave em bits (e.g., 2048, 4096).
        private_key_password (bytes, optional): Senha para proteger a chave privada. Defaults to None.

    Returns:
        tuple: (private_key, public_key) objetos cryptography, ou (None, None) em caso de erro.
    """
    private_path = get_private_key_path(mode)
    public_path = get_public_key_path(mode)

    log.info(f"Gerando novo par de chaves RSA ({key_size} bits) para {mode}...")
    try:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        public_key = private_key.public_key()

        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(private_key_password) if private_key_password else serialization.NoEncryption()
        )
        with open(private_path, 'wb') as f_priv:
            f_priv.write(pem_private)
        log.info(f"Chave privada salva em: {private_path}")

        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(public_path, 'wb') as f_pub:
            f_pub.write(pem_public)
        log.info(f"Chave pública salva em: {public_path}")

        return private_key, public_key

    except IOError as e:
        log.error(f"Erro de I/O ao salvar chaves para {mode}: {e}")
    except Exception as e:
        log.error(f"Erro inesperado ao gerar/salvar chaves para {mode}: {e}")

    return None, None

def load_private_key(mode, password=None):
    """Carrega a chave privada RSA de um arquivo PEM."""
    private_path = get_private_key_path(mode)
    if not os.path.exists(private_path):
        log.error(f"Arquivo de chave privada não encontrado: {private_path}")
        return None

    log.info(f"Carregando chave privada de: {private_path}")
    try:
        with open(private_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=password,
            )
        log.info(f"Chave privada para {mode} carregada com sucesso.")
        return private_key
    except (ValueError, TypeError) as e:
         log.error(f"Erro ao carregar chave privada (senha incorreta ou formato inválido?): {e}")
    except IOError as e:
        log.error(f"Erro de I/O ao carregar chave privada de {private_path}: {e}")
    except Exception as e:
        log.error(f"Erro inesperado ao carregar chave privada de {private_path}: {e}")

    return None

def load_public_key_from_file(mode):
    """Carrega a chave pública RSA de um arquivo PEM."""
    public_path = get_public_key_path(mode)
    if not os.path.exists(public_path):
        log.warning(f"Arquivo de chave pública não encontrado: {public_path}")
        return None

    log.info(f"Carregando chave pública de: {public_path}")
    try:
        with open(public_path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read(),
            )
        log.info(f"Chave pública para {mode} carregada com sucesso do arquivo.")
        return public_key
    except (ValueError, TypeError) as e:
         log.error(f"Erro ao carregar chave pública (formato inválido?): {e}")
    except IOError as e:
        log.error(f"Erro de I/O ao carregar chave pública de {public_path}: {e}")
    except Exception as e:
        log.error(f"Erro inesperado ao carregar chave pública de {public_path}: {e}")

    return None

def load_public_key_from_data(key_data_bytes):
    """Carrega a chave pública RSA a partir de dados binários (PEM)."""
    if not key_data_bytes:
        log.error("Tentativa de carregar chave pública a partir de dados vazios.")
        return None
    log.debug(f"Tentando carregar chave pública a partir de {len(key_data_bytes)} bytes de dados.")
    try:
        public_key = serialization.load_pem_public_key(key_data_bytes)
        log.info("Chave pública carregada com sucesso a partir dos dados.")
        return public_key
    except (ValueError, TypeError) as e:
         log.error(f"Erro ao carregar chave pública dos dados (formato inválido?): {e}")
    except Exception as e:
        log.error(f"Erro inesperado ao carregar chave pública dos dados: {e}")
    return None

def get_public_key_bytes(public_key):
    """Serializa a chave pública para bytes no formato PEM."""
    if not public_key:
        log.error("Tentativa de serializar uma chave pública inválida.")
        return None
    try:
        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_public
    except Exception as e:
        log.error(f"Erro ao serializar chave pública para bytes: {e}")
        return None

def encrypt_message(public_key, message_bytes):
    """
    Criptografa uma mensagem (bytes) usando a chave pública RSA.

    Args:
        public_key: Objeto de chave pública cryptography.
        message_bytes (bytes): A mensagem a ser criptografada.

    Returns:
        bytes: Mensagem criptografada, ou None em caso de erro.
    """
    if not public_key or not message_bytes:
        log.error("Chave pública ou mensagem inválida para criptografia.")
        return None

    try:
        padding_algo = padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
        encrypted_message = public_key.encrypt(
            message_bytes,
            padding_algo
        )
        log.debug(f"Mensagem de {len(message_bytes)} bytes criptografada para {len(encrypted_message)} bytes.")
        return encrypted_message
    except ValueError as e:
        log.error(f"Erro ao criptografar: Mensagem muito longa para a chave/padding? {e}")
    except Exception as e:
        log.error(f"Erro inesperado durante a criptografia: {e}")

    return None

def decrypt_message(private_key, encrypted_message_bytes):
    """
    Descriptografa uma mensagem (bytes) usando a chave privada RSA.

    Args:
        private_key: Objeto de chave privada cryptography.
        encrypted_message_bytes (bytes): A mensagem criptografada.

    Returns:
        bytes: Mensagem original descriptografada, ou None em caso de erro.
    """
    if not private_key or not encrypted_message_bytes:
        log.error("Chave privada ou mensagem criptografada inválida para descriptografia.")
        return None

    try:
        padding_algo = padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
        decrypted_message = private_key.decrypt(
            encrypted_message_bytes,
            padding_algo
        )
        log.debug(f"Mensagem criptografada de {len(encrypted_message_bytes)} bytes descriptografada para {len(decrypted_message)} bytes.")
        return decrypted_message
    except ValueError as e:
        log.error(f"Erro ao descriptografar: Dados corrompidos, padding/chave incorreta? {e}")
    except Exception as e:
        log.error(f"Erro inesperado durante a descriptografia: {e}")

    return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("Testando funcionalidades de criptografia...")

    priv_s, pub_s = generate_keys('server', key_size=1024)
    priv_c, pub_c = generate_keys('client', key_size=1024)

    if priv_s and priv_c:
        print("\nChaves geradas/salvas.")

        priv_s_loaded = load_private_key('server')
        pub_s_loaded = load_public_key_from_file('server')
        priv_c_loaded = load_private_key('client')
        pub_c_loaded = load_public_key_from_file('client')

        if priv_s_loaded and pub_s_loaded and priv_c_loaded and pub_c_loaded:
            print("Chaves carregadas com sucesso.")

            pub_s_bytes = get_public_key_bytes(pub_s_loaded)
            pub_c_bytes = get_public_key_bytes(pub_c_loaded)
            print(f"\nChave pública Server (bytes): {len(pub_s_bytes)} bytes")
            print(f"Chave pública Client (bytes): {len(pub_c_bytes)} bytes")

            pub_s_from_data = load_public_key_from_data(pub_s_bytes)
            pub_c_from_data = load_public_key_from_data(pub_c_bytes)
            if pub_s_from_data and pub_c_from_data:
                print("Chaves públicas carregadas de bytes com sucesso.")

                message = b"Esta e uma mensagem secreta!"
                print(f"\nMensagem Original: {message}")

                encrypted_by_client = encrypt_message(pub_s_from_data, message)
                if encrypted_by_client:
                    print(f"Criptografado pelo Cliente (com pub Servidor): {len(encrypted_by_client)} bytes")

                    decrypted_by_server = decrypt_message(priv_s_loaded, encrypted_by_client)
                    if decrypted_by_server:
                        print(f"Descriptografado pelo Servidor (com priv Servidor): {decrypted_by_server}")
                        assert message == decrypted_by_server
                        print(">> Teste Cliente -> Servidor OK")
                    else:
                        print(">> Falha ao descriptografar pelo Servidor")
                else:
                    print(">> Falha ao criptografar pelo Cliente")
            else:
                 print(">> Falha ao carregar chaves públicas de bytes")
        else:
            print(">> Falha ao carregar chaves dos arquivos.")
    else:
        print(">> Falha ao gerar/salvar chaves.")
