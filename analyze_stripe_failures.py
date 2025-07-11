import stripe
import logging
from datetime import datetime
import os

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='stripe_analysis.log'
)

# Configuração da chave de API da Stripe (substitua com sua chave de teste)
stripe.api_key = "sk_test_sua_chave_de_api_aqui"

# Função para mapear erros comuns da Stripe e sugerir soluções
def get_error_solution(error_type, error_code, error_message):
    solutions = {
        'card_error': {
            'expired_card': 'Enviar lembrete ao cliente para atualizar o cartão.',
            'insufficient_funds': 'Notificar o cliente sobre fundos insuficientes e sugerir outro método de pagamento.',
            'card_declined': 'Verificar com o cliente se o cartão está bloqueado ou tentar outro método.',
            'incorrect_cvc': 'Solicitar que o cliente confirme o código CVC do cartão.',
            'invalid_card_number': 'Validar o número do cartão no front-end antes de enviar à Stripe.'
        },
        'api_connection_error': {
            None: 'Verificar conectividade de rede e tentar novamente após alguns minutos.'
        },
        'rate_limit_error': {
            None: 'Reduzir a frequência de chamadas à API ou contatar o suporte da Stripe para aumentar limites.'
        },
        'authentication_error': {
            None: 'Verificar se a chave de API está correta e tem permissões adequadas.'
        }
    }
    return solutions.get(error_type, {}).get(error_code, f'Nenhuma solução específica. Mensagem de erro: {error_message}')

# Função para analisar falhas de pagamento
def analyze_failed_payments(limit=100):
    try:
        logging.info("Iniciando análise de PaymentIntents...")
        # Recuperar PaymentIntents (limite configurável)
        payment_intents = stripe.PaymentIntent.list(limit=limit)
        failed_payments = []

        for pi in payment_intents.auto_paging_iter():
            if pi.status == 'requires_payment_method' and pi.last_payment_error:
                error = pi.last_payment_error
                failed_payments.append({
                    'id': pi.id,
                    'amount': pi.amount / 100,  # Converter centavos para reais
                    'currency': pi.currency.upper(),
                    'created': datetime.fromtimestamp(pi.created).strftime('%Y-%m-%d %H:%M:%S'),
                    'error_type': error.get('type', 'unknown'),
                    'error_code': error.get('code', None),
                    'error_message': error.get('message', 'Sem mensagem de erro'),
                    'solution': get_error_solution(
                        error.get('type', 'unknown'),
                        error.get('code', None),
                        error.get('message', 'Sem mensagem de erro')
                    )
                })

        logging.info(f"Encontrados {len(failed_payments)} pagamentos com falha.")
        return failed_payments

    except stripe.error.StripeError as e:
        logging.error(f"Erro ao recuperar PaymentIntents: {str(e)}")
        return []

# Função para gerar relatório em Markdown
def generate_report(failed_payments):
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

    # Salvar relatório em arquivo
    report_filename = f"stripe_failure_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report)
    logging.info(f"Relatório gerado: {report_filename}")
    return report_filename

# Função principal
def main():
    try:
        # Analisar falhas
        failed_payments = analyze_failed_payments(limit=100)
        
        # Gerar relatório
        report_filename = generate_report(failed_payments)
        print(f"Relatório gerado com sucesso: {report_filename}")
        
        # Exibir resumo no console
        print(f"Total de falhas encontradas: {len(failed_payments)}")
        if failed_payments:
            print("Exemplo de falha encontrada:")
            print(f"ID: {failed_payments[0]['id']}")
            print(f"Erro: {failed_payments[0]['error_message']}")
            print(f"Solução: {failed_payments[0]['solution']}")

    except Exception as e:
        logging.error(f"Erro na execução do script: {str(e)}")
        print(f"Erro: {str(e)}. Verifique o arquivo de log para mais detalhes.")

if __name__ == "__main__":
    main()