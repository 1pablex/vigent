# Vigent

Plataforma de gestão de treinamentos corporativos obrigatórios, Projeto Final de Curso (PFC), Engenharia de Software, Universidade de Mogi das Cruzes.

## Sobre o projeto

O Vigent gerencia o ciclo de vida de treinamentos obrigatórios: vinculação automática de cursos por departamento, percurso de conteúdo, avaliação de reação, prova de conhecimento e emissão de certificado, com trilha de auditoria e dashboard de indicadores para o RH.

## Status atual

**Fluxo de treinamento**, completo de ponta a ponta:
- Login com autenticação em duas etapas (segundo fator por e-mail); no primeiro acesso com senha provisória, o 2FA é dispensado (o código chegaria pelo mesmo e-mail que já entregou a credencial) e o colaborador vai direto para a troca obrigatória de senha
- Aceite obrigatório do termo de uso após a primeira troca de senha, com política de privacidade acessível a partir da tela de login
- Cursos vinculados ao colaborador pelo departamento: ao mudar de setor, ele passa a ver automaticamente os cursos do novo departamento, sem ação manual do RH
- Conteúdo do curso, com trava de avanço sequencial pelos slides
- Avaliação de reação, obrigatória antes da prova
- Prova de conhecimento, com histórico de tentativas e reciclagem após reprovações repetidas
- Conclusão do curso registrada automaticamente na aprovação (nota mínima atingida), com emissão do certificado
- Meus certificados: lista dos certificados emitidos, com situação (em dia, vencendo, vencido) e tela para visualizar e imprimir o certificado
- Meus dados: consulta, somente leitura, de nome, matrícula, data de cadastro, cargo e setor

**Painel do RH:**
- Cadastro de colaborador, com matrícula automática e envio de credenciais por e-mail
- Listagem de colaboradores, com busca, filtro por departamento e paginação de 10 por página
- Gestão de cursos: dados do curso, departamentos atendidos, aulas, slides e questões da prova. Slides e questões são cadastrados um por vez, cada um na sua tela, a partir de uma lista compacta
- Remoção de colaborador: desliga a conta e pseudonimiza nome e e-mail (`colab<matrícula>`); os dados originais ficam num cofre de reidentificação por 90 dias e depois são excluídos. Certificados e histórico de treinamento são mantidos
- Registros e auditoria: logs do sistema, execuções de rotina, e-mails enviados e histórico de acesso, todos com paginação e filtro
- Painel de conformidade: matriz colaborador × treinamento com busca e filtro por situação, indicadores agregados (em dia, vencendo, vencido, pendente), conformidade por departamento, qualidade percebida, rotinas de notificação de vencimento e de expurgo do cofre disparáveis manualmente e solicitação de reciclagem para treinamentos vencidos
- **Dashboard de indicadores** (aba que substituiu "Atribuições"): índice de conformidade geral comparado com a meta de 90%, conformidade por departamento e por curso, vencimentos previstos em faixas de 0 a 30, 31 a 60 e 61 a 90 dias, qualidade percebida e avaliação de reação por curso (didática e entendimento, com todo o histórico). Os números vêm da API REST descrita abaixo

**Segurança:**
- Hash de senha com Argon2 (migração progressiva: contas antigas em PBKDF2 são atualizadas sozinhas no próximo login bem-sucedido)
- Autenticação em duas etapas (código de 6 dígitos, válido por 5 minutos, enviado por e-mail) em todo login com senha já definida. Um novo código, de login ou de "Esqueci minha senha", só pode ser pedido 5 minutos depois do anterior, o que evita inundar o e-mail do colaborador e gastar a cota do Brevo. Na redefinição, a resposta é a mesma para qualquer e-mail, sem revelar quem é cadastrado
- Senha provisória de uso único: deixa de valer assim que o colaborador define a senha definitiva
- Bloqueio temporário após tentativas de login malsucedidas repetidas, por e-mail e por IP. O IP vem da conexão; o cabeçalho `X-Forwarded-For` só é lido quando há proxy confiável na frente da aplicação (`PROXIES_CONFIAVEIS`), e mesmo assim só o trecho escrito pelo proxy. Assim o cliente não consegue trocar de IP a cada tentativa para escapar do bloqueio
- Sessão única por conta (RNF-13): um novo login em outro computador encerra a sessão anterior, que volta ao login com um aviso e fica registrada na auditoria. O progresso do curso fica salvo no banco, então o colaborador continua do slide onde parou
- A sessão expira ao fechar o navegador e após 30 minutos sem uso (RNF-12); cada acesso renova o prazo
- Toda verificação de permissão ocorre no back-end, nunca só ocultando elemento na tela; na API, quem não é RH recebe 403 em JSON
- Entradas validadas no back-end: departamento e grupo do cadastro são conferidos antes de criar a conta (nenhum e-mail sai com dado inválido), e parâmetros inválidos na URL das listagens não geram erro 500
- Upload de imagens dos cursos (capa e slides, RN-40): só JPG, PNG ou WEBP, identificados pelo conteúdo e não pela extensão, com no máximo 5 MB e 25 megapixels. A imagem aceita é regravada a partir dos pixels, com nome aleatório: conteúdo escondido no arquivo (script anexado) e metadados EXIF/GPS são descartados. Vale para o painel do RH e para o admin
- Texto dos slides sanitizado com `nh3` ao salvar e de novo na exibição: só parágrafo, lista, negrito, itálico e quebra de linha; scripts e atributos como `onerror` são removidos
- `DEBUG` e `ALLOWED_HOSTS` controlados por variável de ambiente, nunca fixos no código
- LGPD: pseudonimização no desligamento, expurgo dos dados originais após 90 dias (comando `expurgar_reidentificacoes`) e registros de remoção e expurgo na auditoria sem o nome real do colaborador

