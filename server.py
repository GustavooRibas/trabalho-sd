"""
Servidor do Chat Distribuído - Trabalho de Sistemas Distribuídos
Implementação de um servidor de chat estilo WhatsApp usando sockets TCP

Este módulo implementa o servidor central do sistema de chat distribuído,
responsável por gerenciar conexões de clientes, rotear mensagens,
administrar grupos e facilitar transferência de arquivos.

Arquitetura:
- Modelo cliente-servidor centralizado
- Threading para concorrência (uma thread por cliente)
- Locks para sincronização de dados compartilhados
- Protocolo JSON sobre TCP para comunicação

Funcionalidades principais:
- Autenticação básica de usuários
- Roteamento de mensagens privadas
- Gerenciamento completo de grupos
- Transferência de arquivos com armazenamento
- Listagem de usuários e grupos

Autores: Gustavo Rodrigues Ribeiro - RA:202003570, Luiz Gustavo Pontes de Araújo - RA:202109901, VICTOR FONSECA SANTANA - RA: 202004697
Data: Setembro 2025
"""

import socket
import threading
import json
import os
import base64
import struct
from datetime import datetime
from typing import Dict, List, Set

from concurrent.futures import ThreadPoolExecutor
import queue
import time
import random


# Utilitários de framing para mensagens JSON no TCP
# Enviamos 4 bytes (big-endian) com o tamanho do JSON, seguidos do JSON.
# Isso delimita claramente cada mensagem no stream TCP e evita JSON truncado/colado.

def send_json(sock: socket.socket, obj: dict):
    data = json.dumps(obj).encode('utf-8')
    header = struct.pack('!I', len(data))  # 4 bytes com o tamanho do JSON
    sock.sendall(header)                   # sendall garante envio completo do cabeçalho
    sock.sendall(data)                     # sendall garante envio completo do payload

def _recv_exact(sock: socket.socket, n: int) -> bytes:
    # Lê exatamente n bytes do socket (recv pode retornar menos que o solicitado).
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão fechada pelo par")
        buf.extend(chunk)
    return bytes(buf)

def recv_json(sock: socket.socket) -> dict:
    # Lê 4 bytes do cabeçalho para saber o tamanho e depois lê o JSON completo.
    header = _recv_exact(sock, 4)
    (length,) = struct.unpack('!I', header)
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode('utf-8'))

