# Sistema Web de Estoque e Rastreabilidade de Camarões

Aplicação web desenvolvida como parte do Trabalho de Conclusão de Curso em Sistemas de Informação de Eliseu Ferreira Martins.

## Sobre o TCC

O projeto propõe um sistema web para controle de estoque e rastreabilidade de camarões em frigoríficos e pequenos empreendimentos. A proposta surgiu da experiência do autor na administração de barcos e na venda de camarões, além de relatos de compradores que enfrentaram perdas por dificuldades no controle de estoque.

O sistema organiza lotes, procedência, câmaras frigoríficas e movimentações. Seu foco é oferecer uma ferramenta simples para apoiar pequenos empreendedores na consulta e acompanhamento do histórico de cada lote.

**Título de trabalho:** Desenvolvimento de um sistema web para controle de estoque e rastreabilidade de camarões em frigoríficos.

## Funcionalidades

- Cadastro de contas independentes por estabelecimento.
- Acesso com e-mail e senha, login com Google e recuperação de senha por e-mail.
- Cadastro, edição, ativação, desativação e exclusão de câmaras.
- Cadastro de lotes com classificação, apresentação, origem, procedência, validade e câmara.
- Registro de entradas, saídas e descartes.
- Bloqueio de saídas e descartes acima do saldo disponível.
- Exigência do motivo para registrar um descarte.
- Consulta do saldo e do histórico de movimentações por lote.
- Edição de dados do lote sem alterar seu peso ou câmara, preservando o histórico.
- Preferências de tema e cor de destaque.

A exclusão de um lote remove também suas movimentações. A exclusão de uma câmara remove os lotes vinculados e seus históricos. O sistema apresenta uma confirmação antes dessas ações, que são permanentes.

## Tecnologias e serviços

| Componente               | Tecnologia ou serviço             | Uso                                      |
| ------------------------ | --------------------------------- | ---------------------------------------- |
| Backend                  | Python e Flask                    | Regras de negócio e páginas web          |
| Interface                | HTML, CSS, JavaScript e Bootstrap | Formulários e layout responsivo          |
| Banco de dados local     | SQLite                            | Desenvolvimento no computador            |
| Banco de dados hospedado | PostgreSQL no Neon                | Dados da versão publicada                |
| Hospedagem da aplicação  | Render                            | Disponibilização do sistema na internet  |
| E-mail transacional      | Brevo                             | Envio de links para redefinição de senha |
| Login Google             | Google OAuth 2.0                  | Autenticação com conta Google            |
| Controle de versão       | Git e GitHub                      | Histórico e armazenamento do código      |

## Como usar o sistema

### 1. Criar uma conta ou entrar

Acesse o site e cadastre-se com nome, e-mail e senha. Cada cadastro cria uma conta de estabelecimento com dados separados dos demais. Também é possível entrar com Google depois de vincular uma conta com o mesmo e-mail.

### 2. Cadastrar as câmaras

No menu, acesse **Câmaras**, informe a identificação do local de armazenamento e, se necessário, uma descrição. As câmaras podem ser editadas, ativadas ou desativadas.

### 3. Cadastrar um lote

Acesse **Estoque** e escolha **Cadastrar lote**. Preencha o código, a classificação, a apresentação, a quantidade inicial, a data de entrada, a validade opcional e a câmara.

Selecione a origem:

- **Mar:** informe a embarcação ou o atravessador.
- **Viveiro:** informe a fazenda ou o produtor e o local de origem.

A quantidade inicial também é registrada como a primeira entrada do histórico.

### 4. Consultar estoque e rastreabilidade

Na página **Estoque**, consulte os lotes e use os filtros para localizar registros. Abra um lote para ver sua procedência, validade, câmara atual, saldo disponível e histórico de movimentações.

As quantidades são exibidas no padrão brasileiro, com ponto para milhares e vírgula para decimais.

### 5. Registrar uma entrada ou saída