**Pendente:** agendamento automático (cron) das rotinas `verificar_vencimentos` e `expurgar_reidentificacoes`; hoje elas rodam pelo botão do painel de conformidade ou pelo terminal.

**Evoluções previstas:**
- Atribuição individual de curso como exceção à regra do departamento (onboarding, reciclagem pontual, curso de outro setor). A estrutura de dados (`AtribuicaoManual`) foi mantida no banco, desativada, como base para essa feature
## Arquitetura: telas em HTML e dados em JSON

O Vigent usa dois tipos de endpoint, cada um com uma responsabilidade:

| Tipo | Devolve | Implementação | Exemplos |
|---|---|---|---|
| Telas | HTML | views do Django + templates, renderizadas no servidor | login, cursos, prova, conformidade, a página do dashboard |
| Dados | JSON | Django REST Framework, em `/api/v1/` | indicadores consumidos pelos gráficos do dashboard |

As telas continuam renderizadas pelo Django, que já resolve formulários, CSRF, mensagens e redirecionamentos. Só o que é consumido por JavaScript vira API. A regra para novos endpoints é: **todo endpoint que devolve JSON passa pelo DRF, dentro de `/api/v1/`**.

A API usa a mesma sessão do login (com 2FA): não existe uma segunda forma de autenticação. Todo endpoint exige o grupo RH por padrão (`core.api.permissions.SomenteRH`), é somente leitura (GET) e tem limite de 120 requisições por minuto por usuário.

## Endpoints

### API REST (JSON), somente RH

| Método | Rota | Indicador |
|---|---|---|
| GET | `/api/v1/indicadores/conformidade/` | Índice de conformidade geral, meta e contagem por situação |
| GET | `/api/v1/indicadores/conformidade/departamentos/` | Índice por departamento, do pior para o melhor |
| GET | `/api/v1/indicadores/conformidade/cursos/` | Índice por curso, do gargalo para o melhor |
| GET | `/api/v1/indicadores/vencimentos/` | Certificados que vencem em 0 a 30, 31 a 60 e 61 a 90 dias |
| GET | `/api/v1/indicadores/reacao/` | Médias de didática e de entendimento por curso (histórico) |
| GET | `/api/v1/indicadores/qualidade/` | Taxa de conclusão, nota média da prova e média da reação |
| GET | `/api/v1/schema/` | Especificação OpenAPI 3 gerada a partir do código |
| GET | `/api/v1/docs/` | Documentação interativa (Swagger UI) |

Índice de conformidade = (em dia + vencendo) ÷ total de pares colaborador ativo × curso exigido pelo setor.

Exemplo de resposta de `/api/v1/indicadores/conformidade/`:
```json
{"percentual": 50, "meta": 90, "total": 4, "em_dia": 1, "vencendo": 1, "vencido": 1, "pendente": 1}
```

### Telas (HTML)

