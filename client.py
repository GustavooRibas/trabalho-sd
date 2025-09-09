#!/usr/bin/env python3
"""
Cliente do Chat Distribuído - Trabalho de Sistemas Distribuídos
Implementação de um cliente de chat estilo WhatsApp usando sockets TCP
"""

import socket
import threading
import json
import os
import base64
from datetime import datetime

class ChatClient:
    def __init__(self):
        self.socket = None
        self.username = None
        self.connected = False
        self.running = True
        
        # Diretório para arquivos recebidos
        self.downloads_dir = "client_downloads"
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)
    
    def connect_to_server(self, host='localhost', port=12345):
        """Conecta ao servidor"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.connected = True
            
            # Thread para escutar mensagens do servidor
            listen_thread = threading.Thread(target=self.listen_server)
            listen_thread.daemon = True
            listen_thread.start()
            
            return True
            
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
            return False
    
    def listen_server(self):
        """Escuta mensagens do servidor"""
        while self.connected and self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                message = json.loads(data.decode('utf-8'))
                self.handle_server_message(message)
                
            except ConnectionResetError:
                print("\n[ERRO] Conexão com servidor perdida")
                break
            except json.JSONDecodeError:
                print("\n[ERRO] Mensagem inválida recebida do servidor")
            except Exception as e:
                print(f"\n[ERRO] Erro ao receber mensagem: {e}")
                break
        
        self.connected = False
    
    def handle_server_message(self, message: dict):
        """Processa mensagens recebidas do servidor"""
        msg_type = message.get('type')
        
        if msg_type == 'private_message_received':
            print(f"\n💬 [PRIVADA] {message['sender']} ({message['timestamp']}): {message['content']}")
            
        elif msg_type == 'group_message_received':
            print(f"\n👥 [GRUPO: {message['group_name']}] {message['sender']} ({message['timestamp']}): {message['content']}")
            
        elif msg_type == 'file_received':
            self.handle_file_received(message)
            
        elif msg_type == 'group_file_received':
            self.handle_group_file_received(message)
            
        elif msg_type == 'users_list':
            print("\n📋 Usuários conectados:")
            for i, user in enumerate(message['users'], 1):
                status = " (você)" if user == self.username else ""
                print(f"  {i}. {user}{status}")
                
        elif msg_type == 'groups_list':
            print(f"\n📋 Grupos disponíveis ({len(message['groups'])}):")
            for i, group in enumerate(message['groups'], 1):
                print(f"  {i}. {group}")
        
        elif msg_type == 'added_to_group':
            print(f"\n🎉 Você foi adicionado ao grupo '{message['group_name']}' por {message['added_by']} ({message['timestamp']})")
        
        elif msg_type == 'members_list_response':
            if message.get('status') == 'success':
                group_name = message['group_name']
                members = message['members']
                print(f"\n👥 Membros do grupo '{group_name}' ({len(members)}):")
                for i, member in enumerate(members, 1):
                    status = " (você)" if member == self.username else ""
                    print(f"  {i}. {member}{status}")
            else:
                print(f"\n❌ {message['message']}")
                
        elif msg_type in ['login_response', 'message_response', 'group_response', 'file_response', 'member_response']:
            status = message.get('status', 'unknown')
            msg = message.get('message', 'Sem mensagem')
            icon = "✅" if status == 'success' else "❌"
            print(f"\n{icon} {msg}")
        
        # Reexibe prompt
        print(f"\n{self.username}> ", end='', flush=True)
    
    def handle_file_received(self, message: dict):
        """Processa arquivo recebido (mensagem privada)"""
        sender = message['sender']
        filename = message['filename']
        file_data = message['file_data']
        timestamp = message['timestamp']
        
        try:
            # Salva arquivo
            safe_filename = f"{sender}_{filename}"
            file_path = os.path.join(self.downloads_dir, safe_filename)
            
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            
            print(f"\n📎 [ARQUIVO PRIVADO] {sender} ({timestamp}) enviou: {filename}")
            print(f"   Salvo como: {file_path}")
            
        except Exception as e:
            print(f"\n❌ Erro ao salvar arquivo de {sender}: {e}")
    
    def handle_group_file_received(self, message: dict):
        """Processa arquivo recebido (grupo)"""
        sender = message['sender']
        group_name = message['group_name']
        filename = message['filename']
        file_data = message['file_data']
        timestamp = message['timestamp']
        
        try:
            # Salva arquivo
            safe_filename = f"{group_name}_{sender}_{filename}"
            file_path = os.path.join(self.downloads_dir, safe_filename)
            
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            
            print(f"\n📎 [ARQUIVO GRUPO: {group_name}] {sender} ({timestamp}) enviou: {filename}")
            print(f"   Salvo como: {file_path}")
            
        except Exception as e:
            print(f"\n❌ Erro ao salvar arquivo do grupo: {e}")
    
    def send_message(self, message: dict):
        """Envia mensagem para o servidor"""
        try:
            self.socket.send(json.dumps(message).encode('utf-8'))
        except Exception as e:
            print(f"[ERRO] Não foi possível enviar mensagem: {e}")
    
    def login(self):
        """Realiza login no servidor"""
        while not self.username:
            username = input("Digite seu nome de usuário: ").strip()
            if username:
                message = {
                    'type': 'login',
                    'username': username
                }
                self.send_message(message)
                
                # Aguarda resposta (simplificado)
                import time
                time.sleep(0.5)
                
                if self.connected:
                    self.username = username
                    print(f"\n✅ Conectado como {username}")
                    break
            else:
                print("Nome de usuário não pode estar vazio!")
    
    def send_private_message(self):
        """Envia mensagem privada"""
        recipient = input("Digite o nome do destinatário: ").strip()
        if not recipient:
            print("❌ Nome do destinatário é obrigatório")
            return
        
        content = input("Digite sua mensagem: ").strip()
        if not content:
            print("❌ Mensagem não pode estar vazia")
            return
        
        message = {
            'type': 'private_message',
            'sender': self.username,
            'recipient': recipient,
            'content': content
        }
        self.send_message(message)
    
    def create_group(self):
        """Cria um novo grupo"""
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        message = {
            'type': 'create_group',
            'group_name': group_name,
            'creator': self.username
        }
        self.send_message(message)
    
    def send_group_message(self):
        """Envia mensagem para grupo"""
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        content = input("Digite sua mensagem: ").strip()
        if not content:
            print("❌ Mensagem não pode estar vazia")
            return
        
        message = {
            'type': 'group_message',
            'sender': self.username,
            'group_name': group_name,
            'content': content
        }
        self.send_message(message)
    
    def send_file(self):
        """Envia arquivo"""
        print("Tipos de envio:")
        print("1. Mensagem privada")
        print("2. Grupo")
        
        choice = input("Escolha o tipo (1-2): ").strip()
        if choice not in ['1', '2']:
            print("❌ Opção inválida")
            return
        
        file_type = 'private' if choice == '1' else 'group'
        
        if file_type == 'private':
            recipient = input("Digite o nome do destinatário: ").strip()
        else:
            recipient = input("Digite o nome do grupo: ").strip()
        
        if not recipient:
            print("❌ Destinatário é obrigatório")
            return
        
        file_path = input("Digite o caminho do arquivo: ").strip()
        if not os.path.exists(file_path):
            print("❌ Arquivo não encontrado")
            return
        
        try:
            filename = os.path.basename(file_path)
            
            # Lê arquivo e converte para base64
            with open(file_path, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            
            message = {
                'type': 'send_file',
                'sender': self.username,
                'recipient': recipient,
                'filename': filename,
                'file_data': file_data,
                'file_type': file_type
            }
            
            self.send_message(message)
            print(f"📎 Enviando arquivo {filename}...")
            
        except Exception as e:
            print(f"❌ Erro ao enviar arquivo: {e}")
    
    def list_users(self):
        """Lista usuários conectados"""
        message = {
            'type': 'list_users'
        }
        self.send_message(message)
    
    def list_groups(self):
        """Lista grupos"""
        message = {
            'type': 'list_groups',
            'username': self.username
        }
        self.send_message(message)
    
    def add_member_to_group(self):
        """Adiciona membro a um grupo"""
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        new_member = input("Digite o nome do usuário para adicionar: ").strip()
        if not new_member:
            print("❌ Nome do usuário é obrigatório")
            return
        
        if new_member == self.username:
            print("❌ Você não pode adicionar a si mesmo")
            return
        
        message = {
            'type': 'add_member',
            'group_name': group_name,
            'new_member': new_member,
            'requester': self.username
        }
        self.send_message(message)
    
    def list_group_members(self):
        """Lista membros de um grupo"""
        group_name = input("Digite o nome do grupo: ").strip()
        if not group_name:
            print("❌ Nome do grupo é obrigatório")
            return
        
        message = {
            'type': 'list_group_members',
            'group_name': group_name,
            'requester': self.username
        }
        self.send_message(message)
    
    def show_menu(self):
        """Mostra menu de opções"""
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
        """Loop principal do cliente"""
        print("=== CLIENTE DE CHAT DISTRIBUÍDO ===")
        print("Trabalho de Sistemas Distribuídos\n")
        
        # Conecta ao servidor
        if not self.connect_to_server():
            return
        
        # Faz login
        self.login()
        
        # Mostra menu inicial
        self.show_menu()
        
        # Loop principal
        while self.running and self.connected:
            try:
                command = input(f"\n{self.username}> ").strip()
                
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
                    print("Encerrando cliente...")
                    self.running = False
                    break
                elif command == '':
                    continue
                else:
                    print("Comando inválido. Digite '9' para ver o menu.")
                    
            except KeyboardInterrupt:
                print("\n\nEncerrando cliente...")
                self.running = False
                break
            except EOFError:
                print("\n\nEncerrando cliente...")
                self.running = False
                break
        
        # Fecha conexão
        if self.socket:
            self.socket.close()
        print("Cliente encerrado.")

def main():
    """Função principal do cliente"""
    client = ChatClient()
    client.run()

if __name__ == "__main__":
    main()