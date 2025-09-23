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

Autores: Gustavo Rodrigues Ribeiro - RA:202003570
Data: Setembro 2025
"""

import socket
import threading
import json
import os
import base64
from datetime import datetime
from typing import Dict, List, Set

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
    
    def start_server(self):
        """
        Inicia servidor TCP e aceita conexões de clientes.
        
        Cria socket TCP, configura para reutilizar endereço, e entra em loop
        infinito aceitando conexões. Para cada cliente conectado, cria uma
        thread dedicada para gerenciar comunicação.
        
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
            
            # Coloca socket em modo de escuta (máximo 10 conexões pendentes)
            server_socket.listen(10)
            
            # Exibe informações de inicialização
            print(f"[SERVIDOR] Iniciado em {self.host}:{self.port}")
            print("[SERVIDOR] Aguardando conexões...")
            
            # Loop principal do servidor
            while True:
                # Bloqueia até receber conexão de cliente
                client_socket, client_address = server_socket.accept()
                print(f"[SERVIDOR] Nova conexão de {client_address}")
                
                # Cria thread dedicada para gerenciar este cliente
                # Cada cliente tem sua própria thread para processamento paralelo
                client_thread = threading.Thread(
                    target=self.handle_client,           # Função a ser executada
                    args=(client_socket, client_address) # Argumentos da função
                )
                
                # Thread daemon é encerrada quando programa principal termina
                client_thread.daemon = True
                
                # Inicia thread de processamento do cliente
                client_thread.start()
                
        except KeyboardInterrupt:
            # Usuário pressionou Ctrl+C para encerrar servidor
            print("\n[SERVIDOR] Encerrando servidor...")
            
        except Exception as e:
            # Outros erros durante operação do servidor
            print(f"[SERVIDOR] Erro: {e}")
            
        finally:
            # Sempre fecha socket do servidor ao encerrar
            server_socket.close()
    
    def handle_client(self, client_socket: socket.socket, client_address):
        """
        Gerencia comunicação com um cliente específico em thread dedicada.
        
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
                data = client_socket.recv(4096)
                
                # Se não recebeu dados, cliente desconectou
                if not data:
                    break
                
                try:
                    # Decodifica bytes para string UTF-8 e parse JSON
                    message = json.loads(data.decode('utf-8'))
                    
                    # Processa mensagem e gera resposta
                    response = self.process_message(message, client_socket)
                    
                    # Tratamento especial para mensagens de login bem-sucedidas
                    if message.get('type') == 'login' and response.get('status') == 'success':
                        username = message['username']
                        
                        # Registra cliente na estrutura global (thread-safe)
                        with self.client_lock:
                            self.clients[username] = client_socket
                            
                        print(f"[SERVIDOR] Usuário {username} conectado")
                    
                    # Envia resposta ao cliente se existir
                    if response:
                        response_json = json.dumps(response).encode('utf-8')
                        client_socket.send(response_json)
                        
                except json.JSONDecodeError:
                    # Cliente enviou dados que não são JSON válido
                    error_response = {
                        'type': 'error',
                        'message': 'Formato de mensagem inválido'
                    }
                    error_json = json.dumps(error_response).encode('utf-8')
                    client_socket.send(error_json)
                    
        except ConnectionResetError:
            # Cliente fechou conexão abruptamente (ex: fechou aplicação)
            print(f"[SERVIDOR] Cliente {client_address} desconectou abruptamente")
            
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
                        
                print(f"[SERVIDOR] Usuário {username} desconectado")
                
            # Sempre fecha socket do cliente
            client_socket.close()
    
    def process_message(self, message: dict, sender_socket: socket.socket) -> dict:
        """
        Roteador central para processar diferentes tipos de mensagens.
        
        Analisa campo 'type' da mensagem e delega processamento para
        função específica. Implementa padrão Strategy para diferentes
        tipos de operação.
        
        Args:
            message (dict): Mensagem JSON recebida do cliente
            sender_socket (socket.socket): Socket do cliente remetente
            
        Returns:
            dict: Resposta JSON para enviar ao cliente
            
        Tipos de mensagem suportados:
        - login: Autenticação de usuário
        - private_message: Mensagem privada entre usuários
        - create_group: Criação de novo grupo
        - group_message: Mensagem para grupo
        - send_file: Envio de arquivo
        - list_users: Listar usuários conectados
        - list_groups: Listar grupos do usuário
        - add_member: Adicionar membro ao grupo
        - list_group_members: Listar membros de grupo
        """
        # Extrai tipo da mensagem
        msg_type = message.get('type')
        
        # Roteia mensagem para handler apropriado
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
            # Tipo de mensagem não reconhecido
            return {
                'type': 'error',
                'message': 'Tipo de mensagem não reconhecido'
            }
    
    def handle_login(self, message: dict) -> dict:
        """
        Processa tentativa de login de usuário.
        
        Valida se nome de usuário é válido e único no sistema.
        Implementa autenticação básica apenas por nome de usuário.
        
        Args:
            message (dict): Mensagem contendo dados de login
                - username: Nome de usuário desejado
                
        Returns:
            dict: Resposta indicando sucesso ou falha do login
            
        Validações realizadas:
        - Nome não pode estar vazio
        - Nome deve ser único (não pode estar em uso)
        """
        # Extrai e limpa nome de usuário
        username = message.get('username', '').strip()
        
        # Valida se nome não está vazio
        if not username:
            return {
                'type': 'login_response',
                'status': 'error',
                'message': 'Nome de usuário não pode estar vazio'
            }
        
        # Verifica se nome já está em uso (thread-safe)
        with self.client_lock:
            if username in self.clients:
                return {
                    'type': 'login_response',
                    'status': 'error',
                    'message': 'Nome de usuário já em uso'
                }
        
        # Login aprovado
        return {
            'type': 'login_response',
            'status': 'success',
            'message': f'Bem-vindo, {username}!'
        }
    
    def handle_private_message(self, message: dict) -> dict:
        """
        Processa envio de mensagem privada entre usuários.
        
        Valida existência do destinatário e roteia mensagem diretamente.
        Adiciona timestamp e notifica destinatário em tempo real.
        
        Args:
            message (dict): Dados da mensagem privada
                - sender: Nome do remetente
                - recipient: Nome do destinatário
                - content: Conteúdo da mensagem
                
        Returns:
            dict: Confirmação de entrega ou erro
        """
        # Extrai dados da mensagem
        sender = message.get('sender')
        recipient = message.get('recipient')
        content = message.get('content')
        
        # Gera timestamp atual
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Valida se todos os campos obrigatórios estão presentes
        if not all([sender, recipient, content]):
            return {
                'type': 'message_response',
                'status': 'error',
                'message': 'Dados da mensagem incompletos'
            }
        
        # Verifica se destinatário existe e está conectado (thread-safe)
        with self.client_lock:
            if recipient not in self.clients:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Usuário destinatário não encontrado'
                }
            
            # Obtém socket do destinatário
            recipient_socket = self.clients[recipient]
            
            # Cria notificação para o destinatário
            notification = {
                'type': 'private_message_received',
                'sender': sender,
                'content': content,
                'timestamp': timestamp
            }
            
            try:
                # Envia notificação ao destinatário
                notification_json = json.dumps(notification).encode('utf-8')
                recipient_socket.send(notification_json)
                
                # Confirma entrega ao remetente
                return {
                    'type': 'message_response',
                    'status': 'success',
                    'message': 'Mensagem enviada com sucesso'
                }
                
            except:
                # Erro ao enviar (destinatário pode ter desconectado)
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Erro ao enviar mensagem'
                }
    
    def handle_create_group(self, message: dict) -> dict:
        """
        Processa criação de novo grupo de chat.
        
        Valida se nome do grupo é único e cria grupo com criador
        como primeiro membro.
        
        Args:
            message (dict): Dados de criação do grupo
                - group_name: Nome desejado para o grupo
                - creator: Nome do usuário criador
                
        Returns:
            dict: Confirmação de criação ou erro
        """
        # Extrai e limpa dados
        group_name = message.get('group_name', '').strip()
        creator = message.get('creator')
        
        # Valida campos obrigatórios
        if not group_name or not creator:
            return {
                'type': 'group_response',
                'status': 'error',
                'message': 'Nome do grupo e criador são obrigatórios'
            }
        
        # Verifica unicidade do nome e cria grupo (thread-safe)
        with self.group_lock:
            if group_name in self.groups:
                return {
                    'type': 'group_response',
                    'status': 'error',
                    'message': 'Grupo já existe'
                }
            
            # Cria grupo com criador como primeiro membro
            # Usa Set para evitar membros duplicados
            self.groups[group_name] = {creator}
            
            return {
                'type': 'group_response',
                'status': 'success',
                'message': f'Grupo "{group_name}" criado com sucesso'
            }
    
    def handle_group_message(self, message: dict) -> dict:
        """
        Processa envio de mensagem para grupo.
        
        Valida se remetente é membro do grupo e distribui mensagem
        para todos os outros membros conectados.
        
        Args:
            message (dict): Dados da mensagem de grupo
                - sender: Nome do remetente
                - group_name: Nome do grupo destinatário
                - content: Conteúdo da mensagem
                
        Returns:
            dict: Confirmação com número de membros que receberam
            
        Controle de acesso:
        - Apenas membros do grupo podem enviar mensagens
        - Mensagem é enviada para todos membros exceto remetente
        """
        # Extrai dados da mensagem
        sender = message.get('sender')
        group_name = message.get('group_name')
        content = message.get('content')
        
        # Gera timestamp atual
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Valida campos obrigatórios
        if not all([sender, group_name, content]):
            return {
                'type': 'message_response',
                'status': 'error',
                'message': 'Dados da mensagem incompletos'
            }
        
        # Verifica existência do grupo e membership (thread-safe)
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Implementa controle de acesso: apenas membros podem enviar
            if sender not in self.groups[group_name]:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': f'Você não é membro do grupo {group_name}. Peça para alguém te adicionar.'
                }
            
            # Cria cópia da lista de membros para evitar modificações durante iteração
            group_members = self.groups[group_name].copy()
        
        # Cria notificação para membros do grupo
        notification = {
            'type': 'group_message_received',
            'sender': sender,
            'group_name': group_name,
            'content': content,
            'timestamp': timestamp
        }
        
        # Distribui mensagem para membros conectados (exceto remetente)
        delivered_count = 0
        with self.client_lock:
            for member in group_members:
                # Não envia para o próprio remetente
                if member != sender and member in self.clients:
                    try:
                        # Obtém socket do membro
                        member_socket = self.clients[member]
                        
                        # Envia notificação
                        notification_json = json.dumps(notification).encode('utf-8')
                        member_socket.send(notification_json)
                        
                        delivered_count += 1
                        
                    except:
                        # Ignora erro de envio para membro específico
                        # Pode estar desconectando ou com problema de rede
                        continue
        
        return {
            'type': 'message_response',
            'status': 'success',
            'message': f'Mensagem enviada para {delivered_count} membros do grupo'
        }
    
    def handle_add_member(self, message: dict) -> dict:
        """
        Processa adição de novo membro a um grupo existente.
        
        Implementa controle de acesso onde apenas membros atuais
        podem adicionar novos membros. Notifica o novo membro automaticamente.
        
        Args:
            message (dict): Dados de adição de membro
                - group_name: Nome do grupo
                - new_member: Nome do usuário a ser adicionado
                - requester: Nome do usuário solicitante
                
        Returns:
            dict: Confirmação de adição ou erro
            
        Validações:
        - Grupo deve existir
        - Solicitante deve ser membro do grupo
        - Novo membro deve estar conectado
        - Novo membro não pode já ser membro
        """
        # Extrai e limpa dados
        group_name = message.get('group_name', '').strip()
        new_member = message.get('new_member', '').strip()
        requester = message.get('requester')
        
        # Valida campos obrigatórios
        if not all([group_name, new_member, requester]):
            return {
                'type': 'member_response',
                'status': 'error',
                'message': 'Dados incompletos para adicionar membro'
            }
        
        # Verifica existência do grupo e permissão do solicitante
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Controle de acesso: apenas membros podem adicionar outros
            if requester not in self.groups[group_name]:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': 'Você não é membro deste grupo'
                }
        
        # Verifica se novo membro está conectado
        with self.client_lock:
            if new_member not in self.clients:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': f'Usuário {new_member} não está conectado'
                }
        
        # Adiciona membro ao grupo (thread-safe)
        with self.group_lock:
            # Verifica se já é membro
            if new_member in self.groups[group_name]:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': f'{new_member} já é membro do grupo'
                }
            
            # Adiciona ao conjunto de membros
            self.groups[group_name].add(new_member)
        
        # Notifica o novo membro sobre adição ao grupo
        with self.client_lock:
            if new_member in self.clients:
                try:
                    # Cria notificação
                    notification = {
                        'type': 'added_to_group',
                        'group_name': group_name,
                        'added_by': requester,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    
                    # Envia notificação
                    member_socket = self.clients[new_member]
                    notification_json = json.dumps(notification).encode('utf-8')
                    member_socket.send(notification_json)
                    
                except:
                    # Ignora erro de notificação
                    # Membro foi adicionado mesmo se notificação falhou
                    pass
        
        return {
            'type': 'member_response',
            'status': 'success',
            'message': f'{new_member} foi adicionado ao grupo {group_name}'
        }
    
    def handle_list_group_members(self, message: dict) -> dict:
        """
        Processa solicitação de lista de membros de um grupo.
        
        Implementa controle de privacidade onde apenas membros do grupo
        podem ver a lista completa de participantes.
        
        Args:
            message (dict): Solicitação de lista de membros
                - group_name: Nome do grupo
                - requester: Nome do usuário solicitante
                
        Returns:
            dict: Lista de membros ou erro de permissão
        """
        # Extrai dados
        group_name = message.get('group_name', '').strip()
        requester = message.get('requester')
        
        # Valida campos obrigatórios
        if not group_name or not requester:
            return {
                'type': 'members_list_response',
                'status': 'error',
                'message': 'Nome do grupo é obrigatório'
            }
        
        # Verifica existência e permissão (thread-safe)
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'members_list_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Controle de privacidade: apenas membros podem ver lista
            if requester not in self.groups[group_name]:
                return {
                    'type': 'members_list_response',
                    'status': 'error',
                    'message': 'Você não é membro deste grupo'
                }
            
            # Converte Set para List para serialização JSON
            members = list(self.groups[group_name])
        
        return {
            'type': 'members_list_response',
            'status': 'success',
            'group_name': group_name,
            'members': members
        }
    
    def handle_send_file(self, message: dict) -> dict:
        """
        Processa envio de arquivos entre usuários ou grupos.
        
        Implementa transferência de arquivos codificados em Base64,
        armazenamento no servidor para backup e distribuição para
        destinatários apropriados.
        
        Args:
            message (dict): Dados do envio de arquivo
                - sender: Nome do remetente
                - recipient: Nome do destinatário (usuário ou grupo)
                - filename: Nome original do arquivo
                - file_data: Dados do arquivo em Base64
                - file_type: 'private' ou 'group'
                
        Returns:
            dict: Confirmação de envio ou erro
            
        Fluxo de processamento:
        1. Valida dados de entrada
        2. Salva arquivo no servidor (backup)
        3. Distribui para destinatário(s)
        4. Confirma operação
        """
        # Extrai dados da mensagem
        sender = message.get('sender')
        recipient = message.get('recipient')  # Pode ser usuário ou grupo
        filename = message.get('filename')
        file_data = message.get('file_data')  # Dados em Base64
        file_type = message.get('file_type', 'private')  # 'private' ou 'group'
        
        # Valida campos obrigatórios
        if not all([sender, recipient, filename, file_data]):
            return {
                'type': 'file_response',
                'status': 'error',
                'message': 'Dados do arquivo incompletos'
            }
        
        try:
            # Salva arquivo no servidor para backup/auditoria
            # Nome prefixado com remetente para evitar conflitos
            file_path = os.path.join(self.files_dir, f"{sender}_{filename}")
            
            with open(file_path, 'wb') as f:
                # Decodifica Base64 e salva dados binários
                f.write(base64.b64decode(file_data))
            
            # Gera timestamp para notificações
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if file_type == 'private':
                # Envio para usuário específico
                with self.client_lock:
                    if recipient not in self.clients:
                        return {
                            'type': 'file_response',
                            'status': 'error',
                            'message': 'Usuário destinatário não encontrado'
                        }
                    
                    # Cria notificação de arquivo recebido
                    notification = {
                        'type': 'file_received',
                        'sender': sender,
                        'filename': filename,
                        'file_data': file_data,
                        'timestamp': timestamp
                    }
                    
                    # Envia para destinatário
                    recipient_socket = self.clients[recipient]
                    notification_json = json.dumps(notification).encode('utf-8')
                    recipient_socket.send(notification_json)
                    
            else:  # file_type == 'group'
                # Envio para grupo
                with self.group_lock:
                    if recipient not in self.groups:
                        return {
                            'type': 'file_response',
                            'status': 'error',
                            'message': 'Grupo não encontrado'
                        }
                    
                    # Verifica se remetente é membro do grupo
                    if sender not in self.groups[recipient]:
                        return {
                            'type': 'file_response',
                            'status': 'error',
                            'message': f'Você não é membro do grupo {recipient}. Peça para alguém te adicionar.'
                        }
                    
                    # Obtém lista de membros
                    group_members = self.groups[recipient].copy()
                
                # Cria notificação de arquivo de grupo
                notification = {
                    'type': 'group_file_received',
                    'sender': sender,
                    'group_name': recipient,
                    'filename': filename,
                    'file_data': file_data,
                    'timestamp': timestamp
                }
                
                # Distribui arquivo para membros do grupo (exceto remetente)
                with self.client_lock:
                    for member in group_members:
                        if member != sender and member in self.clients:
                            try:
                                member_socket = self.clients[member]
                                notification_json = json.dumps(notification).encode('utf-8')
                                member_socket.send(notification_json)
                            except:
                                # Ignora erro de envio para membro específico
                                continue
            
            return {
                'type': 'file_response',
                'status': 'success',
                'message': 'Arquivo enviado com sucesso'
            }
            
        except Exception as e:
            # Erro durante processamento do arquivo
            return {
                'type': 'file_response',
                'status': 'error',
                'message': f'Erro ao processar arquivo: {str(e)}'
            }
    
    def handle_list_users(self) -> dict:
        """
        Processa solicitação de lista de usuários conectados.
        
        Retorna lista atual de todos os usuários com sessão ativa.
        Operação thread-safe para evitar inconsistências.
        
        Returns:
            dict: Lista de nomes de usuários conectados
        """
        # Obtém lista de usuários conectados (thread-safe)
        with self.client_lock:
            users = list(self.clients.keys())
        
        return {
            'type': 'users_list',
            'users': users
        }
    
    def handle_list_groups(self, message: dict) -> dict:
        """
        Processa solicitação de lista de grupos.
        
        Pode listar todos os grupos (para admin) ou apenas grupos
        dos quais o usuário é membro (para usuários normais).
        
        Args:
            message (dict): Solicitação de lista
                - username: Nome do usuário (opcional)
                
        Returns:
            dict: Lista de grupos relevantes
        """
        username = message.get('username')
        
        with self.group_lock:
            if username:
                # Lista apenas grupos dos quais o usuário é membro
                user_groups = [group for group, members in self.groups.items() 
                              if username in members]
                return {
                    'type': 'groups_list',
                    'groups': user_groups
                }
            else:
                # Lista todos os grupos (funcionalidade administrativa)
                return {
                    'type': 'groups_list',
                    'groups': list(self.groups.keys())
                }

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