| Rota | Tela | Acesso |
|---|---|---|
| `/conta/entrar/`, `/conta/verificar-codigo/` | Login e segundo fator | Público |
| `/conta/esqueci-senha/`, `/conta/redefinir-senha/` | Recuperação de senha | Público |
| `/conta/politica-privacidade/` | Política de privacidade | Público |
| `/conta/definir-senha/`, `/conta/aceitar-termo/` | Primeiro acesso | Autenticado |
| `/conta/meus-dados/` | Meus dados | Autenticado |
| `/treinamentos/` | Meus treinamentos | Autenticado |
| `/treinamentos/curso/<id>/abrir/`, `/treinamentos/curso/<id>/` | Percurso do curso | Colaborador do setor |
| `/avaliacoes/curso/<id>/reacao/`, `/avaliacoes/curso/<id>/prova/` | Reação e prova | Colaborador do setor |
| `/certificados/meus/`, `/certificados/<id>/` | Certificados | Dono do certificado |
| `/rh/dashboard/` | Dashboard de indicadores | RH |
| `/rh/conformidade/` | Painel de conformidade | RH |
| `/rh/reciclagem/<usuario>/<curso>/` | Solicitar reciclagem (POST) | RH |
| `/rh/colaboradores/`, `/conta/colaboradores/novo/` | Colaboradores e cadastro | RH |
| `/rh/colaboradores/<id>/remover/` | Desligamento (POST) | RH |
| `/rh/auditoria/` | Registros e auditoria | RH |
| `/rh/cursos/...` | Gestão de cursos, aulas e questões | RH |

## Stack

- Python 3.11 ou 3.12
- Django 5.2 (LTS)
- Django REST Framework 3.16: API de indicadores em JSON
- drf-spectacular 0.28: especificação OpenAPI 3 e Swagger UI
- PostgreSQL (local em desenvolvimento; Supabase em produção)
- Argon2 (`argon2-cffi`): hash de senha
- Brevo (`brevo-python`): envio de e-mail transacional via API REST, não SMTP (credenciais de primeiro acesso e código de autenticação em duas etapas)

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
4. Copie `.env.example` para `.env` e preencha `SECRET_KEY`, `DATABASE_URL`, `BREVO_API_KEY`, `BREVO_SMTP_USER`, `BREVO_SMTP_PASSWORD` e `DEFAULT_FROM_EMAIL`. Em desenvolvimento local mantenha `DEBUG=True`; em produção defina `DEBUG=False` e liste os domínios liberados em `ALLOWED_HOSTS`
5. Rode as migrações:
   ```
   python manage.py migrate
   ```
6. Popule o banco com dados de demonstração (opcional, recomendado):
   ```
   python manage.py carregar_dados_colaboradores
   python manage.py carregar_dados_cursos
   ```
   Para ver o dashboard com volume de dados, há também uma base grande de colaboradores fictícios (detalhes em "Contas de demonstração"):
   ```
   python manage.py carregar_dados_demonstracao
   ```
7. Suba o servidor:
   ```
   python manage.py runserver
   ```
8. Acesse `http://127.0.0.1:8000/`. Com o RH logado, a documentação da API fica em `http://127.0.0.1:8000/api/v1/docs/`

## Testes

