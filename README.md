# Vigent

Plataforma de gestão de treinamentos corporativos. Projeto Final de Curso (PFC), Engenharia de Software, Universidade de Mogi das Cruzes.

## Sobre o projeto

O Vigent gerencia o ciclo de vida de treinamentos obrigatórios: atribuição de curso, percurso de conteúdo, avaliação de reação, prova de conhecimento e emissão de certificado, com trilha de auditoria.

## Status atual ( em desenvolvimento para a entrega do dia 14/09/2026)

Este repositório está em desenvolvimento. 

- **Banco de dados**: campo `senha_provisoria` no model `Usuario`
- **Back-end**: `SenhaProvisoriaMiddleware` intercepta toda requisição enquanto a senha não for trocada; a view `definir_senha` processa a troca
- **Front-end**: tela de login e tela de definição de senha
- **Avaliação de reação** (RN-06) — obrigatória antes da prova, não influencia a nota
- **Prova de conhecimento** (RN-09, RN-20) — questões em ordem fixa, histórico de tentativas preservado

Falta:
O restante do fluxo (conteúdo do curso, avaliação de reação, prova, certificado) já tem a lógica de back-end escrita, falta conectar os templates.

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

## Estrutura dos apps

| App | Responsabilidade |
|---|---|
| `contas` | Usuário, autenticação, departamentos |
| `treinamentos` | Cursos, aulas, slides, progresso |
| `avaliacoes` | Avaliação de reação e prova |
| `certificacao` | Certificados |
| `auditoria` | Logs, e-mails enviados, registros de acesso |
| `relatorios` | Camada de regras de negócio (`services.py`) e ponto de entrada pós-login |
