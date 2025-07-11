import stripe
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from retrying import retry
import re
import csv

# Configuração de logging com rotação de arquivos
from logging.handlers import RotatingFileHandler
log_handler = RotatingFileHandler('stripe_analysis.log', maxBytes=10*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[log_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', 'sk_test_sua_chave_de_api_aqui')
ANALYSIS_LIMIT = int(os.getenv('ANALYSIS_LIMIT', 100))
DAYS_BACK = int(os.getenv('DAYS_BACK', 30))

# Configurar Stripe
stripe.api_key = STRIPE_API_KEY

# Banco de dados SQLite
DB_NAME = 'stripe_failures.db'

def init_db():
    """Inicializa o banco de dados SQLite para armazenar falhas."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_failures (
                id TEXT PRIMARY KEY,
                amount REAL,
                currency TEXT,
                created TEXT,
                error_type TEXT,
                error_code TEXT,
                error_message TEXT,
                solution TEXT,
                analyzed_at TEXT
            )
        ''')
        conn.commit()
    logger.info("Banco de dados inicializado.")

# Validação de CPF
def validate_cpf(cpf):
    """Valida um CPF brasileiro."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11:
        return False
    total = sum(int(cpf[i]) * (10 - i) for i in range(9))
    remainder = (total * 10) % 11
    if remainder == 10 or remainder == 11:
        remainder = 0
    if remainder != int(cpf[9]):
        return False
    total = sum(int(cpf[i]) * (11 - i) for i in range(10))
    remainder = (total * 10) % 11
    if remainder == 10 or remainder == 11:
        remainder = 0
    return remainder == int(cpf[10])

# Validação de CNPJ
def validate_cnpj(cnpj):
    """Valida um CNPJ brasileiro."""
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * weights1[i] for i in range(12))
    remainder = total % 11
    digit1 = 0 if remainder < 2 else 11 - remainder
    if int(cnpj[12]) != digit1:
        return False
    total = sum(int(cnpj[i]) * weights2[i] for i in range(13))
    remainder = total % 11
    digit2 = 0 if remainder < 2 else 11 - remainder
    return int(cnpj[13]) == digit2

# Mapeamento de erros e soluções
def get_error_solution(error_type, error_code, error_message, customer_id=None):
    """Retorna solução para um erro da Stripe, incluindo validação de dados brasileiros."""
    solutions = {
        'card_error': {
            'expired_card': 'Enviar lembrete ao cliente para atualizar o cartão.',
            'insufficient_funds': 'Notificar o cliente sobre fundos insuficientes e sugerir outro método.',
            'card_declined': 'Verificar com o cliente se o cartão está bloqueado ou tentar outro método.',
            'incorrect_cvc': 'Solicitar que o cliente confirme o código CVC do cartão.',
            'invalid_card_number': 'Validar o número do cartão no front-end antes de enviar à Stripe.'
        },
        'api_connection_error': {
            None: 'Verificar conectividade de rede e tentar novamente.'
        },
        'rate_limit_error': {
            None: 'Reduzir frequência de chamadas à API ou contatar o suporte da Stripe.'
        },
        'authentication_error': {
            None: 'Verificar se a chave de API está correta.'
        },
        'invalid_request_error': {
            'invalid_account_details': 'Verificar dados bancários (ex.: CPF/CNPJ incorreto).'
        }
    }
    solution = solutions.get(error_type, {}).get(error_code, f'Mensagem de erro: {error_message}')
    
    # Validação de CPF/CNPJ para erros de conta
    if error_code == 'invalid_account_details' and customer_id:
        try:
            customer = stripe.Customer.retrieve(customer_id)
            tax_id = customer.get('tax_id_data', [{}])[0].get('value', '')
            if tax_id:
                if len(tax_id) == 11 and not validate_cpf(tax_id):
                    solution += ' CPF inválido. Solicitar correção ao cliente.'
                elif len(tax_id) == 14 and not validate_cnpj(tax_id):
                    solution += ' CNPJ inválido. Solicitar correção ao cliente.'
        except stripe.error.StripeError as e:
            logger.error(f"Erro ao verificar cliente {customer_id}: {str(e)}")
    
    return solution

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def fetch_payment_intent(pi_id):
    """Recupera um PaymentIntent com retries para erros transitórios."""
    return stripe.PaymentIntent.retrieve(pi_id)

def analyze_failed_payments(limit=ANALYSIS_LIMIT, days_back=DAYS_BACK):
    """Analisa falhas de pagamento na Stripe."""
    try:
        logger.info(f"Iniciando análise de até {limit} PaymentIntents dos últimos {days_back} dias...")
        since = int((datetime.now() - timedelta(days=days_back)).timestamp())
        payment_intents = stripe.PaymentIntent.list(limit=limit, created={'gte': since})
        failed_payments = []

        # Processamento paralelo
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for pi in payment_intents.auto_paging_iter():
                if pi.status == 'requires_payment_method' and pi.last_payment_error:
                    futures.append(executor.submit(fetch_payment_intent, pi.id))

            for future in futures:
                try:
                    pi = future.result()
                    error = pi.last_payment_error
                    failed_payments.append({
                        'id': pi.id,
                        'amount': pi.amount / 100,
                        'currency': pi.currency.upper(),
                        'created': datetime.fromtimestamp(pi.created).strftime('%Y-%m-%d %H:%M:%S'),
                        'error_type': error.get('type', 'unknown'),
                        'error_code': error.get('code', None),
                        'error_message': error.get('message', 'Sem mensagem de erro'),
                        'solution': get_error_solution(
                            error.get('type', 'unknown'),
                            error.get('code', None),
                            error.get('message', 'Sem mensagem de erro'),
                            pi.get('customer')
                        ),
                        'analyzed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                except stripe.error.StripeError as e:
                    logger.error(f"Erro ao processar PaymentIntent: {str(e)}")

        logger.info(f"Encontrados {len(failed_payments)} pagamentos com falha.")
        return failed_payments

    except stripe.error.StripeError as e:
        logger.error(f"Erro ao recuperar PaymentIntents: {str(e)}")
        return []

def save_to_db(failed_payments):
    """Salva falhas no banco de dados SQLite."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        for payment in failed_payments:
            cursor.execute('''
                INSERT OR REPLACE INTO payment_failures
                (id, amount, currency, created, error_type, error_code, error_message, solution, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payment['id'],
                payment['amount'],
                payment['currency'],
                payment['created'],
                payment['error_type'],
                payment['error_code'],
                payment['error_message'],
                payment['solution'],
                payment['analyzed_at']
            ))
        conn.commit()
    logger.info(f"Salvou {len(failed_payments)} falhas no banco de dados.")

def generate_report(failed_payments, formats=['markdown', 'csv']):
    """Gera relatórios em Markdown e/ou CSV."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if 'markdown' in formats:
        report = "# Relatório de Falhas de Pagamento - Stripe\n\n"
        report += f"**Data de Geração**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"**Total de Falhas Encontradas**: {len(failed_payments)}\n\n"
        
        if not failed_payments:
            report += "## Nenhuma falha de pagamento encontrada.\n"
        else:
            report += "## Detalhes das Falhas\n"
            for payment in failed_payments:
                report += f"### Pagamento ID: {payment['id']}\n"
                report += f"- **Valor**: {payment['amount']:.2f} {payment['currency']}\n"
                report += f"- **Data de Criação**: {payment['created']}\n"
                report += f"- **Tipo de Erro**: {payment['error_type']}\n"
                report += f"- **Código de Erro**: {payment['error_code'] or 'N/A'}\n"
                report += f"- **Mensagem de Erro**: {payment['error_message']}\n"
                report += f"- **Solução Sugerida**: {payment['solution']}\n\n"
        
        report_filename = f"stripe_failure_report_{timestamp}.md"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Relatório Markdown gerado: {report_filename}")

    if 'csv' in formats:
        df = pd.DataFrame(failed_payments)
        csv_filename = f"stripe_failure_report_{timestamp}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        logger.info(f"Relatório CSV gerado: {csv_filename}")

    return report_filename if 'markdown' in formats else csv_filename

def main():
    """Função principal para executar a análise."""
    try:
        init_db()
        failed_payments = analyze_failed_payments(limit=ANALYSIS_LIMIT, days_back=DAYS_BACK)
        if failed_payments:
            save_to_db(failed_payments)
            report_filename = generate_report(failed_payments, formats=['markdown', 'csv'])
            print(f"Relatório gerado: {report_filename}")
            print(f"Total de falhas encontradas: {len(failed_payments)}")
            print(f"Exemplo de falha:")
            print(f"ID: {failed_payments[0]['id']}")
            print(f"Erro: {failed_payments[0]['error_message']}")
            print(f"Solução: {failed_payments[0]['solution']}")
        else:
            print("Nenhuma falha de pagamento encontrada.")
    except Exception as e:
        logger.error(f"Erro na execução do script: {str(e)}")
        print(f"Erro: {str(e)}. Verifique o arquivo de log para mais detalhes.")

if __name__ == "__main__":
    main()