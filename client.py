"""
Cliente do Chat Distribuído - Trabalho de Sistemas Distribuídos
Implementação de um cliente de chat estilo WhatsApp usando sockets TCP

Este módulo implementa a aplicação cliente que se conecta ao servidor
de chat distribuído, permitindo aos usuários trocar mensagens privadas,
participar de grupos e enviar arquivos.

Funcionalidades principais:
- Conexão TCP com servidor
- Interface de linha de comando (CLI)
- Mensagens privadas e em grupo
- Transferência de arquivos
- Gerenciamento de grupos (criação, adição de membros)

Autores: Gustavo Rodrigues Ribeiro - RA:202003570
Data: Setembro 2025
"""

import socket
import threading
import json
import os
import base64
import struct  
from datetime import datetime
import time  
import random  

# Utilitários de framing para o cliente
# Mesmo protocolo do servidor: 4 bytes (big-endian) com o tamanho do JSON + JSON.

def send_json(sock: socket.socket, obj: dict):
    data = json.dumps(obj).encode('utf-8')
    header = struct.pack('!I', len(data))  #  4 bytes com o tamanho do JSON
    sock.sendall(header)                   #  sendall do cabeçalho
    sock.sendall(data)                     #  sendall do payload

def _recv_exact(sock: socket.socket, n: int) -> bytes:
    # Lê exatamente n bytes (recv pode retornar menos).
    # Com timeout configurado no socket, uma ausência de dados por muito tempo
    # gerará socket.timeout — propagamos para o chamador (listen_server)
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout:  # permite detectar ausência de mensagens/heartbeats
            raise
        if not chunk:
            raise ConnectionError("Conexão fechada pelo par")
        buf.extend(chunk)
    return bytes(buf)

def recv_json(sock: socket.socket) -> dict:
    # Lê cabeçalho (4 bytes), depois o JSON completo.
    header = _recv_exact(sock, 4)
    (length,) = struct.unpack('!I', header)
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode('utf-8'))

