# Sistema de estoque e rastreabilidade de camarões

Aplicação web em Flask para organizar lotes, procedência, câmaras e movimentações de estoque em pequenos empreendimentos. Cada cadastro cria uma conta de estabelecimento com os dados isolados dos demais.

## Tecnologias

- Python e Flask
- Flask-SQLAlchemy e PostgreSQL
- Flask-Login para sessões autenticadas
- Flask-WTF para proteção CSRF
- Bootstrap 5.3 para a base responsiva da interface

## Preparação local no Windows PowerShell

1. Entre na pasta `webapp`.
2. Crie e ative um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Crie o arquivo local de configuração e defina uma chave secreta:

   ```powershell
   Copy-Item .env.example .env
   ```

   Troque `SECRET_KEY` por uma chave aleatória longa. Sem `DATABASE_URL`, a aplicação usa SQLite apenas para desenvolvimento local. Para conectar PostgreSQL, configure `DATABASE_URL` no formato `postgresql+psycopg://...` no arquivo `.env`. Preencha também as variáveis `MAIL_*` com os dados SMTP e `GOOGLE_CLIENT_ID` com o Client ID Web do Google, se desejar ativar o botão Google. Não compartilhe o arquivo `.env`.

5. Crie as tabelas do banco usando as migrações que já acompanham o projeto:

   ```powershell
   flask --app run.py db upgrade
   ```

6. Inclua as classificações e apresentações iniciais e crie o administrador:

   ```powershell
   flask --app run.py seed-catalogs
   flask --app run.py create-admin
   ```

7. Execute a aplicação local:

   ```powershell
   flask --app run.py run --debug
   ```

   Abra `http://127.0.0.1:5000` no navegador.

O cadastro público cria um estabelecimento isolado, um usuário responsável e os catálogos padrão. A redefinição de senha envia um link assinado, temporário e invalidado depois da troca de senha. O link é montado com `PUBLIC_BASE_URL`; use o endereço HTTPS público ao publicar a aplicação. Sem SMTP configurado, os e-mails de recuperação não serão entregues.

O Google Sign-In é opcional. Crie no Google Cloud um Client ID OAuth para aplicativo Web, inclua a origem local autorizada (`http://127.0.0.1:5000`) e informe o Client ID em `GOOGLE_CLIENT_ID`. O usuário cria primeiro a conta pelo formulário de cadastro; no primeiro acesso Google com o mesmo e-mail verificado, a conta é vinculada. O backend verifica a assinatura e a audiência do token antes de iniciar a sessão. Em produção, cadastre a origem HTTPS real.

## Publicação para demonstração externa

O notebook serve apenas para desenvolvimento local. Para o orientador acessar pela internet, publique a aplicação Flask e conecte-a a um PostgreSQL hospedado; não exponha o banco diretamente. Uma opção gratuita para demonstração é Render (aplicação), Neon (PostgreSQL) e Brevo (e-mail via HTTPS). A aplicação seleciona `EMAIL_PROVIDER=BREVO` no ambiente hospedado; o envio local continua podendo usar SMTP.

No Render, use `pip install -r requirements.txt` como comando de build e `flask --app run.py db upgrade && gunicorn --bind 0.0.0.0:$PORT run:app` como comando de inicialização. Configure as variáveis `APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `EMAIL_PROVIDER=BREVO`, `BREVO_API_KEY`, `MAIL_DEFAULT_SENDER` e `MAIL_SENDER_NAME`. Cadastre a URL HTTPS da aplicação como origem JavaScript autorizada no cliente Google. Nunca publique `.env` nem coloque chaves em GitHub.

O Render gratuito desliga o serviço web após 15 minutos sem tráfego e pode levar cerca de um minuto para voltar. O sistema de arquivos gratuito é temporário, portanto o SQLite local não deve ser usado na nuvem. O Neon Free suspende o compute após 5 minutos sem consultas, mas reativa no próximo acesso; o limite gratuito inclui horas de compute e armazenamento finitos. A conta gratuita do Brevo limita o envio diário e exige remetente verificado. Consulte as limitações atuais antes de publicar.

Para atualizar uma instalação existente com a migração de isolamento, faça primeiro uma cópia do banco de dados e depois execute `flask --app run.py db upgrade`. Os dados existentes serão associados ao estabelecimento legado criado pela migração.

As migrações já estão incluídas no projeto. Não execute `flask db init` ao abrir este ZIP. Esse comando só é necessário ao criar uma pasta de migrações do zero.

## Verificação

Execute os testes automatizados a partir da pasta `webapp`:

```powershell
python -m pytest
```

## Estado atual

A aplicação inclui autenticação, dashboard, consulta e filtros de estoque, cadastro/edição/desativação de câmaras, cadastro de lotes com campos condicionais de procedência, registro de entrada inicial, entradas e saídas posteriores, histórico do lote e preferências de tema/cor. O saldo é calculado pelas movimentações e saídas acima do disponível são bloqueadas.

O banco possui migrações Alembic, usuário administrador criado por comando de terminal e catálogo inicial de classificações e apresentações.

