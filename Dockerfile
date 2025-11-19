FROM python:3.11-slim

# Diretório de trabalho
WORKDIR /app

# Copia TODO o projeto para dentro da imagem (precisamos dos chat_pb2* que estão em api/)
COPY . /app

# Dependências do servidor gRPC
RUN pip install --no-cache-dir -r grpc_server/requirements.txt

# Para o Python encontrar chat_pb2*.py na pasta api/
ENV PYTHONPATH=/app/api

EXPOSE 50051

# Inicia o servidor gRPC
CMD ["python", "grpc_server/server.py"]