Nos detalhes do lote, escolha **Entrada** ou **Registrar saída**. Informe a quantidade, a data e o horário e, se desejar, observações. O sistema calcula o saldo pelas movimentações e impede que uma saída ultrapasse a quantidade disponível.

### 6. Registrar um descarte

Escolha **Registrar descarte**, informe a quantidade e descreva o motivo nas observações. O descarte pode ser registrado independentemente da validade, desde que haja saldo disponível. Não é permitido descartar mais do que o saldo do lote.

### 7. Editar ou excluir um lote

Nos detalhes do lote, escolha **Editar lote** para corrigir seus dados. A quantidade e a câmara não são editadas nessa tela, pois fazem parte do controle de movimentações.

Para excluir, escolha **Excluir lote** e confirme. O lote e todo o seu histórico serão removidos permanentemente.

### 8. Excluir uma câmara

Na página **Câmaras**, escolha **Excluir**. Se houver lotes relacionados, a confirmação informa quantos serão afetados. Ao confirmar, a câmara, seus lotes e as movimentações correspondentes serão removidos permanentemente.

## Executar localmente no Windows PowerShell

Abra o PowerShell na pasta do projeto. Se ainda não existir um ambiente virtual, crie-o e instale as dependências:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Crie o arquivo local de configuração:

```powershell
Copy-Item .env.example .env
```

Abra `.env` e ajuste as configurações necessárias. O arquivo `.env` é local e não deve ser enviado ao GitHub.

Aplique as migrações e inicie o sistema:

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe -m flask --app run.py run --debug
```

Abra `http://127.0.0.1:5000` no navegador.

Sem `DATABASE_URL`, o ambiente local usa SQLite. Para usar PostgreSQL localmente, configure a cadeia de conexão do Neon em `DATABASE_URL`.

## Configurações dos serviços

### Neon — banco de dados

Crie um projeto PostgreSQL no Neon e use a cadeia de conexão fornecida pelo serviço como valor de `DATABASE_URL`. Na publicação, configure essa variável no painel do Render. Não publique a senha do banco nem a cadeia de conexão em arquivos versionados.

### Render — hospedagem

O Render hospeda a aplicação. Configure:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `flask --app run.py db upgrade && gunicorn --bind 0.0.0.0:$PORT run:app`

Configure no ambiente do serviço as variáveis necessárias, incluindo `APP_ENV`, `SECRET_KEY`, `DATABASE_URL` e `PUBLIC_BASE_URL`. Use `APP_ENV=production` e o endereço HTTPS público do sistema em `PUBLIC_BASE_URL`.

### Brevo — recuperação de senha

Na hospedagem, o envio de e-mails usa a API do Brevo. Configure `EMAIL_PROVIDER=BREVO`, `BREVO_API_KEY`, `MAIL_DEFAULT_SENDER` e `MAIL_SENDER_NAME`. O endereço remetente precisa estar cadastrado e verificado no Brevo.

Para desenvolvimento local com SMTP, configure `EMAIL_PROVIDER=SMTP` e as variáveis `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD` e `MAIL_DEFAULT_SENDER`.

### Google — login

Crie no Google Cloud um cliente OAuth do tipo **Aplicativo da Web**. Configure como origem autorizada o endereço local `http://127.0.0.1:5000` e, em produção, o endereço HTTPS do site. Informe o Client ID em `GOOGLE_CLIENT_ID`.

## Segurança e dados de configuração

- Não envie `.env`, senhas, chaves de API ou cadeias de conexão ao GitHub.
- `SECRET_KEY` deve ser longa e diferente no ambiente de produção.
- O SQLite é destinado ao desenvolvimento local; a versão hospedada utiliza PostgreSQL.
- As migrações do banco já acompanham o projeto. Para aplicá-las, use `flask --app run.py db upgrade`.
- As políticas e limites dos planos de hospedagem podem mudar; consulte os provedores antes de depender de um plano gratuito.

## Testes

Para executar os testes automatizados, use na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
