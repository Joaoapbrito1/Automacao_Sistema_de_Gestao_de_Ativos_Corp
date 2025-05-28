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

        query_upcoming = """
            SELECT u.nome AS user_name, 
                   u.email, 
                   a.model AS asset_name,
                   a.warrantyexpires
            FROM asset_assignment aa
            JOIN ativos a ON aa.active_id = a.id 
            JOIN users u ON aa.user_id = u.id
            WHERE aa.isactive = TRUE AND a.warrantyexpires BETWEEN %s AND %s;
        """

        cursor.execute(query_upcoming, (today, limit_date))
        upcoming_results = cursor.fetchall()

        for user_name, email, asset_name, warranty_expires in upcoming_results:
            send_email_notification(
                email=email,
                warranty_expires=warranty_expires,
                user_name=user_name,
                asset_name=asset_name,
                expired=False
            )

        query_expired = """
            SELECT u.nome AS user_name, 
                   u.email, 
                   a.model AS asset_name,
                   a.warrantyexpires
            FROM asset_assignment aa
            JOIN ativos a ON aa.active_id = a.id
            JOIN users u ON aa.user_id = u.id
            WHERE aa.isactive = TRUE AND a.warrantyexpires < %s;
        """

        cursor.execute(query_expired, (today,))
        expired_results = cursor.fetchall()

        for user_name, email, asset_name, warranty_expires in expired_results:
            send_email_notification(
                email=email,
                warranty_expires=warranty_expires,
                user_name=user_name,
                asset_name=asset_name,
                expired=True
            )

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
            'body': f'Erro ao processar notificações: {str(e)}'
        }

def send_email_notification(email, warranty_expires, user_name, asset_name, expired=False):

    user_greeting_name = user_name if user_name and user_name.strip() else "Usuário(a)"
    
    asset_display_name = asset_name if asset_name and asset_name.strip() else "Ativo" # "Ativo" como fallback

    formatted_warranty_expires = warranty_expires.strftime('%d/%m/%Y')

    if expired:
        subject = f"Alerta: O seu ativo {asset_display_name} Expirou"
        body_text = (f"Olá {user_greeting_name},\n\n"
                     f"O seu ativo {asset_display_name.lower()} expirou em {formatted_warranty_expires}.\n"
                     f"Por favor, verifique a situação e tome as providências necessárias.\n\n"
                     f"Atenciosamente,\nEquipe de TI.")
    else:
        dias_restantes = (warranty_expires - datetime.utcnow().date()).days
        subject = f"Alerta: O seu ativo {asset_display_name} esta Próximo de Vencer"
        body_text = (f"Olá {user_greeting_name},\n\n"
                     f"O seu ativo {asset_display_name.lower()} irá expirar em {dias_restantes} dias (data de vencimento: {formatted_warranty_expires}).\n"
                     f"Por favor, tome as providências necessárias.\n\n"
                     f"Atenciosamente,\nEquipe de TI.")

    try:
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body_text}}
            }
        )
        print(f"E-mail enviado para {email} (Assunto: {subject}): {response['MessageId']}")
    except Exception as e:
        print(f"Erro ao enviar e-mail para {email}: {str(e)}")