class ChatClient:
    """
    Classe principal do cliente de chat distribuído.
    
    Responsável por gerenciar a conexão com o servidor, interface do usuário
    e processamento de mensagens em tempo real através de threading.
    
    Atributos:
        socket (socket.socket): Socket TCP para comunicação com servidor
        username (str): Nome do usuário autenticado
        connected (bool): Estado da conexão com servidor
        running (bool): Controle do loop principal da aplicação
        downloads_dir (str): Diretório para arquivos recebidos
    """
    
    def __init__(self):
        """
        Inicializa o cliente de chat.
        
        Configura variáveis de instância e cria diretório para downloads
        caso não exista.
        """
        # Socket de comunicação com o servidor
        self.socket = None
        
        # Nome do usuário após autenticação
        self.username = None
        
        # Flag de controle da conexão TCP
        self.connected = False
        
        # Flag de controle do loop principal
        self.running = True
        
        # Diretório para salvar arquivos recebidos
        self.downloads_dir = "client_downloads"
        
        # Cria diretório de downloads se não existir
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)

        # ---------------------------------------
        # Configuração e estado para heartbeat/reconexão
        # ---------------------------------------
        self.HEARTBEAT_GRACE = int(os.getenv("CHAT_HB_GRACE", "40"))  # Segundos sem ping antes de considerar queda
        self.RECONNECT_BASE  = float(os.getenv("CHAT_RC_BASE", "1.0")) # Backoff inicial (s)
        self.RECONNECT_MAX   = float(os.getenv("CHAT_RC_MAX",  "30.0"))# Backoff máximo (s)
        self._last_host = 'localhost'  # Guarda host/port da última conexão para reconectar
        self._last_port = 12345       
    def connect_to_server(self, host='localhost', port=12345):
        """
        Estabelece conexão TCP com o servidor de chat.
        
        Cria socket TCP, conecta ao servidor e inicia thread para escutar
        mensagens recebidas em tempo real.
        
        Args:
            host (str): Endereço IP ou hostname do servidor (padrão: localhost)
            port (int): Porta do servidor (padrão: 12345)
            
        Returns:
            bool: True se conexão foi estabelecida com sucesso, False caso contrário
        """
        try:
            # Cria socket TCP (AF_INET = IPv4, SOCK_STREAM = TCP)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Define timeout para permitir detectar ausência de mensagens/heartbeats
            self.socket.settimeout(5.0)
            
            # Conecta ao servidor no endereço e porta especificados
            self.socket.connect((host, port))
            
            # Guarda último host/port para reconexão
            self._last_host, self._last_port = host, port
            
            # Marca como conectado
            self.connected = True
            
            # Cria e inicia thread para escutar mensagens do servidor
            # Thread daemon é encerrada automaticamente quando programa principal termina
            listen_thread = threading.Thread(target=self.listen_server)
            listen_thread.daemon = True
            listen_thread.start()
            
            return True
            
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
            return False
    
    def listen_server(self):
        """
        Thread dedicada para escutar mensagens do servidor continuamente.
        
        Executa em loop até a conexão ser perdida ou aplicação encerrada.
        Processa mensagens JSON recebidas do servidor e atualiza interface.
        
        Tratamento de erros:
        - ConnectionResetError: Servidor desconectou
        - JSONDecodeError: Mensagem malformada recebida
        - Exception: Outros erros de comunicação
        """
        last_ping = time.time()  # Momento do último tráfego/heartbeat recebido
        backoff = self.RECONNECT_BASE  # Backoff inicial para reconexão

        while self.connected and self.running:
            try:
                # Recebe dados do servidor (buffer de 4096 bytes)
                # Substituído por leitura com framing: uma mensagem completa por vez.
                message = recv_json(self.socket)
                # Tráfego recebido — atualiza relógio e zera backoff
                last_ping = time.time()
                backoff = self.RECONNECT_BASE
                
                # Responde imediatamente a heartbeat_ping
                if message.get('type') == 'heartbeat_ping':
                    try:
                        self.send_message({'type': 'heartbeat_ack'})  # ACK para o servidor
                    except Exception:
                        # Se até mesmo responder falhar, forçaremos reconexão no próximo loop
                        pass
                    continue  # Nada mais a fazer para pings

                # Decodifica bytes para string UTF-8 e converte JSON para dict
                # Decodificação/parse já feitos por recv_json.
                
                # Processa mensagem recebida
                self.handle_server_message(message)
                
            except socket.timeout:
                # Sem receber nada por um período; checa se passou do grace
                if (time.time() - last_ping) > self.HEARTBEAT_GRACE:
                    print("\n[WARN] Sem heartbeat do servidor — tentando reconectar...")
                    if not self._attempt_reconnect_inline(backoff): 
                        # A reconexão inline falhou — cresce backoff e tenta novamente no próximo timeout
                        backoff = min(self.RECONNECT_MAX, backoff * 2) * (0.5 + random.random())
                    else:
                        # Reconectado — reseta marcadores
                        last_ping = time.time()
                        backoff = self.RECONNECT_BASE
                # Caso contrário, apenas continua aguardando
                continue

            except ConnectionResetError:
                # Servidor fechou conexão abruptamente
                print("\n[ERRO] Conexão com servidor perdida — tentando reconectar...")
                if not self._attempt_reconnect_inline(backoff):
                    backoff = min(self.RECONNECT_MAX, backoff * 2) * (0.5 + random.random())
                else:
                    last_ping = time.time()
                    backoff = self.RECONNECT_BASE
                continue
                
            except json.JSONDecodeError:
                # Mensagem recebida não é JSON válido
                print("\n[ERRO] Mensagem inválida recebida do servidor")
                
            except ConnectionError:
                # Conexão fechada pelo par detectada pelo framing — tenta reconectar
                print("\n[ERRO] Conexão encerrada — tentando reconectar...")
                if not self._attempt_reconnect_inline(backoff):
                    backoff = min(self.RECONNECT_MAX, backoff * 2) * (0.5 + random.random())
                else:
                    last_ping = time.time()
                    backoff = self.RECONNECT_BASE
                continue
            
            except Exception as e:
                # Outros erros de comunicação
                print(f"\n[ERRO] Erro ao receber mensagem: {e}")
                # Tenta reconectar também em erros gerais de socket
                if not self._attempt_reconnect_inline(backoff):
                    backoff = min(self.RECONNECT_MAX, backoff * 2) * (0.5 + random.random())
                else:
                    last_ping = time.time()
                    backoff = self.RECONNECT_BASE
                continue
        
        # Marca como desconectado ao sair do loop
        self.connected = False

    def _attempt_reconnect_inline(self, delay: float) -> bool:
        """
        Tenta reconectar **nesta mesma thread** (sem criar nova thread de escuta),
        respeitando um atraso (backoff) fornecido. Reutiliza _last_host/_last_port.
        Se reconectar, refaz login automaticamente (se houver username).
        """
        try:
            time.sleep(delay)
            # Fecha socket antigo (se existir)
            try:
                if self.socket:
                    self.socket.close()
            except:
                pass

            # Cria novo socket e configura timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self._last_host, self._last_port))

            # Substitui o socket atual pela nova conexão
            self.socket = sock
            self.connected = True

            # Reenvia login automaticamente (se já tínhamos username)
            if self.username:
                self.send_message({'type': 'login', 'username': self.username})
            print("[OK] Reconectado.")
            return True

        except Exception as e:
            print(f"[FALHA] Reconexão ainda não foi possível: {e}")
            self.connected = False
            return False
    
    def handle_server_message(self, message: dict):
        """
        Processa diferentes tipos de mensagens recebidas do servidor.
        
        Analisa o campo 'type' da mensagem e chama a função apropriada
        para cada tipo de notificação (mensagem privada, grupo, arquivo, etc.).
        
        Args:
            message (dict): Mensagem JSON recebida do servidor
            
        Tipos de mensagem suportados:
        - private_message_received: Nova mensagem privada
        - group_message_received: Nova mensagem de grupo  
        - file_received: Arquivo privado recebido
        - group_file_received: Arquivo de grupo recebido
        - users_list: Lista de usuários online
        - groups_list: Lista de grupos do usuário
        - added_to_group: Notificação de adição ao grupo
        - members_list_response: Lista de membros de grupo
        - *_response: Respostas de confirmação de operações
        """
        # Extrai tipo da mensagem
        msg_type = message.get('type')
        
        # Processa mensagem privada recebida
        if msg_type == 'private_message_received':
            print(f"\n💬 [PRIVADA] {message['sender']} ({message['timestamp']}): {message['content']}")
            
        # Processa mensagem de grupo recebida
        elif msg_type == 'group_message_received':
            print(f"\n👥 [GRUPO: {message['group_name']}] {message['sender']} ({message['timestamp']}): {message['content']}")
            
        # Processa arquivo privado recebido
        elif msg_type == 'file_received':
            self.handle_file_received(message)
            
        # Processa arquivo de grupo recebido
        elif msg_type == 'group_file_received':
            self.handle_group_file_received(message)
            
        # Exibe lista de usuários conectados
        elif msg_type == 'users_list':
            print("\n📋 Usuários conectados:")
            for i, user in enumerate(message['users'], 1):
                # Marca o próprio usuário na lista
                status = " (você)" if user == self.username else ""
                print(f"  {i}. {user}{status}")
                
        # Exibe lista de grupos do usuário
        elif msg_type == 'groups_list':
            print(f"\n📋 Grupos disponíveis ({len(message['groups'])}):")
            for i, group in enumerate(message['groups'], 1):
                print(f"  {i}. {group}")
        
        # Notifica que foi adicionado a um grupo
        elif msg_type == 'added_to_group':
            print(f"\n🎉 Você foi adicionado ao grupo '{message['group_name']}' por {message['added_by']} ({message['timestamp']})")
        
        # Processa resposta da lista de membros de grupo
        elif msg_type == 'members_list_response':
            if message.get('status') == 'success':
                group_name = message['group_name']
                members = message['members']
                print(f"\n👥 Membros do grupo '{group_name}' ({len(members)}):")
                for i, member in enumerate(members, 1):
                    # Marca o próprio usuário na lista
                    status = " (você)" if member == self.username else ""
                    print(f"  {i}. {member}{status}")
            else:
                # Exibe erro se operação falhou
                print(f"\n❌ {message['message']}")
                
        # Processa respostas de confirmação de operações
        elif msg_type in ['login_response', 'message_response', 'group_response', 'file_response', 'member_response']:
            # Determina se operação foi bem-sucedida
            status = message.get('status', 'unknown')
            msg = message.get('message', 'Sem mensagem')
            
            # Escolhe ícone baseado no status
            icon = "✅" if status == 'success' else "❌"
            print(f"\n{icon} {msg}")
        
        # Reexibe prompt do usuário após processar mensagem
        print(f"\n{self.username}> ", end='', flush=True)
    
    def handle_file_received(self, message: dict):
        """
        Processa arquivo recebido via mensagem privada.
        
        Decodifica dados Base64, salva arquivo localmente e notifica usuário.
        Nome do arquivo é prefixado com remetente para evitar conflitos.
        
        Args:
            message (dict): Mensagem contendo dados do arquivo
                - sender: Nome do remetente
                - filename: Nome original do arquivo
                - file_data: Dados em Base64
                - timestamp: Horário do envio
        """
        # Extrai informações do arquivo
        sender = message['sender']
        filename = message['filename']
        file_data = message['file_data']
        timestamp = message['timestamp']
        
        try:
            # Cria nome seguro prefixado com remetente
            safe_filename = f"{sender}_{filename}"
            file_path = os.path.join(self.downloads_dir, safe_filename)
            
            # Decodifica Base64 e salva arquivo
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            
            # Notifica usuário sobre recebimento
            print(f"\n📎 [ARQUIVO PRIVADO] {sender} ({timestamp}) enviou: {filename}")
            print(f"   Salvo como: {file_path}")
            
        except Exception as e:
            print(f"\n❌ Erro ao salvar arquivo de {sender}: {e}")
    
    def handle_group_file_received(self, message: dict):
        """
        Processa arquivo recebido via grupo.
        
        Similar ao arquivo privado, mas nome é prefixado com grupo e remetente
        para melhor organização.
        
        Args:
            message (dict): Mensagem contendo dados do arquivo de grupo
                - sender: Nome do remetente
                - group_name: Nome do grupo
                - filename: Nome original do arquivo
                - file_data: Dados em Base64
                - timestamp: Horário do envio
        """
        # Extrai informações do arquivo
        sender = message['sender']
        group_name = message['group_name']
        filename = message['filename']
        file_data = message['file_data']
        timestamp = message['timestamp']
        
        try:
            # Cria nome seguro com prefixo de grupo e remetente
            safe_filename = f"{group_name}_{sender}_{filename}"
            file_path = os.path.join(self.downloads_dir, safe_filename)
            
            # Decodifica Base64 e salva arquivo
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            
            # Notifica usuário sobre recebimento
            print(f"\n📎 [ARQUIVO GRUPO: {group_name}] {sender} ({timestamp}) enviou: {filename}")
            print(f"   Salvo como: {file_path}")
            
        except Exception as e:
            print(f"\n❌ Erro ao salvar arquivo do grupo: {e}")
    
    def send_message(self, message: dict):
        """
        Envia mensagem JSON para o servidor.
        
        Serializa dicionário Python para JSON e envia via socket TCP.
        
        Args:
            message (dict): Dicionário com dados da mensagem a ser enviada
        """
        try:
            # Converte dict para JSON e codifica em bytes UTF-8
            # Envia via socket TCP
            # Substituído por send_json (framing + sendall) para evitar envio parcial.
            send_json(self.socket, message)
            
        except Exception as e:
            print(f"[ERRO] Não foi possível enviar mensagem: {e}")
    
    def login(self):
        """
        Realiza autenticação do usuário no servidor.
        
        Solicita nome de usuário até que um válido seja aceito pelo servidor.
        Usa método simplificado aguardando resposta com sleep.
        """
        while not self.username:
            # Solicita nome de usuário
            username = input("Digite seu nome de usuário: ").strip()
            
            if username:
                # Cria mensagem de login
                message = {
                    'type': 'login',
                    'username': username
                }
                
                # Envia ao servidor
                self.send_message(message)
                
                # Aguarda resposta do servidor (método simplificado)
                time.sleep(0.5)  # usando time já importado
                
                # Se ainda conectado, assume login bem-sucedido
                if self.connected:
                    self.username = username
                    print(f"\n✅ Conectado como {username}")
                    break
            else:
                print("Nome de usuário não pode estar vazio!")
    
    def send_private_message(self):
        """
        Interface para envio de mensagem privada.
        
        Coleta destinatário e conteúdo da mensagem do usuário,
        valida dados e envia ao servidor.
        """
        # Coleta nome do destinatário
        recipient = input("Digite o nome do destinatário: ").strip()
        if not recipient:
            print("❌ Nome do destinatário é obrigatório")
            return
        
        # Coleta conteúdo da mensagem
        content = input("Digite sua mensagem: ").strip()
        if not content:
            print("❌ Mensagem não pode estar vazia")
            return
        
        # Cria mensagem estruturada
        message = {
            'type': 'private_message',
            'sender': self.username,
            'recipient': recipient,
            'content': content
        }
        
        # Envia ao servidor
        self.send_message(message)
    
    def create_group(self):
        """
        Interface para criação de novo grupo.
        
        Coleta nome do grupo e envia solicitação de criação ao servidor.
        """
        # Coleta nome do grupo
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        # Cria mensagem de criação de grupo
        message = {
            'type': 'create_group',
            'group_name': group_name,
            'creator': self.username
        }
        
        # Envia ao servidor
        self.send_message(message)
    
    def send_group_message(self):
        """
        Interface para envio de mensagem para grupo.
        
        Coleta nome do grupo e conteúdo da mensagem,
        valida dados e envia ao servidor.
        """
        # Coleta nome do grupo
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        # Coleta conteúdo da mensagem
        content = input("Digite sua mensagem: ").strip()
        if not content:
            print("❌ Mensagem não pode estar vazia")
            return
        
        # Cria mensagem estruturada
        message = {
            'type': 'group_message',
            'sender': self.username,
            'group_name': group_name,
            'content': content
        }
        
        # Envia ao servidor
        self.send_message(message)
    
    def send_file(self):
        """
        Interface para envio de arquivos.
        
        Permite escolher entre envio privado ou para grupo,
        lê arquivo do sistema, codifica em Base64 e envia ao servidor.
        """
        # Apresenta opções de envio
        print("Tipos de envio:")
        print("1. Mensagem privada")
        print("2. Grupo")
        
        # Coleta escolha do usuário
        choice = input("Escolha o tipo (1-2): ").strip()
        if choice not in ['1', '2']:
            print("❌ Opção inválida")
            return
        
        # Determina tipo de envio
        file_type = 'private' if choice == '1' else 'group'
        
        # Coleta destinatário baseado no tipo
        if file_type == 'private':
            recipient = input("Digite o nome do destinatário: ").strip()
        else:
            recipient = input("Digite o nome do grupo: ").strip()
        
        if not recipient:
            print("❌ Destinatário é obrigatório")
            return
        
        # Coleta caminho do arquivo
        file_path = input("Digite o caminho do arquivo: ").strip()
        if not os.path.exists(file_path):
            print("❌ Arquivo não encontrado")
            return
        
        try:
            # Extrai nome do arquivo
            filename = os.path.basename(file_path)
            
            # Lê arquivo em modo binário e codifica em Base64
            with open(file_path, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Cria mensagem estruturada
            message = {
                'type': 'send_file',
                'sender': self.username,
                'recipient': recipient,
                'filename': filename,
                'file_data': file_data,
                'file_type': file_type
            }
            
            # Envia ao servidor
            self.send_message(message)
            print(f"📎 Enviando arquivo {filename}...")
            
        except Exception as e:
            print(f"❌ Erro ao enviar arquivo: {e}")
    
    def list_users(self):
        """
        Solicita lista de usuários conectados ao servidor.
        """
        message = {
            'type': 'list_users'
        }
        self.send_message(message)
    
    def list_groups(self):
        """
        Solicita lista de grupos dos quais o usuário participa.
        """
        message = {
            'type': 'list_groups',
            'username': self.username
        }
        self.send_message(message)
    
    def add_member_to_group(self):
        """
        Interface para adicionar membro a um grupo.
        
        Coleta nome do grupo e usuário a ser adicionado,
        valida dados e envia solicitação ao servidor.
        """
        # Coleta nome do grupo
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        # Coleta usuário a ser adicionado
        new_member = input("Digite o nome do usuário para adicionar: ").strip()
        if not new_member:
            print("❌ Nome do usuário é obrigatório")
            return
        
        # Valida que não está tentando adicionar a si mesmo
        if new_member == self.username:
            print("❌ Você não pode adicionar a si mesmo")
            return
        
        # Cria mensagem estruturada
        message = {
            'type': 'add_member',
            'group_name': group_name,
            'new_member': new_member,
            'requester': self.username
        }
        
        # Envia ao servidor
        self.send_message(message)
    
    def list_group_members(self):
        """
        Interface para listar membros de um grupo.
        
        Coleta nome do grupo e solicita lista de membros ao servidor.
        """
        # Coleta nome do grupo
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        # Cria mensagem estruturada
        message = {
            'type': 'list_group_members',
            'group_name': group_name,
            'requester': self.username
        }
        
        # Envia ao servidor
        self.send_message(message)
    
    def show_menu(self):
        """
        Exibe menu principal de opções do sistema.
        
        Apresenta todas as funcionalidades disponíveis numeradas
        para facilitar navegação do usuário.
        """
        print("\n" + "="*50)
        print("📱 CHAT DISTRIBUÍDO - MENU DE OPÇÕES")
        print("="*50)
        print("1. 💬 Enviar mensagem privada")
        print("2. 👥 Criar grupo")
        print("3. 👥 Enviar mensagem para grupo")
        print("4. 📎 Enviar arquivo")
        print("5. 📋 Listar usuários online")
        print("6. 📋 Listar meus grupos")
        print("7. ➕ Adicionar membro ao grupo")
        print("8. 👥 Ver membros do grupo")
        print("9. ❓ Mostrar menu")
        print("10. 🚪 Sair")
        print("="*50)
    
    def run(self):
        """
        Loop principal do cliente.
        
        Coordena todo o fluxo da aplicação:
        1. Conecta ao servidor
        2. Realiza login
        3. Exibe menu
        4. Processa comandos do usuário em loop
        5. Trata encerramento gracioso
        
        Tratamento de exceções:
        - KeyboardInterrupt: Ctrl+C pressionado
        - EOFError: Input encerrado (Ctrl+D)
        """
        # Exibe cabeçalho da aplicação
        print("=== CLIENTE DE CHAT DISTRIBUÍDO ===")
        print("Trabalho de Sistemas Distribuídos\n")
        
        # Tenta conectar ao servidor
        if not self.connect_to_server():
            return
        
        # Realiza processo de login
        self.login()
        
        # Exibe menu de opções
        self.show_menu()
        
        # Loop principal de comandos
        while self.running and self.connected:
            try:
                # Lê comando do usuário
                command = input(f"\n{self.username}> ").strip()
                
                # Processa comando selecionado
                if command == '1':
                    self.send_private_message()
                elif command == '2':
                    self.create_group()
                elif command == '3':
                    self.send_group_message()
                elif command == '4':
                    self.send_file()
                elif command == '5':
                    self.list_users()
                elif command == '6':
                    self.list_groups()
                elif command == '7':
                    self.add_member_to_group()
                elif command == '8':
                    self.list_group_members()
                elif command == '9':
                    self.show_menu()
                elif command == '10':
                    # Encerra aplicação
                    print("👋 Encerrando cliente...")
                    self.running = False
                    break
                elif command == '':
                    # Comando vazio, continua loop
                    continue
                else:
                    # Comando inválido
                    print("❌ Comando inválido. Digite '9' para ver o menu.")
                    
            except KeyboardInterrupt:
                # Ctrl+C pressionado
                print("\n\n👋 Encerrando cliente...")
                self.running = False
                break
                
            except EOFError:
                # EOF encontrado (Ctrl+D)
                print("\n\n👋 Encerrando cliente...")
                self.running = False
                break
        
        # Fecha conexão antes de encerrar
        if self.socket:
            self.socket.close()
            
        print("✅ Cliente encerrado.")

def main():
    """
    Função principal do programa cliente.
    
    Cria instância do ChatClient e executa aplicação.
    Ponto de entrada quando executado como script principal.
    """
    # Cria e executa cliente
    client = ChatClient()
    client.run()

# Executa função main apenas se arquivo for executado diretamente
# (não quando importado como módulo)
if __name__ == "__main__":
    main()
