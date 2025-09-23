# Chat Distribuído - Sistema Estilo WhatsApp

**Trabalho de Sistemas Distribuídos**  
Implementação de um sistema de chat distribuído usando sockets TCP em Python.

## 📋 Funcionalidades Implementadas

### ✅ Requisitos Funcionais Atendidos:
- **Arquitetura cliente-servidor** usando sockets TCP
- **Mensagens privadas** entre usuários em tempo real
- **Criação e gerenciamento completo de grupos**
- **Adição de membros aos grupos** com controle de acesso
- **Listagem de membros por grupo**
- **Envio e recebimento de arquivos** (texto, imagem, PDF, etc.)
- **Gerenciamento de sessão** com username único
- **Identificação e roteamento correto** de mensagens

### ✅ Requisitos Não Funcionais Atendidos:
- **Implementação obrigatória com sockets TCP**
- **Servidor multithreaded** para múltiplas conexões simultâneas
- **Interface de terminal (CLI)** funcional e intuitiva
- **Tratamento de concorrência** com locks thread-safe
- **Estrutura de código bem organizada** e completamente comentada
- **Instruções de execução** detalhadas

## 🚀 Como Executar

### Pré-requisitos
- Python 3.6 ou superior
- Sistema operacional: Windows, Linux ou macOS

### 1. Executar o Servidor

```bash
python server.py
```

O servidor será iniciado em `localhost:12345` e ficará aguardando conexões.

**Saída esperada:**
```
=== SERVIDOR DE CHAT DISTRIBUÍDO ===
Trabalho de Sistemas Distribuídos
Pressione Ctrl+C para parar o servidor

[SERVIDOR] Iniciado em localhost:12345
[SERVIDOR] Aguardando conexões...
```

### 2. Executar Clientes

Em terminais separados, execute múltiplos clientes:

```bash
python client.py
```

Cada cliente solicitará um nome de usuário único para fazer login.

## 📱 Como Usar o Cliente

### Menu Principal
Após fazer login, você verá o menu com as opções:

```
📱 CHAT DISTRIBUÍDO - MENU DE OPÇÕES
==================================================
1. 💬 Enviar mensagem privada
2. 👥 Criar grupo
3. 👥 Enviar mensagem para grupo
4. 📎 Enviar arquivo
5. 📋 Listar usuários online
6. 📋 Listar meus grupos
7. ➕ Adicionar membro ao grupo
8. 👥 Ver membros do grupo
9. ❓ Mostrar menu
10. 🚪 Sair
==================================================
```

### Comandos Detalhados

#### 1. 💬 Mensagem Privada
- Digite o nome do usuário destinatário
- Digite sua mensagem
- A mensagem aparecerá instantaneamente no cliente do destinatário

#### 2. 👥 Criar Grupo
- Digite o nome do grupo (deve ser único)
- Você se tornará automaticamente o primeiro membro do grupo
- Outros usuários podem ser adicionados posteriormente

#### 3. 👥 Mensagem para Grupo
- Digite o nome do grupo existente
- Digite sua mensagem
- Todos os membros do grupo receberão a mensagem
- **Importante:** Você deve ser membro do grupo para enviar mensagens
- **Se não for membro:** Peça para alguém te adicionar usando a opção 7

#### 4. 📎 Enviar Arquivo
- Escolha entre envio privado (1) ou para grupo (2)
- Digite o destinatário (usuário ou grupo)
- Digite o caminho completo do arquivo
- Formatos suportados: qualquer tipo de arquivo
- **Para grupos:** Você deve ser membro do grupo para enviar arquivos

#### 5. 📋 Listar Usuários
- Mostra todos os usuários conectados ao servidor
- Indica qual é você na lista

#### 6. 📋 Listar Meus Grupos
- Mostra apenas os grupos dos quais você faz parte
- Não mostra grupos em que você não é membro