class ChatServer:
    """
    Classe principal do servidor de chat distribuído.
    
    Implementa servidor TCP multithreaded que gerencia conexões simultâneas
    de múltiplos clientes, coordena troca de mensagens e administra grupos.
    
    Atributos:
        host (str): Endereço IP do servidor
        port (int): Porta de escuta do servidor
        clients (Dict[str, socket]): Mapeamento username -> socket do cliente
        groups (Dict[str, Set[str]]): Mapeamento nome_grupo -> set de membros
        client_lock (threading.Lock): Lock para sincronizar acesso à lista de clientes
        group_lock (threading.Lock): Lock para sincronizar acesso aos grupos
        files_dir (str): Diretório para armazenamento de arquivos
    """
    
    def __init__(self, host='localhost', port=12345):
        """
        Inicializa servidor com configurações padrão.
        
        Args:
            host (str): Endereço IP para bind do servidor (padrão: localhost)
            port (int): Porta para escuta do servidor (padrão: 12345)
        """
        # Configurações de rede
        self.host = host
        self.port = port
        
        # Estruturas de dados principais
        # Dicionário que mapeia username para socket do cliente
        self.clients: Dict[str, socket.socket] = {}
        
        # Dicionário que mapeia nome do grupo para conjunto de membros
        self.groups: Dict[str, Set[str]] = {}
        
        # Locks para controle de concorrência
        # Protege acesso concorrente à estrutura de clientes
        self.client_lock = threading.Lock()
        
        # Protege acesso concorrente à estrutura de grupos
        self.group_lock = threading.Lock()
        
        # Configuração de armazenamento de arquivos
        self.files_dir = "server_files"
        
        # Cria diretório de arquivos se não existir
        if not os.path.exists(self.files_dir):
            os.makedirs(self.files_dir)


        # Configuração do Thread Pool
        # Limita o número de threads simultâneas
   
        self.MAX_WORKERS = int(os.getenv("CHAT_SERVER_MAX_WORKERS", "32"))  
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS, thread_name_prefix="worker")  
        self.task_queue: "queue.Queue[tuple[socket.socket, tuple]]" = queue.Queue()  
        self._stop_event = threading.Event()  

        # Estado do Heartbeat (liveness)
        # last_seen: instante do último ACK recebido de cada socket
        # missed_heartbeats: contagem de pings perdidos
        # hb_lock: protege as estruturas de heartbeat

        self.HEARTBEAT_INTERVAL = int(os.getenv("CHAT_HB_INTERVAL", "15"))  
        self.HEARTBEAT_TIMEOUT  = int(os.getenv("CHAT_HB_TIMEOUT",  "10"))  
        self.MAX_MISSED         = int(os.getenv("CHAT_HB_MAXMISSED","2"))   
        self.last_seen: Dict[socket.socket, datetime] = {}                  
        self.missed_heartbeats: Dict[socket.socket, int] = {}               
        self.hb_lock = threading.Lock()                                     

        # Inicializa workers fixos
        # Cada worker consome sockets da fila e chama handle_client.
        
        for _ in range(self.MAX_WORKERS):  
            self.executor.submit(self._worker_loop)  
    
    def _worker_loop(self):
        """
        Loop de worker do pool: aguarda um socket na fila
        e processa o cliente chamando handle_client. Mantém o mesmo
        comportamento de "uma thread por cliente" mas com um limite fixo.
        """
        while not self._stop_event.is_set():
            try:
                client_socket, client_address = self.task_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.handle_client(client_socket, client_address)
            finally:
                self.task_queue.task_done()
    
    def start_server(self):
        """
        Inicia servidor TCP e aceita conexões de clientes.
        
        Cria socket TCP, configura para reutilizar endereço, e entra em loop
        infinito aceitando conexões. Para cada cliente conectado, **enfileira**
        o socket para o pool fixo de threads (evita explosão de threads).
        
        Tratamento de exceções:
        - KeyboardInterrupt: Encerramento gracioso com Ctrl+C
        - Exception: Outros erros de socket ou sistema
        """
        # Cria socket TCP (AF_INET = IPv4, SOCK_STREAM = TCP)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Permite reutilizar endereço mesmo se recentemente usado
        # Evita erro "Address already in use" ao reiniciar servidor
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Associa socket ao endereço e porta especificados
            server_socket.bind((self.host, self.port))
            
            # Coloca socket em modo de escuta (máximo 128 conexões pendentes)
            server_socket.listen(128)  # backlog maior para alta demanda
            
            # Exibe informações de inicialização
            print(f"[SERVIDOR] Iniciado em {self.host}:{self.port}")
            print(f"[SERVIDOR] Aguardando conexões... (workers={self.MAX_WORKERS})")  

            # Inicia thread de monitoramento de heartbeat do servidor
            # Este monitor envia "heartbeat_ping" periodicamente e avalia timeouts

            hb_thread = threading.Thread(target=self._heartbeat_monitor, daemon=True) 
            hb_thread.start()
            
            # Loop principal do servidor
            while True:
                # Bloqueia até receber conexão de cliente
                client_socket, client_address = server_socket.accept()
                print(f"[SERVIDOR] Nova conexão de {client_address}")
                
                # Em vez de criar uma nova thread por cliente,
                # colocamos o socket na fila para que um worker do pool
                # assuma o processamento.

                self.task_queue.put((client_socket, client_address))
                
        except KeyboardInterrupt:
            # Usuário pressionou Ctrl+C para encerrar servidor
            print("\n[SERVIDOR] Encerrando servidor...")
            
        except Exception as e:
            # Outros erros durante operação do servidor
            print(f"[SERVIDOR] Erro: {e}")
            
        finally:
            # Encerramento do pool
            self._stop_event.set()
            server_socket.close()
            self.executor.shutdown(wait=False, cancel_futures=True)  
    
    def _heartbeat_monitor(self):  
        """
        Envia periodicamente 'heartbeat_ping' para todos os sockets ativos,
        verifica se recebemos 'heartbeat_ack' recente e aplica timeout com
        contagem de perdas. Se exceder MAX_MISSED, encerra e limpa a conexão.
        """
        while not self._stop_event.is_set():
            time.sleep(self.HEARTBEAT_INTERVAL)
            now = datetime.now()

            # Captura snapshot dos sockets atuais (thread-safe)
            with self.client_lock:
                sockets = list(self.clients.values())

            for sock in sockets:
                # Tenta enviar ping; se falhar, trata como conexão quebrada
                try:
                    send_json(sock, {"type": "heartbeat_ping"})  # Ping do app
                except Exception:
                    # Falha imediata ao enviar → limpa socket
                    self._cleanup_socket(sock, reason="falha no envio do heartbeat")
                    continue

                # Avalia timeout/misses com base no last_seen
                with self.hb_lock:
                    last = self.last_seen.get(sock)
                    missed = self.missed_heartbeats.get(sock, 0)

                if (last is None) or ((now - last).total_seconds() > (self.HEARTBEAT_INTERVAL + self.HEARTBEAT_TIMEOUT)):
                    # Não vimos ACK recente → incrementa perdas
                    with self.hb_lock:
                        self.missed_heartbeats[sock] = missed + 1
                        missed = self.missed_heartbeats[sock]

                    if missed > self.MAX_MISSED:
                        # Muitos heartbeats perdidos → encerra conexão
                        self._cleanup_socket(sock, reason="heartbeat timeout")
                else:
                    # Recebemos ACK recente → zera contagem de perdas
                    with self.hb_lock:
                        self.missed_heartbeats[sock] = 0

    def _cleanup_socket(self, sock: socket.socket, reason: str = ""):  
        """
        Remove o socket das estruturas (clients, heartbeat), fecha o socket
        e loga o motivo da limpeza. Evita vazamento de recursos.
        """
        try:
            sock.close()
        except:
            pass

        removed_user = None
        with self.client_lock:
            for user, s in list(self.clients.items()):
                if s is sock:
                    removed_user = user
                    del self.clients[user]
                    break

        with self.hb_lock:
            self.last_seen.pop(sock, None)
            self.missed_heartbeats.pop(sock, None)

        if removed_user:
            print(f"[SERVIDOR] Usuário {removed_user} desconectado ({reason})")
        else:
            if reason:
                print(f"[SERVIDOR] Socket limpo ({reason})")
    
    def handle_client(self, client_socket: socket.socket, client_address):
        """
        Gerencia comunicação com um cliente específico em thread dedicada (worker do pool).
        
        Processa mensagens recebidas do cliente em loop contínuo até
        desconexão. Cada mensagem é processada e resposta é enviada de volta.
        
        Args:
            client_socket (socket.socket): Socket TCP do cliente
            client_address (tuple): Endereço IP e porta do cliente
            
        Fluxo de processamento:
        1. Recebe dados do cliente via socket
        2. Decodifica JSON e processa mensagem
        3. Gera resposta baseada no tipo de operação
        4. Envia resposta de volta ao cliente
        5. Mantém registro de login do usuário
        """
        # Variável para armazenar nome do usuário após login
        username = None
        
        try:
            # Loop de comunicação com cliente
            while True:
                # Recebe dados do cliente (buffer de 4096 bytes)
                # Substituído por leitura com framing: uma mensagem completa por vez.
                message = recv_json(client_socket)
                
                # Tratamento de heartbeat no servidor:
                # Quando o cliente envia 'heartbeat_ack', apenas atualizamos liveness
                # e continuamos (sem gerar resposta adicional).
                if message.get('type') == 'heartbeat_ack': 
                    with self.hb_lock:
                        self.last_seen[client_socket] = datetime.now()
                        self.missed_heartbeats[client_socket] = 0
                    continue  # Não há resposta para ACK
                
                try:
                    # Decodifica bytes para string UTF-8 e parse JSON
                    
                    
                    # Processa mensagem e gera resposta
                    response = self.process_message(message, client_socket)
                    
                    # Tratamento especial para mensagens de login bem-sucedidas
                    if message.get('type') == 'login' and response.get('status') == 'success':
                        username = message['username']
                        
                        # Registra cliente na estrutura global (thread-safe)
                        with self.client_lock:
                            self.clients[username] = client_socket
                        # Inicializa estado de heartbeat do socket recém-logado
                        with self.hb_lock:
                            self.last_seen[client_socket] = datetime.now()
                            self.missed_heartbeats[client_socket] = 0
                            
                        print(f"[SERVIDOR] Usuário {username} conectado")
                    
                    # Envia resposta ao cliente se existir
                    if response:
                        # Envio agora usando framing para garantir entrega completa.
                        send_json(client_socket, response)
                        
                except json.JSONDecodeError:
                    # Cliente enviou dados que não são JSON válido
                    error_response = {
                        'type': 'error',
                        'message': 'Formato de mensagem inválido'
                    }
                    # Resposta de erro também com framing.
                    send_json(client_socket, error_response)
                    
        except ConnectionResetError:
            # Cliente fechou conexão abruptamente (ex: fechou aplicação)
            print(f"[SERVIDOR] Cliente {client_address} desconectou abruptamente")
        except ConnectionError:
            # Conexão fechada pelo par detectada pelos utilitários de framing.
            pass
        except Exception as e:
            # Outros erros de comunicação ou processamento
            print(f"[SERVIDOR] Erro com cliente {client_address}: {e}")
            
        finally:
            # Limpeza ao encerrar conexão com cliente
            if username:
                # Remove cliente da estrutura global (thread-safe)
                with self.client_lock:
                    if username in self.clients:
                        del self.clients[username]
                # Remove também dos mapas de heartbeat
                self._cleanup_socket(client_socket, reason="encerramento do handle_client")
            else:
                # Se não tinha username associado, ainda assim limpa HB maps
                self._cleanup_socket(client_socket, reason="encerramento sem login")
    

    def process_message(self, message: dict, sender_socket: socket.socket) -> dict:

        msg_type = message.get('type')
        if msg_type == 'login':
            return self.handle_login(message)
        elif msg_type == 'private_message':
            return self.handle_private_message(message)
        elif msg_type == 'create_group':
            return self.handle_create_group(message)
        elif msg_type == 'group_message':
            return self.handle_group_message(message)
        elif msg_type == 'send_file':
            return self.handle_send_file(message)
        elif msg_type == 'list_users':
            return self.handle_list_users()
        elif msg_type == 'list_groups':
            return self.handle_list_groups(message)
        elif msg_type == 'add_member':
            return self.handle_add_member(message)
        elif msg_type == 'list_group_members':
            return self.handle_list_group_members(message)
        else:
            return {'type': 'error','message': 'Tipo de mensagem não reconhecido'}

    def handle_login(self, message: dict) -> dict:
        username = message.get('username', '').strip()
        if not username:
            return {'type': 'login_response','status': 'error','message': 'Nome de usuário não pode estar vazio'}
        with self.client_lock:
            if username in self.clients:
                return {'type': 'login_response','status': 'error','message': 'Nome de usuário já em uso'}
        return {'type': 'login_response','status': 'success','message': f'Bem-vindo, {username}!'}

    def handle_private_message(self, message: dict) -> dict:
        sender = message.get('sender'); recipient = message.get('recipient'); content = message.get('content')
        timestamp = datetime.now().strftime("%H:%M:%S")
        if not all([sender, recipient, content]):
            return {'type': 'message_response','status': 'error','message': 'Dados da mensagem incompletos'}
        with self.client_lock:
            if recipient not in self.clients:
                return {'type': 'message_response','status': 'error','message': 'Usuário destinatário não encontrado'}
            recipient_socket = self.clients[recipient]
            notification = {'type': 'private_message_received','sender': sender,'content': content,'timestamp': timestamp}
            try:
                send_json(recipient_socket, notification) 
                return {'type': 'message_response','status': 'success','message': 'Mensagem enviada com sucesso'}
            except:
                return {'type': 'message_response','status': 'error','message': 'Erro ao enviar mensagem'}

    def handle_create_group(self, message: dict) -> dict:
        group_name = message.get('group_name', '').strip(); creator = message.get('creator')
        if not group_name or not creator:
            return {'type': 'group_response','status': 'error','message': 'Nome do grupo e criador são obrigatórios'}
        with self.group_lock:
            if group_name in self.groups:
                return {'type': 'group_response','status': 'error','message': 'Grupo já existe'}
            self.groups[group_name] = {creator}
            return {'type': 'group_response','status': 'success','message': f'Grupo "{group_name}" criado com sucesso'}

    def handle_group_message(self, message: dict) -> dict:
        sender = message.get('sender'); group_name = message.get('group_name'); content = message.get('content')
        timestamp = datetime.now().strftime("%H:%M:%S")
        if not all([sender, group_name, content]):
            return {'type': 'message_response','status': 'error','message': 'Dados da mensagem incompletos'}
        with self.group_lock:
            if group_name not in self.groups:
                return {'type': 'message_response','status': 'error','message': 'Grupo não encontrado'}
            if sender not in self.groups[group_name]:
                return {'type': 'message_response','status': 'error','message': f'Você não é membro do grupo {group_name}. Peça para alguém te adicionar.'}
            group_members = self.groups[group_name].copy()
        notification = {'type': 'group_message_received','sender': sender,'group_name': group_name,'content': content,'timestamp': timestamp}
        delivered = 0
        with self.client_lock:
            for m in group_members:
                if m != sender and m in self.clients:
                    try:
                        send_json(self.clients[m], notification)  
                        delivered += 1
                    except:
                        continue
        return {'type': 'message_response','status': 'success','message': f'Mensagem enviada para {delivered} membros do grupo'}

    def handle_add_member(self, message: dict) -> dict:
        group_name = message.get('group_name','').strip(); new_member = message.get('new_member','').strip(); requester = message.get('requester')
        if not all([group_name, new_member, requester]):
            return {'type': 'member_response','status': 'error','message': 'Dados incompletos para adicionar membro'}
        with self.group_lock:
            if group_name not in self.groups:
                return {'type': 'member_response','status': 'error','message': 'Grupo não encontrado'}
            if requester not in self.groups[group_name]:
                return {'type': 'member_response','status': 'error','message': 'Você não é membro deste grupo'}
        with self.client_lock:
            if new_member not in self.clients:
                return {'type': 'member_response','status': 'error','message': f'Usuário {new_member} não está conectado'}
        with self.group_lock:
            if new_member in self.groups[group_name]:
                return {'type': 'member_response','status': 'error','message': f'{new_member} já é membro do grupo'}
            self.groups[group_name].add(new_member)
        with self.client_lock:
            if new_member in self.clients:
                try:
                    notification = {'type': 'added_to_group','group_name': group_name,'added_by': requester,'timestamp': datetime.now().strftime("%H:%M:%S")}
                    send_json(self.clients[new_member], notification) 
                except:
                    pass
        return {'type': 'member_response','status': 'success','message': f'{new_member} foi adicionado ao grupo {group_name}'}

    def handle_list_group_members(self, message: dict) -> dict:
        group_name = message.get('group_name','').strip(); requester = message.get('requester')
        if not group_name or not requester:
            return {'type': 'members_list_response','status': 'error','message': 'Nome do grupo é obrigatório'}
        with self.group_lock:
            if group_name not in self.groups:
                return {'type': 'members_list_response','status': 'error','message': 'Grupo não encontrado'}
            if requester not in self.groups[group_name]:
                return {'type': 'members_list_response','status': 'error','message': 'Você não é membro deste grupo'}
            members = list(self.groups[group_name])
        return {'type': 'members_list_response','status': 'success','group_name': group_name,'members': members}

    def handle_send_file(self, message: dict) -> dict:
        sender = message.get('sender'); recipient = message.get('recipient'); filename = message.get('filename')
        file_data = message.get('file_data'); file_type = message.get('file_type','private')
        if not all([sender, recipient, filename, file_data]):
            return {'type': 'file_response','status': 'error','message': 'Dados do arquivo incompletos'}
        try:
            file_path = os.path.join(self.files_dir, f"{sender}_{filename}")
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            timestamp = datetime.now().strftime("%H:%M:%S")
            if file_type == 'private':
                with self.client_lock:
                    if recipient not in self.clients:
                        return {'type': 'file_response','status': 'error','message': 'Usuário destinatário não encontrado'}
                    notification = {'type': 'file_received','sender': sender,'filename': filename,'file_data': file_data,'timestamp': timestamp}
                    send_json(self.clients[recipient], notification) 
            else:
                with self.group_lock:
                    if recipient not in self.groups:
                        return {'type': 'file_response','status': 'error','message': 'Grupo não encontrado'}
                    if sender not in self.groups[recipient]:
                        return {'type': 'file_response','status': 'error','message': f'Você não é membro do grupo {recipient}. Peça para alguém te adicionar.'}
                    members = self.groups[recipient].copy()
                notification = {'type': 'group_file_received','sender': sender,'group_name': recipient,'filename': filename,'file_data': file_data,'timestamp': timestamp}
                with self.client_lock:
                    for m in members:
                        if m != sender and m in self.clients:
                            try:
                                send_json(self.clients[m], notification)  
                            except:
                                continue
            return {'type': 'file_response','status': 'success','message': 'Arquivo enviado com sucesso'}
        except Exception as e:
            return {'type': 'file_response','status': 'error','message': f'Erro ao processar arquivo: {str(e)}'}

    def handle_list_users(self) -> dict:
        with self.client_lock:
            users = list(self.clients.keys())
        return {'type': 'users_list','users': users}
    
    def handle_list_groups(self, message: dict) -> dict:
        username = message.get('username')
        with self.group_lock:
            if username:
                user_groups = [g for g, members in self.groups.items() if username in members]
                return {'type': 'groups_list','groups': user_groups}
            else:
                return {'type': 'groups_list','groups': list(self.groups.keys())}

def main():
    """
    Função principal do programa servidor.
    
    Cria instância do ChatServer, exibe informações de inicialização
    e inicia operação do servidor. Ponto de entrada quando executado
    como script principal.
    """
    # Exibe cabeçalho da aplicação
    print("=== SERVIDOR DE CHAT DISTRIBUÍDO ===")
    print("Trabalho de Sistemas Distribuídos")
    print("Pressione Ctrl+C para parar o servidor\n")
    
    # Cria e inicia servidor
    server = ChatServer()
    server.start_server()

# Executa função main apenas se arquivo for executado diretamente
# (não quando importado como módulo)
if __name__ == "__main__":
    main()
