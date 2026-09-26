# Vigent

Plataforma de gestão de treinamentos corporativos obrigatórios, Projeto Final de Curso (PFC), Engenharia de Software, Universidade de Mogi das Cruzes.

## Sobre o projeto

O Vigent gerencia o ciclo de vida de treinamentos obrigatórios: atribuição de curso, percurso de conteúdo, avaliação de reação, prova de conhecimento e emissão de certificado, com trilha de auditoria.

## Status atual

**Fluxo de treinamento**, completo de ponta a ponta:
- Login com autenticação em duas etapas (segundo fator por e-mail) em todo acesso, incluindo o primeiro; ao confirmar o código, quem ainda está com senha provisória é direcionado para a troca obrigatória antes de entrar no sistema.
- Aceite obrigatório da política de privacidade após a primeira troca de senha, com a política também acessível a qualquer momento a partir do login e das telas internas.
- Conteúdo do curso, com trava de avanço sequencial pelos slides.
- Avaliação de reação, obrigatória antes da prova.
- Prova de conhecimento, com histórico de tentativas e reciclagem após reprovações repetidas.
- Conclusão do curso registrada automaticamente na aprovação (nota mínima atingida); a tela para visualizar ou imprimir o certificado ainda não foi construída.

**Painel do RH:**
- Cadastro de colaborador, com matrícula automática e envio de credenciais por e-mail.
- Listagem de colaboradores, com busca e filtro por departamento.
- Registros e auditoria: logs do sistema, execuções de rotina, e-mails enviados e histórico de acesso, todos com paginação e filtro.
- Painel de conformidade: indicadores agregados (em dia, vencendo, vencido, pendente), conformidade por departamento, qualidade percebida (nota média da prova e da avaliação de reação), rotina de notificação de vencimento disparável manualmente e solicitação de reciclagem para treinamentos vencidos.

**Segurança:**
- Hash de senha com Argon2 (migração progressiva: contas antigas em PBKDF2 são atualizadas sozinhas no próximo login bem-sucedido).
- Autenticação em duas etapas (código de 6 dígitos, válido por 5 minutos, enviado por e-mail) em todo login, sem exceção.
- Senha provisória de uso único: deixa de valer assim que o colaborador define a senha definitiva.
- Bloqueio temporário após tentativas de login malsucedidas repetidas.
- Toda verificação de permissão ocorre no back-end, nunca só ocultando elemento na tela.
- `DEBUG` e `ALLOWED_HOSTS` controlados por variável de ambiente, nunca fixos no código.

**Pendente:** tela para visualizar e imprimir o certificado, tela de "meus dados" para o colaborador.

## Stack

- Python 3.11 ou 3.12
- Django 5.2 (LTS)
- PostgreSQL (local em desenvolvimento; Supabase em produção)
- Argon2 (`argon2-cffi`): hash de senha
- Brevo (`brevo-python`): envio de e-mail transacional via API REST, não SMTP (credenciais de primeiro acesso, código de autenticação em duas etapas, notificações)

## Como rodar localmente

1. Clone o repositório e entre na pasta
2. Crie e ative um ambiente virtual:
   ```
   python -m venv venv
   venv\Scripts\activate       # Windows
   source venv/bin/activate    # Mac/Linux
   ```
3. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
4. Copie `.env.example` para `.env` e preencha `SECRET_KEY`, `DATABASE_URL` e `BREVO_API_KEY`
5. Rode as migrações:
   ```
   python manage.py migrate
   ```
6. Popule o banco com dados de demonstração (opcional, recomendado):
   ```
   python manage.py carregar_dados_colaboradores
   python manage.py carregar_dados_cursos
   ```
7. Suba o servidor:
   ```
   python manage.py runserver
   ```
8. Acesse `http://127.0.0.1:8000/`

## Contas de demonstração

Criadas pelo comando `carregar_dados_colaboradores`:

| Papel | E-mail | Senha |
|---|---|---|
| RH | ricardo.lima@nortex.com.br | 123456 |
| Colaboradora (Vendas) | fernanda.lima@nortex.com.br | 123456 |
| Primeiro acesso (Sala Limpa) | bruno.tavares@nortex.com.br | Nortex@2026 |

O comando `carregar_dados_cursos` cria três treinamentos: **LGPD (Proteção de Dados)** e **Código de Conduta Ética** (todos os departamentos), e **Parametrização de Sala Limpa** (restrito ao departamento Sala Limpa), cada um já com aulas, slides, prova e questões prontas para teste.

## Estrutura dos apps

| App | Responsabilidade |
|---|---|
| `contas` | Usuário, autenticação, autenticação em duas etapas, departamentos |
| `treinamentos` | Cursos, aulas, slides, progresso |
| `avaliacoes` | Avaliação de reação e prova |
| `certificacao` | Certificados |
| `auditoria` | Logs, e-mails enviados, registros de acesso, execuções de rotina |
| `core` | Camada de regras de negócio (`services.py`), envio de e-mail via Brevo (`correio.py`), ponto de entrada pós-login, comandos de carga de dados e as telas do painel do RH |