#### 7. ➕ Adicionar Membro ao Grupo
- Digite o nome do grupo (você deve ser membro)
- Digite o nome do usuário para adicionar
- O usuário deve estar conectado no momento
- O usuário será notificado automaticamente sobre a adição

#### 8. 👥 Ver Membros do Grupo
- Digite o nome do grupo (você deve ser membro)
- Mostra lista completa de todos os membros
- Indica qual usuário é você na lista

#### 9. ❓ Mostrar Menu
- Reexibe o menu de opções completo

#### 10. 🚪 Sair
- Encerra o cliente de forma segura

## 📁 Sistema de Armazenamento de Arquivos

### Como o Servidor Salva os Arquivos

Quando um usuário envia um arquivo, o **servidor** faz uma cópia de segurança seguindo este padrão:

**Formato:** `{remetente}_{nome_original_do_arquivo}`

**Exemplos práticos:**
- Alice envia "documento.pdf" → servidor salva como `Alice_documento.pdf`
- Bob envia "foto.jpg" → servidor salva como `Bob_foto.jpg`
- Carlos envia "planilha.xlsx" → servidor salva como `Carlos_planilha.xlsx`

### Como o Cliente Salva os Arquivos Recebidos

Os **clientes** que recebem arquivos os salvam de forma diferente:

**Para mensagens privadas:** `{remetente}_{nome_original}`
- Exemplo: Alice recebe arquivo de Bob → salva como `Bob_documento.pdf`

**Para grupos:** `{nome_do_grupo}_{remetente}_{nome_original}`
- Exemplo: No grupo "Trabalho", Bob envia arquivo → Alice salva como `Trabalho_Bob_documento.pdf`

### Vantagens deste Sistema:
1. **Evita conflitos:** Nunca dois arquivos terão o mesmo nome
2. **Rastreabilidade:** Sempre sabemos quem enviou o arquivo
3. **Organização:** Fácil identificar origem dos arquivos
4. **Backup automático:** Servidor mantém cópia de tudo

## 🔧 Como Parar o Sistema

### Parar o Servidor
Para parar o servidor, há duas opções:

1. **Método recomendado:** Pressione `Ctrl+C` no terminal do servidor
   ```
   [SERVIDOR] Encerrando servidor...
   ```

2. **Fechamento forçado:** Feche o terminal (não recomendado)

### Parar o Cliente
Para sair do cliente:

1. **Pelo menu:** Digite `10` e pressione Enter
2. **Atalho:** Pressione `Ctrl+C` a qualquer momento
3. **EOF:** Pressione `Ctrl+D` (Linux/Mac) ou `Ctrl+Z` (Windows)

**Saída esperada:**
```
👋 Encerrando cliente...
✅ Cliente encerrado.
```

## 📁 Estrutura de Arquivos

Ao executar o sistema, os seguintes diretórios serão criados automaticamente:

```
projeto/
├── server.py              # Código do servidor (completamente comentado)
├── client.py              # Código do cliente (completamente comentado)
├── README.md              # Este arquivo
├── server_files/          # Arquivos recebidos pelo servidor
└── client_downloads/      # Arquivos baixados pelos clientes
```

### Arquivos Recebidos
- **Servidor:** Salva todos os arquivos em `server_files/` com prefixo do remetente
- **Cliente:** Salva arquivos recebidos em `client_downloads/` com prefixos identificadores

## 🧪 Testando o Sistema

### Teste Básico (2 Clientes)
1. Inicie o servidor
2. Abra 2 terminais e execute `python client.py` em cada um
3. Faça login com nomes diferentes (ex: "Alice" e "Bob")
4. Teste mensagem privada de Alice para Bob
5. Teste criação de grupo e mensagem em grupo

### Teste Avançado (5+ Clientes)
1. Inicie o servidor
2. Abra 5 terminais separados
3. Execute `python client.py` em cada terminal
4. Faça login com nomes únicos: "Alice", "Bob", "Carlos", "Diana", "Eduardo"

