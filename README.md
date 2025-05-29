# Lambda de Notificação de Garantia de Ativos

Este projeto consiste em uma função **AWS Lambda**, escrita em Python, que é acionada pelo **AWS EventBridge** e automatiza o envio de notificações por e-mail sobre vencimentosde ativos próximos a expirar ou já expiradas.  
A função consulta um banco de dados **PostgreSQL**, identifica os ativos relacionados a cada usuário e envia alertas personalizados por meio do **Amazon Simple Email Service (SES)**.

---

### Funcionalidades
- EventBridge para acionar a Lambda.
- Conexão com banco de dados PostgreSQL.
- Consulta de ativos com garantia expirando nos próximos 30 dias.
- Consulta de ativos com garantia já expirada.
- Envio de e-mails personalizados de notificação utilizando AWS SES.

---

### Tecnologias Utilizadas

- Python 3.x
- AWS Lambda
- AWS Simple Email Service (SES)
- PostgreSQL
- Psycopg2
- Boto3

---

### Estrutura do Projeto

- **lambda_handler**: Função principal da Lambda. Realiza a conexão com o banco, executa as consultas e aciona o envio de e-mails.
- **send_email_notification**: Função auxiliar para compor e enviar os e-mails de notificação via AWS SES.

---

### Configurações Necessárias

As seguintes variáveis de ambiente devem ser configuradas na AWS Lambda:

| Variável      | Descrição                                                        |
|---------------|------------------------------------------------------------------|
| DB_HOST       | Host do banco de dados PostgreSQL                                |
| DB_NAME       | Nome do banco de dados                                           |
| DB_USER       | Usuário do banco de dados                                        |
| DB_PASSWORD   | Senha do banco de dados                                          |
| DB_PORT       | Porta do banco de dados (opcional, padrão: 5432)                 |
| SES_REGION    | Região do serviço AWS SES (opcional, padrão: us-east-1)          |
| SENDER_EMAIL  | E-mail verificado no AWS SES que será usado como remetente       |

Além disso, a Lambda precisa das seguintes permissões:

- Acesso ao banco de dados PostgreSQL.
- Permissão `ses:SendEmail` para envio de e-mails via AWS SES.

---

### Banco de Dados

O código realiza consultas nas seguintes tabelas e campos:

- **Tabela `asset_assignment`:**
  - `user_id`
  - `active_id`
  - `isactive`
- **Tabela `ativos`:**
  - `id`
  - `model`
  - `warrantyexpires`
- **Tabela `users`:**
  - `id`
  - `nome`
  - `email`

As consultas retornam usuários que possuem ativos com garantia próxima de expirar (até 30 dias) ou já expirada.

---

### Exemplo de Retorno

Sucesso:
```json
{
  "statusCode": 200,
  "body": "Notificações enviadas: 5 próximas, 2 expiradas."
}
{
  "statusCode": 500,
  "body": "Erro ao processar notificações: <mensagem de erro>"
}
```
---

### Deploy
- Empacote o código-fonte juntamente com as dependências (psycopg2-binary e boto3, se necessário).
- Configure as variáveis de ambiente conforme a seção Configurações Necessárias.
- Ajuste as permissões da função Lambda para permitir o envio de e-mails via SES.
- Realize o deploy via AWS Console ou utilizando ferramentas como AWS CLI ou SAM.

### Observações
- O e-mail do remetente (SENDER_EMAIL) deve estar verificado no SES.
- Em ambiente de sandbox do SES, os destinatários também precisam estar verificados.
- O código utiliza boas práticas para formatação de datas e tratamento de nomes nulos.

### Autor
Desenvolvido por João Brito.