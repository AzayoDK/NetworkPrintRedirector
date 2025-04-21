# NetworkPrintRedirector v1.0

Redireciona dados de uma porta serial local (Estação do Usuário - Cliente) para uma porta serial remota (Estação de Impressão - Servidor) através de uma conexão de rede TCP, com criptografia básica. Útil para compartilhar dispositivos seriais (como impressoras de cupom, leitores, etc.) em uma rede local onde a comunicação serial direta não é possível ou desejada.

**Importante:** Este sistema depende da emulação de pares de portas seriais virtuais em ambas as máquinas (Cliente e Servidor).

## Pré-requisitos Essenciais de Configuração (com0com)

Antes de usar o NetworkPrintRedirector, é **obrigatório** configurar um par de portas seriais virtuais conectadas em **ambas** as máquinas (Cliente e Servidor) usando uma ferramenta como o [com0com](http://com0com.sourceforge.net/).

**Fluxo de Dados Esperado:**

1.  **Na Estação do Usuário (Cliente):**
    *   Configure o `com0com` para criar um par de portas virtuais, por exemplo, `COM2 <=> COM3`.
    *   A aplicação do usuário (que normalmente imprimiria direto na porta serial física) deve ser configurada para enviar dados para a porta virtual `COM2`.
    *   O `NetworkPrintRedirector` no modo **Cliente** deve ser configurado para escutar a outra porta virtual do par, `COM3`. Ele lerá os dados que chegam em `COM3` (vindos de `COM2` através do `com0com`) e os enviará pela rede para o Servidor.

2.  **Na Estação de Impressão (Servidor):**
    *   Configure o `com0com` para criar um par de portas virtuais similar, por exemplo, `COM2 <=> COM3`.
    *   O `NetworkPrintRedirector` no modo **Servidor** receberá os dados da rede (vindos do Cliente) e os escreverá na porta virtual `COM2`.
    *   A impressora física (ou um software emulador como o **Zebra Emulator Com**) deve ser configurada para escutar a outra porta virtual do par, `COM3`. Ela receberá os dados que chegam em `COM3` (vindos de `COM2` através do `com0com`).

**Resumo do Fluxo:**
Aplicação do Usuário -> `COM2` (Cliente via com0com) -> `COM3` (Cliente via com0com) -> `NetworkPrintRedirector Cliente` (lendo COM3) -> Rede TCP -> `NetworkPrintRedirector Servidor` (escrevendo COM2) -> `COM2` (Servidor via com0com) -> `COM3` (Servidor via com0com) -> Impressora/Emulador (lendo COM3).

**Sem a configuração correta do `com0com` em ambas as máquinas, criando esses pares de portas virtuais conectadas, o redirecionamento não funcionará.**

## Funcionalidades

*   **Modo Cliente (Estação do Usuário):** Lê dados de uma porta serial local (ex: `COM3` configurada com `com0com`) e os envia para o servidor via TCP.
*   **Modo Servidor (Estação de Impressão):** Recebe dados de clientes via TCP e os escreve em uma porta serial local (ex: `COM2` configurada com `com0com`).
*   **Configuração Flexível:** Parâmetros (IPs, portas, serial, etc.) definidos em arquivos `client_config_v2.json` e `server_config_v2.json`.
*   **Execução em Segundo Plano (Windows):** Opção para rodar minimizado na bandeja do sistema com um ícone e menu básico (requer configuração).
*   **Logging:** Registra atividades e erros em arquivos (`client_activity.log` / `server_activity.log`) com nível de detalhe configurável.
*   **Criptografia:** Usa chaves RSA para criptografar a comunicação entre cliente e servidor (Nota: A implementação exata da troca de chaves e protocolo pode precisar de revisão para segurança robusta).
*   **Dois Executáveis (Windows):**
    *   `NetworkPrintRedirector_Console.exe`: Versão com console, usada para configuração inicial/reconfiguração e execução interativa.
    *   `NetworkPrintRedirector.exe`: Versão sem console (`--windowed`), ideal para execução silenciosa em segundo plano (requer configuração prévia via versão Console).

## Requisitos

*   Python 3.7+
*   **com0com** (ou similar) instalado e configurado em ambas as máquinas (Cliente e Servidor), conforme descrito na seção "Pré-requisitos Essenciais".
*   Bibliotecas Python (instale com `pip install -r requirements.txt` se for rodar do código fonte):
    *   `pyserial`
    *   `cryptography`
    *   `pystray` (para modo bandeja)
    *   `Pillow` (para modo bandeja)

## Instalação (para desenvolvimento)

1.  Clone o repositório:
    ```bash
    git clone [URL do seu repositório Git]
    cd [nome-da-pasta-do-projeto]
    ```
2.  (Opcional) Crie e ative um ambiente virtual:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```
3.  Crie um arquivo `requirements.txt` com o seguinte conteúdo:
    ```text name=requirements.txt
    pyserial
    cryptography
    pystray
    Pillow
    ```
4.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

## Configuração Inicial (Obrigatória)

A configuração é **essencial** e deve ser feita **antes** de tentar rodar o programa em modo de segundo plano (`NetworkPrintRedirector.exe`). **Lembre-se que a configuração do `com0com` (descrita acima) também é necessária.**

1.  **Use a versão Console para Configurar:** Execute `NetworkPrintRedirector_Console.exe` (ou `python main.py` se estiver rodando do código fonte) com o modo desejado (`client` ou `server`) e a flag `--reconfigure`. Isso iniciará a configuração interativa no terminal:
    ```bash
    # Exemplo para configurar o cliente pela primeira vez ou reconfigurar
    .\NetworkPrintRedirector_Console.exe client --reconfigure

    # Exemplo para configurar o servidor pela primeira vez ou reconfigurar
    .\NetworkPrintRedirector_Console.exe server --reconfigure
    ```
2.  **Responda às perguntas de configuração:** O programa solicitará as informações necessárias dependendo do modo (`client` ou `server`).

    **Configuração do Cliente (`client --reconfigure`):**
    *   `Endereço IP do Servidor:` Digite o endereço IP da máquina onde o `NetworkPrintRedirector` está rodando em modo Servidor.
    *   `Porta do Servidor:` Digite a porta TCP que o Servidor está escutando (deve ser a mesma configurada no Servidor).
    *   `Porta Serial para Leitura:` Digite o nome da porta serial local da qual o Cliente lerá os dados (ex: `COM3`, conforme o exemplo do `com0com`).
    *   `Baud Rate:` Velocidade da comunicação serial (ex: `9600`, `19200`, `115200`). Deve corresponder à configuração da porta `COM2` (do par `com0com`) que a aplicação do usuário está usando.
    *   `Byte Size (5-8):` Número de bits de dados (geralmente `8`).
    *   `Parity (None, Even, Odd, Mark, Space):` Tipo de paridade (geralmente `None`). Digite `N` para None, `E` para Even, `O` para Odd, `M` para Mark, `S` para Space.
    *   `Stop Bits (1, 1.5, 2):` Número de stop bits (geralmente `1`).
    *   `Nível de Log (DEBUG, INFO, WARNING, ERROR, CRITICAL):` Define o quão detalhado será o log (`client_activity.log`).
        *   `DEBUG`: Máximo detalhe, bom para diagnóstico.
        *   `INFO`: Informações gerais (conexões, etc.). Recomendado.
        *   `WARNING`: Apenas avisos e erros.
        *   `ERROR`: Apenas erros.
        *   `CRITICAL`: Apenas erros muito graves.
    *   `Iniciar minimizado na bandeja do sistema? (true/false):` Responda `true` (ou `sim`, `s`, `1`) se desejar que o `NetworkPrintRedirector.exe` (versão sem console) inicie diretamente na bandeja do sistema. `false` (ou `nao`, `n`, `0`) fará com que ele não use a bandeja (útil apenas para a versão Console).

    **Configuração do Servidor (`server --reconfigure`):**
    *   `Endereço IP para Escutar (0.0.0.0 para todos):` O endereço IP local no qual o servidor deve aceitar conexões. `0.0.0.0` é o recomendado, pois permite conexões de qualquer interface de rede da máquina.
    *   `Porta para Escutar:` A porta TCP na qual o servidor aguardará conexões dos Clientes (ex: `9100`).
    *   `Porta Serial para Escrita:` Digite o nome da porta serial local na qual o Servidor escreverá os dados recebidos (ex: `COM2`, conforme o exemplo do `com0com`).
    *   `Baud Rate:` Velocidade da comunicação serial (ex: `9600`). Deve corresponder à configuração da porta `COM3` (do par `com0com`) que a impressora/emulador está escutando.
    *   `Byte Size (5-8):` Número de bits de dados (geralmente `8`).
    *   `Parity (None, Even, Odd, Mark, Space):` Tipo de paridade (geralmente `None`). Digite `N` para None, `E` para Even, `O` para Odd, `M` para Mark, `S` para Space.
    *   `Stop Bits (1, 1.5, 2):` Número de stop bits (geralmente `1`).
    *   `Nível de Log (DEBUG, INFO, WARNING, ERROR, CRITICAL):` Define o quão detalhado será o log (`server_activity.log`). (Veja a descrição na configuração do Cliente).
    *   `Iniciar minimizado na bandeja do sistema? (true/false):` Responda `true` (ou `sim`, `s`, `1`) se desejar que o `NetworkPrintRedirector.exe` (versão sem console) inicie diretamente na bandeja do sistema. `false` (ou `nao`, `n`, `0`) fará com que ele não use a bandeja.

3.  **Arquivos Gerados:** A configuração será salva em `client_config_v2.json` ou `server_config_v2.json` no mesmo diretório do executável.

**Importante:** Tentar executar `NetworkPrintRedirector.exe` (a versão sem console) sem um arquivo de configuração válido (`.json`) no mesmo diretório resultará em erro, pois ele não pode solicitar a configuração interativa.

## Instalação e Execução (Usando os Executáveis)

1.  **Copie os Executáveis:**
    *   Crie uma pasta para o programa, por exemplo, em `C:\Program Files (x86)\NetworkPrintRedirector` (pode ser necessário permissão de administrador) ou em outro local de sua preferência.
    *   Copie os arquivos `NetworkPrintRedirector_Console.exe` e `NetworkPrintRedirector.exe` para esta pasta.
    *   **Importante:** Os arquivos de configuração (`client_config_v2.json` ou `server_config_v2.json`) e os arquivos de log (`.log`) serão criados/lidos nesta mesma pasta onde os executáveis estão.

2.  **Crie Atalhos:**
    *   Na pasta onde copiou os executáveis, clique com o botão direito em `NetworkPrintRedirector_Console.exe` e selecione "Enviar para" -> "Área de Trabalho (criar atalho)". Renomeie o atalho se desejar (ex: "NPR Configurar Cliente", "NPR Configurar Servidor").
    *   Faça o mesmo para `NetworkPrintRedirector.exe`. Renomeie o atalho (ex: "NPR Cliente", "NPR Servidor"). Você pode precisar de dois atalhos para este, um para o cliente e um para o servidor, se for usar ambos na mesma máquina (embora não seja o caso de uso típico).

3.  **Configure os Atalhos (Modo de Operação):**
    *   Clique com o botão direito no atalho desejado e vá em "Propriedades".
    *   Na aba "Atalho", localize o campo "Destino".
    *   **Após** o caminho completo do executável (que estará entre aspas), adicione um espaço e o modo de operação (`client` ou `server`) e/ou a flag (`--reconfigure`) desejada.
    *   **Exemplos:**
        *   **Atalho para Configurar/Reconfigurar o Cliente:**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector_Console.exe" client --reconfigure`
        *   **Atalho para Configurar/Reconfigurar o Servidor:**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector_Console.exe" server --reconfigure`
        *   **Atalho para Rodar o Cliente em modo Bandeja (após configurar):**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector.exe" client`
        *   **Atalho para Rodar o Servidor em modo Bandeja (após configurar):**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector.exe" server`
        *   **Atalho para Rodar o Cliente no Console (ver logs em tempo real):**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector_Console.exe" client`
        *   **Atalho para Rodar o Servidor no Console (ver logs em tempo real):**
            `"C:\Program Files (x86)\NetworkPrintRedirector\NetworkPrintRedirector_Console.exe" server`
    *   Verifique também se o campo "Iniciar em" está apontando para a pasta onde os executáveis estão (ex: `"C:\Program Files (x86)\NetworkPrintRedirector"`). Isso garante que ele encontre os arquivos `.json` e `.log`.
    *   Clique em "Aplicar" e "OK".

4.  **Execução:**
    *   **Primeiro:** Use um atalho do `NetworkPrintRedirector_Console.exe` configurado com `--reconfigure` (ex: "NPR Configurar Cliente") para fazer a configuração inicial na máquina Cliente e outro (ex: "NPR Configurar Servidor") na máquina Servidor.
    *   **Depois:** Use os atalhos do `NetworkPrintRedirector.exe` (ex: "NPR Cliente", "NPR Servidor") para iniciar o programa silenciosamente em modo de bandeja. Ou use os atalhos do `_Console` sem `--reconfigure` para rodar com o terminal visível.

5.  **(Opcional) Inicialização Automática com Windows:**
    *   Para que o programa (Cliente ou Servidor) inicie automaticamente em modo bandeja quando o usuário fizer login:
        *   Pressione `Win + R` para abrir a caixa "Executar".
        *   Digite `shell:startup` e pressione Enter. Isso abrirá a pasta de Inicialização do usuário atual.
        *   Copie o atalho do `NetworkPrintRedirector.exe` (já configurado com `client` ou `server` no passo 3, **sem** `--reconfigure`) para dentro desta pasta de Inicialização.

## Uso (Menu da Bandeja)

Quando rodando em modo bandeja (`NetworkPrintRedirector.exe` ou `NetworkPrintRedirector_Console.exe` com `run_in_background: true` na config):

*   Um ícone aparecerá na bandeja do sistema (próximo ao relógio).
*   Clique com o botão direito no ícone para acessar o menu:
    *   **Abrir Log:** Tenta abrir o arquivo de log (`client_activity.log` ou `server_activity.log`) no editor de texto padrão.
    *   **Menu Admin (apenas Servidor):**
        *   *Listar Clientes (Ver Log):* Registra a lista de clientes conectados atualmente no arquivo de log e tenta abri-lo.
        *   *Reconfigurar (Use Console):* Exibe uma mensagem lembrando que a reconfiguração deve ser feita usando o atalho do `NetworkPrintRedirector_Console.exe` com a flag `--reconfigure`.
        *   *Mostrar Logs Recentes (Abrir Log):* Tenta abrir o arquivo de log do servidor.
    *   **Sair:** Encerra o programa corretamente.

## Construindo os Executáveis (Usando PyInstaller)

Se você modificou o código fonte e precisa recriar os executáveis:

1.  Certifique-se de ter o PyInstaller instalado no seu ambiente Python (`pip install pyinstaller`).
2.  Coloque um arquivo de ícone chamado `icon.ico` no diretório raiz do projeto (onde está `main.py`). Este será usado para o ícone da bandeja *e* para o ícone do arquivo `.exe`.
3.  Abra um terminal (como CMD ou PowerShell) no diretório raiz do projeto.
4.  Execute os seguintes comandos:

    *   **Para criar `NetworkPrintRedirector_Console.exe` (com terminal):**
        ```bash
        pyinstaller --name NetworkPrintRedirector_Console --onefile --icon=icon.ico --hidden-import cryptography.hazmat.backends.openssl --hidden-import PIL --hidden-import pystray main.py
        ```

    *   **Para criar `NetworkPrintRedirector.exe` (sem terminal, modo janela/bandeja):**
        ```bash
        pyinstaller --name NetworkPrintRedirector --windowed --noconsole --icon=icon.ico --onefile --hidden-import cryptography.hazmat.backends.openssl --hidden-import PIL --hidden-import pystray main.py
        ```
5.  Os executáveis finais estarão na subpasta `dist/`. Copie-os para a pasta de instalação desejada (ex: `C:\Program Files (x86)\NetworkPrintRedirector`) conforme descrito na seção "Instalação e Execução (Usando os Executáveis)".

## Troubleshooting

*   **Erro `input(): lost sys.stdin` ao iniciar `NetworkPrintRedirector.exe`:** Quase sempre significa que o arquivo de configuração (`.json`) não foi encontrado na pasta do executável ou está inválido. A versão sem console não pode pedir a configuração. Use o atalho do `NetworkPrintRedirector_Console.exe` com o parâmetro `--reconfigure` para criar/corrigir o arquivo de configuração na pasta correta.
*   **Ícone da bandeja não aparece:**
    *   Verifique se a opção `run_in_background` está definida como `true` no arquivo de configuração (`.json`). Use a versão Console com `--reconfigure` para verificar/alterar isso.
    *   Se compilando, certifique-se que `pystray` e `Pillow` foram incluídos corretamente (as flags `--hidden-import` nos comandos do PyInstaller ajudam com isso).
    *   Verifique os logs (`.log`) por erros relacionados à inicialização do `pystray` ou carregamento do ícone. O nível de log `DEBUG` pode ser útil aqui.
*   **Programa fecha ao fechar terminal (versão Console):** Se `run_in_background` for `true` na configuração, ele deveria minimizar para a bandeja mesmo se iniciado pelo `_Console.exe`. Se for `false`, o comportamento esperado é fechar junto com o terminal.
*   **Atalho não funciona / Erro ao iniciar pelo atalho:**
    *   Verifique se o caminho no campo "Destino" está correto, completo e entre aspas.
    *   Verifique se o parâmetro (`client`, `server`, `--reconfigure`) está **fora** das aspas e separado por um espaço.
    *   Verifique se o campo "Iniciar em" aponta para a pasta onde os executáveis **e** os arquivos `.json` estão localizados. Se este campo estiver vazio ou incorreto, o programa pode não encontrar seu arquivo de configuração.
*   **Comunicação não funciona:**
    *   Verifique se o `com0com` está instalado e configurado corretamente com pares de portas conectadas em **ambas** as máquinas (Cliente e Servidor).
    *   Confirme se a aplicação do usuário está enviando para a porta correta do par `com0com` no Cliente (ex: `COM2`).
    *   Confirme se o `NetworkPrintRedirector Cliente` está configurado para ler da **outra** porta do par `com0com` no Cliente (ex: `COM3`).
    *   Confirme se o `NetworkPrintRedirector Servidor` está configurado para escrever na porta correta do par `com0com` no Servidor (ex: `COM2`).
    *   Confirme se a impressora/emulador está configurada para ler da **outra** porta do par `com0com` no Servidor (ex: `COM3`).
    *   Verifique as configurações de IP e Porta TCP nos arquivos `.json` do Cliente e Servidor. O Cliente deve apontar para o IP e Porta corretos do Servidor.
    *   Verifique se não há um firewall bloqueando a conexão TCP entre Cliente e Servidor na porta configurada.
    *   Consulte os arquivos `.log` em ambas as máquinas para mensagens de erro detalhadas. Aumentar o `log_level` para `DEBUG` temporariamente pode ajudar a identificar o ponto da falha.

## Usando o Emulador de Impressora (Zebra Emulator Com)

Para testar a configuração do Servidor sem uma impressora física conectada, você pode usar o `Zebra Emulator Com`. Ele simula uma impressora escutando em uma porta serial e exibindo os dados recebidos no console.

**Como usar:**

1.  **Identifique a Porta Serial:** Na máquina Servidor, determine qual porta serial o emulador deve escutar. Seguindo o exemplo do `com0com` (`COM2 <=> COM3`), o `NetworkPrintRedirector Servidor` escreve em `COM2`, então o emulador deve escutar em `COM3`.
2.  **Execute o Emulador:** Abra um terminal (CMD ou PowerShell) na pasta onde o emulador está localizado.
    *   **Se usando o script Python:**
        ```bash
        python zebra_emulator_com.py
        ``` 
    *   **Se usando o executável:**
        Basta execultar o arquiv ZebraEmulatorCom.exe.
    
3. **Escholha a Porta Serial** Escolha a porta COM para ser ser escultada conforme a logica apresentada a cima.

4.  **Verifique a Saída:** O emulador iniciará e mostrará "Emulador Zebra escutando em COM3...". Quando o `NetworkPrintRedirector Servidor` receber dados do Cliente e escrevê-los na porta `COM2` (que está conectada a `COM3` via `com0com`), o emulador exibirá esses dados no console.

**Nota:** O emulador precisa da biblioteca `pyserial` instalada se você estiver executando o script `.py`. O executável `.exe` já deve conter as dependências necessárias.

## Autor

*   **AzayoDK**