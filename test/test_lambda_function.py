import pytest
from unittest import mock
from datetime import datetime, timedelta

import lambda_function

@pytest.fixture
def mock_environ():
    """
    Fixture para mockar as variáveis de ambiente.
    """
    with mock.patch.dict(
        lambda_function.os.environ,
        {
            "DB_HOST": "test_host",
            "DB_NAME": "test_db",
            "DB_USER": "test_user",
            "DB_PASSWORD": "test_password",
            "DB_PORT": "5432",
            "SES_REGION": "us-east-1",
            "SENDER_EMAIL": "sender@example.com",
        },
    ):
        yield

@pytest.fixture
def mock_psycopg2_connect():
    """
    Fixture para mockar a conexão com o psycopg2.
    """
    with mock.patch("lambda_function.psycopg2.connect") as mock_connect:
        mock_conn = mock.Mock()
        mock_cursor = mock.Mock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_connect, mock_conn, mock_cursor

@pytest.fixture
def mock_boto3_client():
    """
    Fixture para mockar o cliente boto3 SES.
    """
    with mock.patch("lambda_function.boto3.client") as mock_client:
        mock_ses_client = mock.Mock()
        mock_client.return_value = mock_ses_client
        yield mock_client, mock_ses_client

def test_lambda_handler_success_no_results(
    mock_environ, mock_psycopg2_connect, mock_boto3_client
):
    """
    Testa o lambda_handler quando não há resultados de banco de dados.
    """
    mock_connect, mock_conn, mock_cursor = mock_psycopg2_connect
    mock_client_call, mock_ses_client = mock_boto3_client

    # Configura os retornos do cursor para simular que não há resultados
    mock_cursor.fetchall.side_effect = [[], []]

    event = {}
    context = {}
    response = lambda_function.lambda_handler(event, context)

    assert response["statusCode"] == 200
    assert response["body"] == "Notificações enviadas: 0 próximas, 0 expiradas."

    # Verifica se as funções do psycopg2 foram chamadas
    mock_connect.assert_called_once_with(
        host="test_host",
        database="test_db",
        user="test_user",
        password="test_password",
        port="5432",
    )
    mock_cursor.execute.call_count == 2
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()

    # Verifica se o boto3.client foi chamado para o SES
    mock_client_call.assert_called_once_with("ses", region_name="us-east-1")
    # Verifica se send_email não foi chamado (pois não há resultados)
    mock_ses_client.send_email.assert_not_called()


def test_lambda_handler_success_with_upcoming_and_expired_results(
    mock_environ, mock_psycopg2_connect, mock_boto3_client
):
    """
    Testa o lambda_handler com resultados de banco de dados para próximos e expirados.
    """
    mock_connect, mock_conn, mock_cursor = mock_psycopg2_connect
    mock_client_call, mock_ses_client = mock_boto3_client

    today = datetime.utcnow().date()
    future_date = today + timedelta(days=15)
    past_date = today - timedelta(days=5)

    # Configura os retornos do cursor para simular resultados
    mock_cursor.fetchall.side_effect = [
        # Resultados para query_upcoming
        [
            ("User One", "user1@example.com", "Laptop X", future_date),
            ("User Two", "user2@example.com", "Monitor Y", future_date),
        ],
        # Resultados para query_expired
        [
            ("User Three", "user3@example.com", "Mouse Z", past_date),
        ],
    ]

    event = {}
    context = {}
    response = lambda_function.lambda_handler(event, context)

    assert response["statusCode"] == 200
    assert response["body"] == "Notificações enviadas: 2 próximas, 1 expiradas."

    # Verifica se send_email foi chamado para cada notificação
    assert mock_ses_client.send_email.call_count == 3

def test_lambda_handler_exception(
    mock_environ, mock_psycopg2_connect, mock_boto3_client
):
    """
    Testa o lambda_handler quando ocorre uma exceção (ex: erro no DB).
    """
    mock_connect, mock_conn, mock_cursor = mock_psycopg2_connect
    mock_client_call, mock_ses_client = mock_boto3_client

    # Simula uma exceção ao tentar conectar ao DB
    mock_connect.side_effect = Exception("Erro de conexão com o banco de dados")

    event = {}
    context = {}
    response = lambda_function.lambda_handler(event, context)

    assert response["statusCode"] == 500
    assert "Erro ao processar notificações" in response["body"]
    assert "Erro de conexão com o banco de dados" in response["body"]

    # Verifica se send_email não foi chamado
    mock_ses_client.send_email.assert_not_called()
    # Verifica se close não foi chamado no conn e cursor (pois a conexão falhou)
    mock_cursor.close.assert_not_called()
    mock_conn.close.assert_not_called()


def test_send_email_notification_upcoming(mock_environ, mock_boto3_client):
    """
    Testa a função send_email_notification para ativos próximos de vencer.
    """
    mock_client_call, mock_ses_client = mock_boto3_client

    future_date = datetime.utcnow().date() + timedelta(days=10)
    lambda_function.send_email_notification(
        email="test@example.com",
        warranty_expires=future_date,
        user_name="Test User",
        asset_name="Test Asset",
        expired=False,
    )

    mock_ses_client.send_email.assert_called_once()
    args, kwargs = mock_ses_client.send_email.call_args
    assert kwargs["Source"] == "sender@example.com"
    assert kwargs["Destination"]["ToAddresses"] == ["test@example.com"]
    assert "esta Próximo de Vencer" in kwargs["Message"]["Subject"]["Data"]
    assert f"Test Asset irá expirar em 10 dias (data de vencimento: {future_date.strftime('%d/%m/%Y')})" in kwargs["Message"]["Body"]["Text"]["Data"]


def test_send_email_notification_expired(mock_environ, mock_boto3_client):
    """
    Testa a função send_email_notification para ativos expirados.
    """
    mock_client_call, mock_ses_client = mock_boto3_client

    past_date = datetime.utcnow().date() - timedelta(days=5)
    lambda_function.send_email_notification(
        email="expired@example.com",
        warranty_expires=past_date,
        user_name="Expired User",
        asset_name="Expired Asset",
        expired=True,
    )

    mock_ses_client.send_email.assert_called_once()
    args, kwargs = mock_ses_client.send_email.call_args
    assert kwargs["Source"] == "sender@example.com"
    assert kwargs["Destination"]["ToAddresses"] == ["expired@example.com"]
    assert "Expirou" in kwargs["Message"]["Subject"]["Data"]
    assert f"Expired Asset expirou em {past_date.strftime('%d/%m/%Y')}" in kwargs["Message"]["Body"]["Text"]["Data"]

def test_send_email_notification_no_user_or_asset_name(mock_environ, mock_boto3_client):
    """
    Testa send_email_notification quando user_name ou asset_name são vazios/None.
    """
    mock_client_call, mock_ses_client = mock_boto3_client

    future_date = datetime.utcnow().date() + timedelta(days=20)
    lambda_function.send_email_notification(
        email="generic@example.com",
        warranty_expires=future_date,
        user_name="",  
        asset_name=None,  
        expired=False,
    )

    mock_ses_client.send_email.assert_called_once()
    args, kwargs = mock_ses_client.send_email.call_args
    assert "Olá Usuário(a)," in kwargs["Message"]["Body"]["Text"]["Data"]
    assert "O seu ativo ativo irá expirar" in kwargs["Message"]["Body"]["Text"]["Data"]
    assert "Alerta: O seu ativo Ativo esta Próximo de Vencer" in kwargs["Message"]["Subject"]["Data"]