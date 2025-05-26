import os
import psycopg2
import boto3
from datetime import datetime, timedelta

# Configurações de ambiente
DB_HOST = os.environ['DB_HOST']
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_PORT = os.environ.get('DB_PORT', '5432')

SES_REGION = os.environ.get('SES_REGION', 'us-east-1')
SENDER_EMAIL = os.environ['SENDER_EMAIL']

# Inicializa SES
ses_client = boto3.client('ses', region_name=SES_REGION)

def lambda_handler(event, context):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()

        today = datetime.utcnow().date()
        limit_date = today + timedelta(days=30)

        # Consulta para próximos do vencimento
        query_upcoming = """
            SELECT aa.user_id, u.email, a.warranty_expires
            FROM asset_assignment aa
            JOIN ativos a ON aa.asset_id = a.id
            JOIN users u ON aa.user_id = u.id
            WHERE aa.is_active = TRUE AND a.warranty_expires BETWEEN %s AND %s;
        """

        cursor.execute(query_upcoming, (today, limit_date))
        upcoming_results = cursor.fetchall()

        for user_id, email, warranty_expires in upcoming_results:
            send_email_notification(email, warranty_expires, expired=False)

        # Consulta para expirados
        query_expired = """
            SELECT aa.user_id, u.email, a.warranty_expires
            FROM asset_assignment aa
            JOIN ativos a ON aa.asset_id = a.id
            JOIN users u ON aa.user_id = u.id
            WHERE aa.is_active = TRUE AND a.warranty_expires < %s;
        """

        cursor.execute(query_expired, (today,))
        expired_results = cursor.fetchall()

        for user_id, email, warranty_expires in expired_results:
            send_email_notification(email, warranty_expires, expired=True)

        cursor.close()
        conn.close()

        return {
            'statusCode': 200,
            'body': f'Notificações enviadas: {len(upcoming_results)} próximas, {len(expired_results)} expiradas.'
        }

    except Exception as e:
        print(f"Erro: {e}")
        return {
            'statusCode': 500,
            'body': str(e)
        }

def send_email_notification(email, warranty_expires, expired=False):
    if expired:
        subject = "Alerta: Seu Ativo Expirou"
        body_text = (f"Olá,\n\n"
                     f"Seu ativo expirou em {warranty_expires}.\n"
                     f"Por favor, regularize a situação.\n\n"
                     f"Atenciosamente,\nEquipe de TI.")
    else:
        dias_restantes = (warranty_expires - datetime.utcnow().date()).days
        subject = "Aviso: Seu Ativo está Próximo de Vencer"
        body_text = (f"Olá,\n\n"
                     f"O seu ativo irá expirar em {dias_restantes} dias (em {warranty_expires}).\n"
                     f"Por favor, tome as providências necessárias.\n\n"
                     f"Atenciosamente,\nEquipe de TI.")

    response = ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={'ToAddresses': [email]},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': body_text}}
        }
    )
    print(f"E-mail enviado para {email}: {response['MessageId']}")