**Sequência de testes recomendada:**
```
1. Alice cria grupo "Trabalho"
2. Alice adiciona Bob e Carlos ao grupo "Trabalho"
3. Bob, Carlos e Alice enviam mensagens para o grupo
4. Diana cria grupo "Amigos" 
5. Diana adiciona Eduardo ao grupo "Amigos"
6. Eduardo envia mensagem privada para Alice
7. Alice envia arquivo PDF para o grupo "Trabalho"
8. Carlos envia arquivo para Diana (privado)
9. Todos listam usuários online simultaneamente
10. Alice e Diana verificam membros de seus respectivos grupos
```

### Exemplo de Fluxo Completo de Grupo:

**Terminal 1 (Alice):**
```
Alice> 2          # Criar grupo
Digite o nome do grupo: Trabalho
✅ Grupo "Trabalho" criado com sucesso

Alice> 7          # Adicionar membro
Digite o nome do grupo: Trabalho  
Digite o nome do usuário para adicionar: Bob
✅ Bob foi adicionado ao grupo Trabalho

Alice> 8          # Ver membros
Digite o nome do grupo: Trabalho
👥 Membros do grupo 'Trabalho' (2):
  1. Alice (você)
  2. Bob
```

**Terminal 2 (Bob) - tenta enviar mensagem SEM ser membro:**
```
Bob> 3            # Enviar mensagem para grupo
Digite o nome do grupo: Trabalho
Digite sua mensagem: Olá pessoal!
❌ Você não é membro do grupo Trabalho. Peça para alguém te adicionar.
```

**Terminal 1 (Alice) - adiciona Bob:**
```
Alice> 7          # Adicionar membro
Digite o nome do grupo: Trabalho  
Digite o nome do usuário para adicionar: Bob
✅ Bob foi adicionado ao grupo Trabalho
```

**Terminal 2 (Bob) - recebe notificação e agora pode enviar:**
```
🎉 Você foi adicionado ao grupo 'Trabalho' por Alice (14:30:25)

Bob> 3            # Enviar mensagem para grupo
Digite o nome do grupo: Trabalho
Digite sua mensagem: Olá pessoal do grupo!
✅ Mensagem enviada para 1 membros do grupo
```

**Terminal 1 (Alice) - recebe mensagem:**
```
👥 [GRUPO: Trabalho] Bob (14:30:45): Olá pessoal do grupo!
```

## 🔍 Monitoramento e Logs

### Logs do Servidor
O servidor mostra informações importantes no terminal:
```bash
[SERVIDOR] Iniciado em localhost:12345
[SERVIDOR] Aguardando conexões...
[SERVIDOR] Nova conexão de ('127.0.0.1', 54321)
[SERVIDOR] Usuário Alice conectado
[SERVIDOR] Usuário Bob conectado
[SERVIDOR] Usuário Alice desconectado
```

### Verificação de Arquivos
Para verificar se arquivos estão sendo salvos corretamente:

**No servidor:**
```bash
ls server_files/
# Exemplo de saída:
# Alice_documento.pdf  Bob_foto.jpg  Carlos_planilha.xlsx
```

**No cliente:**
```bash
ls client_downloads/
# Exemplo de saída:
# Bob_documento.pdf  Trabalho_Alice_apresentacao.pptx
```

## ⚡ Recursos Técnicos Implementados

### Concorrência e Threading
- **Servidor multithreaded:** Cada cliente conectado é gerenciado por uma thread separada
- **Locks thread-safe:** Uso de `threading.Lock()` para proteger estruturas de dados compartilhadas
- **Gerenciamento seguro:** Lista de clientes e grupos protegida contra race conditions

### Protocolo de Comunicação
- **Formato JSON:** Todas as mensagens são enviadas em formato JSON
- **Codificação UTF-8:** Suporte completo a caracteres especiais
- **Base64 para arquivos:** Arquivos são codificados em base64 para transmissão segura

