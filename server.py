#!/usr/bin/env python3
"""
Servidor do Chat Distribuído - Trabalho de Sistemas Distribuídos
Implementação de um servidor de chat estilo WhatsApp usando sockets TCP
"""

import socket
import threading
import json
import os
import base64
from datetime import datetime
from typing import Dict, List, Set

class ChatServer:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.clients: Dict[str, socket.socket] = {}  # username -> socket
        self.groups: Dict[str, Set[str]] = {}  # group_name -> set of usernames
        self.client_lock = threading.Lock()
        self.group_lock = threading.Lock()
        
        # Diretório para arquivos
        self.files_dir = "server_files"
        if not os.path.exists(self.files_dir):
            os.makedirs(self.files_dir)
    
    def start_server(self):
        """Inicia o servidor e aceita conexões"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(10)
            print(f"[SERVIDOR] Iniciado em {self.host}:{self.port}")
            print("[SERVIDOR] Aguardando conexões...")
            
            while True:
                client_socket, client_address = server_socket.accept()
                print(f"[SERVIDOR] Nova conexão de {client_address}")
                
                # Thread para lidar com cada cliente
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
                
        except KeyboardInterrupt:
            print("\n[SERVIDOR] Encerrando servidor...")
        except Exception as e:
            print(f"[SERVIDOR] Erro: {e}")
        finally:
            server_socket.close()
    
    def handle_client(self, client_socket: socket.socket, client_address):
        """Gerencia a comunicação com um cliente específico"""
        username = None
        
        try:
            while True:
                # Recebe dados do cliente
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = json.loads(data.decode('utf-8'))
                    response = self.process_message(message, client_socket)
                    
                    # Se é uma mensagem de login, registra o cliente
                    if message.get('type') == 'login' and response.get('status') == 'success':
                        username = message['username']
                        with self.client_lock:
                            self.clients[username] = client_socket
                        print(f"[SERVIDOR] Usuário {username} conectado")
                    
                    # Envia resposta para o cliente
                    if response:
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        
                except json.JSONDecodeError:
                    error_response = {
                        'type': 'error',
                        'message': 'Formato de mensagem inválido'
                    }
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                    
        except ConnectionResetError:
            print(f"[SERVIDOR] Cliente {client_address} desconectou abruptamente")
        except Exception as e:
            print(f"[SERVIDOR] Erro com cliente {client_address}: {e}")
        finally:
            # Remove cliente ao desconectar
            if username:
                with self.client_lock:
                    if username in self.clients:
                        del self.clients[username]
                print(f"[SERVIDOR] Usuário {username} desconectado")
            client_socket.close()
    
    def process_message(self, message: dict, sender_socket: socket.socket) -> dict:
        """Processa diferentes tipos de mensagens"""
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
            return {
                'type': 'error',
                'message': 'Tipo de mensagem não reconhecido'
            }
    
    def handle_login(self, message: dict) -> dict:
        """Processa login do usuário"""
        username = message.get('username', '').strip()
        
        if not username:
            return {
                'type': 'login_response',
                'status': 'error',
                'message': 'Nome de usuário não pode estar vazio'
            }
        
        with self.client_lock:
            if username in self.clients:
                return {
                    'type': 'login_response',
                    'status': 'error',
                    'message': 'Nome de usuário já em uso'
                }
        
        return {
            'type': 'login_response',
            'status': 'success',
            'message': f'Bem-vindo, {username}!'
        }
    
    def handle_private_message(self, message: dict) -> dict:
        """Processa mensagem privada"""
        sender = message.get('sender')
        recipient = message.get('recipient')
        content = message.get('content')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if not all([sender, recipient, content]):
            return {
                'type': 'message_response',
                'status': 'error',
                'message': 'Dados da mensagem incompletos'
            }
        
        with self.client_lock:
            if recipient not in self.clients:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Usuário destinatário não encontrado'
                }
            
            # Envia mensagem para o destinatário
            recipient_socket = self.clients[recipient]
            notification = {
                'type': 'private_message_received',
                'sender': sender,
                'content': content,
                'timestamp': timestamp
            }
            
            try:
                recipient_socket.send(json.dumps(notification).encode('utf-8'))
                return {
                    'type': 'message_response',
                    'status': 'success',
                    'message': 'Mensagem enviada com sucesso'
                }
            except:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Erro ao enviar mensagem'
                }
    
    def handle_create_group(self, message: dict) -> dict:
        """Cria um novo grupo"""
        group_name = message.get('group_name', '').strip()
        creator = message.get('creator')
        
        if not group_name or not creator:
            return {
                'type': 'group_response',
                'status': 'error',
                'message': 'Nome do grupo e criador são obrigatórios'
            }
        
        with self.group_lock:
            if group_name in self.groups:
                return {
                    'type': 'group_response',
                    'status': 'error',
                    'message': 'Grupo já existe'
                }
            
            # Cria grupo com o criador como primeiro membro
            self.groups[group_name] = {creator}
            
            return {
                'type': 'group_response',
                'status': 'success',
                'message': f'Grupo "{group_name}" criado com sucesso'
            }
    
    def handle_group_message(self, message: dict) -> dict:
        """Processa mensagem para grupo"""
        sender = message.get('sender')
        group_name = message.get('group_name')
        content = message.get('content')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if not all([sender, group_name, content]):
            return {
                'type': 'message_response',
                'status': 'error',
                'message': 'Dados da mensagem incompletos'
            }
        
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Verifica se o usuário é membro do grupo
            if sender not in self.groups[group_name]:
                return {
                    'type': 'message_response',
                    'status': 'error',
                    'message': f'Você não é membro do grupo {group_name}. Peça para alguém te adicionar.'
                }
            
            group_members = self.groups[group_name].copy()
        
        # Envia mensagem para todos os membros do grupo (exceto o remetente)
        notification = {
            'type': 'group_message_received',
            'sender': sender,
            'group_name': group_name,
            'content': content,
            'timestamp': timestamp
        }
        
        delivered_count = 0
        with self.client_lock:
            for member in group_members:
                if member != sender and member in self.clients:
                    try:
                        member_socket = self.clients[member]
                        member_socket.send(json.dumps(notification).encode('utf-8'))
                        delivered_count += 1
                    except:
                        continue
        
        return {
            'type': 'message_response',
            'status': 'success',
            'message': f'Mensagem enviada para {delivered_count} membros do grupo'
        }
    
    def handle_add_member(self, message: dict) -> dict:
        """Adiciona membro a um grupo"""
        group_name = message.get('group_name', '').strip()
        new_member = message.get('new_member', '').strip()
        requester = message.get('requester')
        
        if not all([group_name, new_member, requester]):
            return {
                'type': 'member_response',
                'status': 'error',
                'message': 'Dados incompletos para adicionar membro'
            }
        
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Verifica se o solicitante é membro do grupo
            if requester not in self.groups[group_name]:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': 'Você não é membro deste grupo'
                }
        
        # Verifica se o novo membro está conectado
        with self.client_lock:
            if new_member not in self.clients:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': f'Usuário {new_member} não está conectado'
                }
        
        with self.group_lock:
            # Verifica se já é membro
            if new_member in self.groups[group_name]:
                return {
                    'type': 'member_response',
                    'status': 'error',
                    'message': f'{new_member} já é membro do grupo'
                }
            
            # Adiciona o membro
            self.groups[group_name].add(new_member)
        
        # Notifica o novo membro
        with self.client_lock:
            if new_member in self.clients:
                try:
                    notification = {
                        'type': 'added_to_group',
                        'group_name': group_name,
                        'added_by': requester,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    member_socket = self.clients[new_member]
                    member_socket.send(json.dumps(notification).encode('utf-8'))
                except:
                    pass
        
        return {
            'type': 'member_response',
            'status': 'success',
            'message': f'{new_member} foi adicionado ao grupo {group_name}'
        }
    
    def handle_list_group_members(self, message: dict) -> dict:
        """Lista membros de um grupo"""
        group_name = message.get('group_name', '').strip()
        requester = message.get('requester')
        
        if not group_name or not requester:
            return {
                'type': 'members_list_response',
                'status': 'error',
                'message': 'Nome do grupo é obrigatório'
            }
        
        with self.group_lock:
            if group_name not in self.groups:
                return {
                    'type': 'members_list_response',
                    'status': 'error',
                    'message': 'Grupo não encontrado'
                }
            
            # Verifica se o solicitante é membro do grupo
            if requester not in self.groups[group_name]:
                return {
                    'type': 'members_list_response',
                    'status': 'error',
                    'message': 'Você não é membro deste grupo'
                }
            
            members = list(self.groups[group_name])
        
        return {
            'type': 'members_list_response',
            'status': 'success',
            'group_name': group_name,
            'members': members
        }
    
    def handle_send_file(self, message: dict) -> dict:
        """Processa envio de arquivo"""
        sender = message.get('sender')
        recipient = message.get('recipient')  # pode ser usuário ou grupo
        filename = message.get('filename')
        file_data = message.get('file_data')  # dados em base64
        file_type = message.get('file_type', 'private')  # 'private' ou 'group'
        
        if not all([sender, recipient, filename, file_data]):
            return {
                'type': 'file_response',
                'status': 'error',
                'message': 'Dados do arquivo incompletos'
            }
        
        try:
            # Salva arquivo no servidor
            file_path = os.path.join(self.files_dir, f"{sender}_{filename}")
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            
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
                    
                    notification = {
                        'type': 'file_received',
                        'sender': sender,
                        'filename': filename,
                        'file_data': file_data,
                        'timestamp': timestamp
                    }
                    
                    recipient_socket = self.clients[recipient]
                    recipient_socket.send(json.dumps(notification).encode('utf-8'))
                    
            else:  # file_type == 'group'
                # Envio para grupo
                with self.group_lock:
                    if recipient not in self.groups:
                        return {
                            'type': 'file_response',
                            'status': 'error',
                            'message': 'Grupo não encontrado'
                        }
                    
                    # Verifica se o remetente é membro do grupo
                    if sender not in self.groups[recipient]:
                        return {
                            'type': 'file_response',
                            'status': 'error',
                            'message': f'Você não é membro do grupo {recipient}. Peça para alguém te adicionar.'
                        }
                    
                    group_members = self.groups[recipient].copy()
                
                notification = {
                    'type': 'group_file_received',
                    'sender': sender,
                    'group_name': recipient,
                    'filename': filename,
                    'file_data': file_data,
                    'timestamp': timestamp
                }
                
                with self.client_lock:
                    for member in group_members:
                        if member != sender and member in self.clients:
                            try:
                                member_socket = self.clients[member]
                                member_socket.send(json.dumps(notification).encode('utf-8'))
                            except:
                                continue
            
            return {
                'type': 'file_response',
                'status': 'success',
                'message': 'Arquivo enviado com sucesso'
            }
            
        except Exception as e:
            return {
                'type': 'file_response',
                'status': 'error',
                'message': f'Erro ao processar arquivo: {str(e)}'
            }
    
    def handle_list_users(self) -> dict:
        """Lista usuários conectados"""
        with self.client_lock:
            users = list(self.clients.keys())
        
        return {
            'type': 'users_list',
            'users': users
        }
    
    def handle_list_groups(self, message: dict) -> dict:
        """Lista grupos disponíveis"""
        username = message.get('username')
        
        with self.group_lock:
            if username:
                # Lista apenas grupos do usuário
                user_groups = [group for group, members in self.groups.items() 
                              if username in members]
                return {
                    'type': 'groups_list',
                    'groups': user_groups
                }
            else:
                # Lista todos os grupos
                return {
                    'type': 'groups_list',
                    'groups': list(self.groups.keys())
                }

def main():
    """Função principal do servidor"""
    print("=== SERVIDOR DE CHAT DISTRIBUÍDO ===")
    print("Trabalho de Sistemas Distribuídos")
    print("Pressione Ctrl+C para parar o servidor\n")
    
    server = ChatServer()
    server.start_server()

if __name__ == "__main__":
    main()