São 226 testes automatizados (Django `TestCase` e `SimpleTestCase`). Para rodar todos:
```
python manage.py test
```
Com cobertura:
```
coverage run manage.py test
coverage report
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| `core/tests.py` | 26 | Regras de negócio de `services.py` com banco (RN-02, RN-04 a RN-09, RN-13, RN-14, RN-29, RN-34) |
| `core/test_services_unitarios.py` | 12 | Unitários sem banco: emissão de certificado, índice de conformidade (RN-38), faixas de vencimento (RN-39) |
| `core/test_api_indicadores.py` | 19 | API de indicadores: acesso, contrato JSON, reação histórica (RN-30), reciclagem atômica, número de consultas, tela do dashboard |
| `core/test_seguranca_endpoints.py` | 29 | Autenticação, perfil, IDOR, CSRF, XSS, upload, redirecionamento aberto, cabeçalhos, parâmetros inválidos na URL. Toda rota nova precisa ser classificada aqui |
| `core/test_seed_cursos.py` | 4 | Carga de cursos: mesmo conteúdo e departamentos do arquivo versionado, uma alternativa correta por questão, imagens regravadas (RN-40) e repetição sem duplicar |
| `core/test_seed_demonstracao.py` | 7 | Seed de demonstração: volume e mistura de situações, perfis por departamento, repetição sem duplicar, limpeza, bloqueio sem `DEBUG` e e-mail `.invalid` que não sai pelo Brevo |
| `core/test_integracao_rh.py` | 13 | Painel do RH: conformidade, rotinas, reciclagem, paginação de colaboradores e do painel de conformidade |
| `contas/tests.py` | 11 | Usuário, matrícula, normalização de e-mail, código de verificação |
| `contas/test_integracao_cadastro.py` | 8 | Cadastro de colaborador, com departamento e grupo validados |
| `contas/test_integracao_codigo.py` | 12 | Segundo fator e redefinição de senha: limite de tentativas (RN-25) e intervalo de 5 minutos entre códigos |
| `contas/test_sessao_unica.py` | 10 | Sessão única por conta (novo login em outro computador encerra a sessão anterior) e expiração após 30 minutos sem uso ou ao fechar o navegador |
| `contas/test_rede.py` | 11 | IP de origem: `X-Forwarded-For` ignorado sem proxy confiável, leitura do trecho escrito pelo proxy, IP inválido descartado |
| `treinamentos/tests.py` | 5 | Models de curso, aula, slide e progresso |
| `treinamentos/test_integracao_gestao_cursos.py` | 24 | Gestão de cursos pelo RH: curso, aula, slides um por vez e questões |
| `treinamentos/test_upload_seguro.py` | 14 | Upload de imagens e texto dos slides (RN-40): formatos, limites, arquivo poliglota, EXIF, nome aleatório, sanitização |
| `avaliacoes/test_integracao.py` | 10 | Avaliação de reação e prova |
| `certificacao/tests.py` | 3 | Situação do certificado |
| `certificacao/test_integracao.py` | 4 | Meus certificados e acesso ao certificado |
| `certificacao/test_rotina_vencimentos.py` | 4 | Rotina de notificação de vencimento (RN-11, RN-12) |

Os testes comentados com "Corrigido:" em `test_seguranca_endpoints.py` nasceram documentando uma vulnerabilidade conhecida e passaram a valer quando a correção entrou. Hoje não há vulnerabilidade conhecida em aberto.

## Contas de demonstração

Criadas pelo comando `carregar_dados_colaboradores`:

| Papel | E-mail | Senha |
|---|---|---|
| RH (Recursos Humanos) | ricardo.lima@nortex.com.br | 123456 |
| Colaboradora (Vendas) | fernanda.lima@nortex.com.br | 123456 |
| Primeiro acesso (Sala Limpa) | bruno.tavares@nortex.com.br | Nortex@2026 |

O comando `carregar_dados_cursos` cria quatro treinamentos, cada um com capa, aulas, slides com imagem, prova e questões:

| Curso | Departamentos |
|---|---|
| Abertura de chamados | Todos |
| Compliance e codigo de conduta | Todos |
| Prevenção a fraude | Financeiro |
| Recrutamento e seleção sem discriminação | Recursos Humanos |

O conteúdo fica versionado em `core/dados/cursos/` (`cursos.json` e a pasta `imagens/`). As imagens passam pela mesma validação e regravação do upload pelo RH (RN-40) e são salvas pelo storage do Django, então em produção vão para o storage configurado. Rodar o comando de novo não duplica: curso que já existe é pulado.

Para transformar cursos cadastrados pela tela do RH em carga de dados, exporte-os pelos ids (sem ids, exporta todos). O comando reescreve `core/dados/cursos/`:
```
python manage.py exportar_cursos 5 6 7 8
```

O comando `carregar_dados_demonstracao` cria uma base grande para o dashboard de indicadores (ele já roda os dois comandos acima):

- 60 colaboradores fictícios em 5 departamentos (Vendas, Financeiro, TI, Operações e Sala Limpa), com treinamentos em dia, vencendo, vencidos e pendentes
- Cada departamento tem um perfil: Vendas fica acima da meta de 90% e Sala Limpa fica crítico, para os gráficos terem contraste
- Quem tem certificado também tem progresso nas aulas, avaliação de reação e tentativas de prova, então todos os indicadores são preenchidos
- O sorteio usa semente fixa: os números são os mesmos a cada execução. Rodar de novo recria a base, e `--limpar` remove só esses colaboradores
- Login de qualquer um deles: `nome.sobrenome@exemplo.invalid` (sem acento), senha `123456`
- Proteções: o comando só roda com `DEBUG=True`, para nunca popular o banco de produção, e e-mails para o domínio reservado `.invalid` ficam registrados na auditoria mas não são enviados pelo Brevo

## Estrutura dos apps

| App | Responsabilidade |
|---|---|
| `contas` | Usuário, autenticação, autenticação em duas etapas, departamentos |
| `treinamentos` | Cursos, aulas, slides, progresso, vínculo de curso por departamento |
| `avaliacoes` | Avaliação de reação e prova |
| `certificacao` | Certificados |
| `auditoria` | Logs, e-mails enviados, registros de acesso, execuções de rotina |
| `core` | Camada de regras de negócio (`services.py`), API de indicadores (`core/api/`), envio de e-mail via Brevo (`correio.py`), ponto de entrada pós-login, comandos de carga de dados e as telas do painel do RH |