### Tratamento de Erros
- **Desconexões abruptas:** Sistema detecta e remove clientes desconectados
- **Mensagens malformadas:** Validação de formato JSON
- **Usuários duplicados:** Impede login com username já em uso
- **Arquivos inexistentes:** Validação antes do envio

### Controle de Acesso
- **Grupos privados:** Apenas membros podem enviar mensagens e arquivos
- **Adição controlada:** Apenas membros podem adicionar outros usuários
- **Visibilidade limitada:** Apenas membros podem ver lista de participantes

## 🚨 Limitações Conhecidas

1. **Persistência:** Mensagens não são salvas quando usuários estão offline
2. **Tamanho de arquivos:** Limitado pelo buffer do socket (4096 bytes por vez)
3. **Autenticação:** Sistema simples sem senhas
4. **Criptografia:** Comunicação não criptografada
5. **Histórico:** Não mantém histórico de mensagens anteriores
6. **Remoção de membros:** Não implementado (apenas adição)

## 🔧 Possíveis Melhorias

### Curto Prazo:
- [ ] Persistência de mensagens offline
- [ ] Limite de tamanho para arquivos grandes
- [ ] Comando para sair de grupos
- [ ] Remoção de membros por administradores

### Longo Prazo:
- [ ] Interface gráfica (GUI)
- [ ] Autenticação com senhas
- [ ] Criptografia end-to-end
- [ ] Histórico de mensagens
- [ ] Notificações de status (online/offline)
- [ ] Transferência de arquivos por chunks

## 📞 Suporte e Debugging

### Problemas Comuns:

**1. "Conexão recusada"**
```
Solução: Verifique se o servidor está rodando antes de iniciar clientes
```

**2. "Usuário já em uso"**
```
Solução: Escolha um nome de usuário diferente
```

**3. "Arquivo não encontrado"**
```
Solução: Use o caminho completo do arquivo (ex: /home/user/documento.pdf)
```

**4. Cliente trava ou não responde**
```
Solução: Use Ctrl+C para forçar encerramento e reinicie
```

**5. "Você não é membro do grupo"**
```
Solução: Peça para um membro atual te adicionar usando opção 7
```

### Para Desenvolvedores:

**Debug do servidor:**
- Adicione mais prints na função `handle_client()` para rastrear mensagens
- Use `netstat -an | grep 12345` para verificar se a porta está ocupada
- Monitore os locks de grupo e cliente para problemas de concorrência

**Debug do cliente:**
- Monitore a função `listen_server()` para problemas de recepção
- Verifique permissões de escrita nas pastas de download
- Use o comando "9" frequentemente para ver o menu se esquecer os números

---

## 🎯 Conclusão

Este sistema implementa com sucesso todos os requisitos especificados para o trabalho de Sistemas Distribuídos:

### ✅ Funcionalidades Principais
- **Comunicação cliente-servidor via sockets TCP**
- **Mensagens privadas e em grupo em tempo real**  
- **Transferência de arquivos completa**
- **Concorrência com múltiplos clientes**
- **Interface CLI funcional**
- **Código completamente estruturado e comentado**

### ✅ Funcionalidades Avançadas
- **Gerenciamento completo de grupos**
- **Adição de membros com controle de acesso**
- **Listagem de membros por grupo**
- **Notificações automáticas**
- **Sistema de arquivos organizados**
- **Controle de membership rigoroso**

### ✅ Qualidade Técnica
- **Arquitetura bem definida**
- **Tratamento robusto de exceções**
- **Sincronização thread-safe**
- **Protocolo de comunicação estruturado**
- **Documentação completa**

O sistema está pronto para demonstração com 5+ clientes simultâneos conforme solicitado na especificação, incluindo todas as funcionalidades implementadas e documentadas.
