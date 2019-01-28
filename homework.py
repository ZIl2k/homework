import logging
import smtplib
import socket
import sys
from configparser import ConfigParser
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging import handlers

import pandas as pd
from atlassian import Confluence


def send_email(emails, data):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'День рождения'
    msg['From'] = smtp_user
    msg['bcc'] = ', '.join(emails)

    text = '<p>Добрый день! Ближайшие дни рождения:</p><br>'
    html = text + data.to_html()

    msg.attach(MIMEText(html, 'html'))

    server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    server.login(smtp_user, smtp_password)
    server.sendmail(smtp_user, emails, msg.as_string())
    server.quit()


config = ConfigParser()
config.read('config.conf')

confluence_server = config.get("confluence", "server")
confluence_port = config.get("confluence", "port")
confluence_user = config.get("confluence", "user")
confluence_password = config.get("confluence", "password")
confluence_document = config.get("confluence", "document_key")

smtp_server = config.get("smtp", "server")
smtp_port = config.get("smtp", "port")
smtp_user = config.get("smtp", "user")
smtp_password = config.get("smtp", "password")

log_file = 'homework.log'

log = logging.getLogger()
log.setLevel(logging.INFO)
Log_format = logging.Formatter('%(levelname)-4s [%(asctime)s] %(message)s')

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(Log_format)
log.addHandler(ch)

fh = logging.handlers.RotatingFileHandler(log_file, encoding='utf8', mode='a', maxBytes=50 * 1024 * 1024)
fh.setFormatter(Log_format)
log.addHandler(fh)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
confluence_status = sock.connect_ex((confluence_server, int(confluence_port)))

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
mail_status = sock.connect_ex((smtp_server, int(smtp_port)))

now = datetime.now()
week_ago = now - timedelta(days=7)
tomorrow = now + timedelta(days=1)

if datetime.today().weekday() in (5, 6):
    log.error("скрипт запущен в выходной день. В выходные никаких рассылок.")
    sys.exit(1)

if confluence_status is not 0:
    log.error("сервер %s:%s недоступен.", confluence_server, confluence_port)
    sys.exit(1)

if mail_status is not 0:
    log.error("сервер %s:%s недоступен.", smtp_server, smtp_port)
    sys.exit(1)

confluence = Confluence(
    url=f'http://{confluence_server}:{confluence_port}',
    username=confluence_user,
    password=confluence_password)

html_data = confluence.get_page_by_id(confluence_document, expand='body.storage')['body']['storage']['value']

df = pd.read_html(html_data, header=0, converters={'День рождения': str})[0]
df = df.loc[df["Комната"] != "уволен", ['ФИО', 'e-mail', 'День рождения']]

df['День рождения'] = df['День рождения'].astype(str)
df['День рождения'] = df['День рождения'].apply(
    lambda x: f"{now.year}.{x[-2:]}.{x[:2]}" if x.lower() != 'nan' else None
)

mask = (df['День рождения'] <= tomorrow.strftime("%Y.%m.%d")) & (
        df['День рождения'] >= week_ago.strftime("%Y.%m.%d")
)

birthday_users = df.loc[mask, ['ФИО', 'e-mail', 'День рождения']]

if birthday_users.size == 0:
    log.info('именинники не найдены')
    sys.exit(1)

send_emails = list(set(df['e-mail'].tolist()) - set(birthday_users['e-mail'].tolist()))

if len(send_emails) != 0:
    send_email(send_emails, birthday_users)  # отправляем всем, кроме именинников

for index, row in birthday_users.iterrows():  # досылаем именникам исключая их самих из таблицы
    email = row['e-mail']
    send_email(email, birthday_users.loc[birthday_users['e-mail'] != email])
