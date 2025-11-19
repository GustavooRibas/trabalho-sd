import time
import grpc
from concurrent import futures
import os, sys

# garante que os módulos gerados (chat_pb2*.py) em /app/api sejam encontrados
sys.path.append(os.environ.get("PYTHONPATH", "/app/api"))

import chat_pb2
import chat_pb2_grpc

class ChatService(chat_pb2_grpc.ChatServiceServicer):
    # ---- Unary ----
    def Login(self, request, context):
        return chat_pb2.StatusResponse(success=True, message=f"Bem-vindo, {request.username}!")

    def CreateGroup(self, request, context):
        return chat_pb2.StatusResponse(success=True, message=f'Grupo "{request.group_name}" criado (stub).')

    def AddMemberToGroup(self, request, context):
        return chat_pb2.StatusResponse(success=True, message=f'{request.new_member} adicionado (stub).')

    def ListUsers(self, request, context):
        return chat_pb2.UserList(usernames=[])

    def ListGroupMembers(self, request, context):
        return chat_pb2.UserList(usernames=[])

    # ---- Client streaming ----
    def UploadFile(self, request_iterator, context):
        # consome o stream e retorna OK (stub)
        for _ in request_iterator:
            pass
        return chat_pb2.StatusResponse(success=True, message="Arquivo recebido (stub).")

    # ---- Bidirectional streaming ----
    def ChatStream(self, request_iterator, context):
        # eco simples: qualquer mensagem do cliente vira uma notificação
        for cli in request_iterator:
            yield chat_pb2.ServerMessage(
                notification=chat_pb2.Notification(message=f"recebido de {cli.username} (stub)")
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("[gRPC] Servidor no :50051 (stub) — pronto")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
