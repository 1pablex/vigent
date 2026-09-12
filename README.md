# Vigent

Plataforma de gestão de treinamentos corporativos obrigatórios — Projeto Final de Curso (PFC), Engenharia de Software, Universidade de Mogi das Cruzes.

## Sobre o projeto

O Vigent gerencia o ciclo de vida de treinamentos obrigatórios: atribuição de curso, percurso de conteúdo, avaliação de reação, prova de conhecimento e emissão de certificado, com trilha de auditoria.

## Status atual

O fluxo de treinamento está completo, de ponta a ponta:

- **Login e senha provisória** (RN-27) — bloqueio de acesso até a troca da senha no primeiro acesso
- **Conteúdo do curso** (RN-23) — percurso por slides, com trava de avanço sequencial
- **Avaliação de reação** (RN-06) — obrigatória antes da prova, não influencia a nota
- **Prova de conhecimento** (RN-09, RN-20) — questões em ordem fixa, histórico de tentativas preservado
- **Certificado** (RN-08, RN-21) — emissão automática após aprovação, com nota mínima e reação registrada como pré-requisitos, gravando a versão do curso vigente. Ainda não existe tela própria para visualizar ou baixar o certificado — hoje ele só é mencionado na tela de resultado da prova
- **Reciclagem** (RN-19) — reprovação após todas as tentativas reinicia o progresso do curso

O painel de conformidade do RH, a notificação automática de vencimento, a reciclagem em lote e a visualização/PDF do certificado ainda não foram implementados ficam para as próximas etapas.

## Stack

- Python 3.11 ou 3.12
- Django 5.2 (LTS)
- PostgreSQL (local em desenvolvimento; Supabase em produção)

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
4. Copie `.env.example` para `.env` e preencha `SECRET_KEY` e `DATABASE_URL`
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

O comando `carregar_dados_cursos` cria três treinamentos: **LGPD — Proteção de Dados** e **Código de Conduta Ética** (todos os departamentos), e **Parametrização de Sala Limpa** (restrito ao departamento Sala Limpa) cada um já com aulas, slides, prova e questões prontas para teste.

## Estrutura dos apps

| App | Responsabilidade |
|---|---|
| `contas` | Usuário, autenticação, departamentos |
| `treinamentos` | Cursos, aulas, slides, progresso |
| `avaliacoes` | Avaliação de reação e prova |
| `certificacao` | Certificados |
| `auditoria` | Logs, e-mails enviados, registros de acesso |
| `core` | Camada de regras de negócio (`services.py`), ponto de entrada pós-login e comandos de carga de dados |