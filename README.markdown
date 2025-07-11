# Stripe Payment Failure Analyzer

## Visão Geral
Este projeto, desenvolvido por **Paulo Xavier**, é uma ferramenta robusta em Python para analisar falhas de pagamento na API da Stripe, identificar causas de erros e sugerir soluções práticas. Projetado para empresas que utilizam a Stripe como gateway de pagamento, o script otimiza a detecção de problemas como cartões recusados, erros de conectividade ou falhas de configuração, com foco em reduzir perdas de vendas e melhorar a experiência do cliente. Ele é especialmente adaptado para o mercado brasileiro, com validação de CPF/CNPJ e suporte a grandes volumes de dados.

## Funcionalidades
- **Análise Eficiente de Pagamentos**: Recupera `PaymentIntents` dos últimos 30 dias (configurável) com paginação manual para alto desempenho.
- **Diagnóstico Avançado de Erros**: Identifica tipos de erro (ex.: `card_error`, `api_connection_error`) e códigos específicos (ex.: `expired_card`, `insufficient_funds`), com soluções personalizadas.
- **Validação Brasileira**: Inclui validação de CPF/CNPJ para erros de dados bancários, ideal para integrações no Brasil.
- **Processamento Paralelo**: Utiliza `ThreadPoolExecutor` para analisar múltiplos `PaymentIntents` simultaneamente, com até 5 threads.
- **Retries Automáticos**: Implementa retries exponenciais para falhas transitórias (ex.: problemas de rede) usando a biblioteca `retrying`.
- **Armazenamento em Banco de Dados**: Salva falhas em um banco SQLite para histórico e análise futura.
- **Relatórios Flexíveis**: Gera relatórios detalhados em Markdown e CSV, com ID do pagamento, valor, data, erro e solução sugerida.
- **Logging Robusto**: Registra a execução com rotação de logs (máximo 10 MB por arquivo), garantindo rastreabilidade.
- **Configuração Externa**: Usa arquivo `.env` para gerenciar chaves de API, limites de análise e período de busca.

## Como Usar
### Pré-requisitos
- Python 3.8+
- Bibliotecas: `stripe`, `python-dotenv`, `pandas`, `retrying` (`pip install stripe python-dotenv pandas retrying`)
- Chave de API da Stripe (modo de teste ou produção)

### Configuração
1. Crie um arquivo `.env` na pasta do projeto com:
   ```
   STRIPE_API_KEY=sk_test_sua_chave_de_api_aqui
   ANALYSIS_LIMIT=100
   DAYS_BACK=30
   ```
2. Execute o script com:
   ```bash
   python analyze_stripe_failures.py
   ```

### Saída
- **Relatórios**: Arquivos `stripe_failure_report_YYYYMMDD_HHMMSS.md` (Markdown) e `stripe_failure_report_YYYYMMDD_HHMMSS.csv` (CSV) com detalhes das falhas.
- **Banco de Dados**: `stripe_failures.db` com histórico de falhas.
- **Log**: `stripe_analysis.log` com registros da execução (com rotação de arquivos).

## Exemplo de Relatório
```markdown
# Relatório de Falhas de Pagamento - Stripe

**Data de Geração**: 2025-07-10 21:54:00
**Total de Falhas Encontradas**: 2

## Detalhes das Falhas

### Pagamento ID: pi_3N5Xyz123456789
- **Valor**: 50.00 BRL
- **Data de Criação**: 2025-07-10 14:22:10
- **Tipo de Erro**: card_error
- **Código de Erro**: expired_card
- **Mensagem de Erro**: Your card has expired.
- **Solução Sugerida**: Enviar lembrete ao cliente para atualizar o cartão.

### Pagamento ID: pi_3N5Wxy987654321
- **Valor**: 120.00 BRL
- **Data de Criação**: 2025-07-10 13:15:30
- **Tipo de Erro**: invalid_request_error
- **Código de Erro**: invalid_account_details
- **Mensagem de Erro**: Invalid tax ID.
- **Solução Sugerida**: Verificar dados bancários (ex.: CPF/CNPJ incorreto). CPF inválido. Solicitar correção ao cliente.
```

## Estrutura do Projeto
- `analyze_stripe_failures.py`: Script principal para análise de falhas.
- `.env`: Configurações de API e parâmetros.
- `stripe_failures.db`: Banco de dados SQLite para histórico.
- `stripe_analysis.log`: Log de execução com rotação.
- `stripe_failure_report_*.md`: Relatórios em Markdown.
- `stripe_failure_report_*.csv`: Relatórios em CSV.

## Casos de Uso
- **E-commerce**: Reduza perdas de vendas identificando e corrigindo falhas de pagamento.
- **Startups Brasileiras**: Valide dados bancários (CPF/CNPJ) para integrações locais com a Stripe.
- **Consultoria**: Ofereça serviços de diagnóstico e otimização para empresas que usam a Stripe.
- **Análise de Dados**: Monitore tendências de falhas com relatórios em CSV para análises em ferramentas como Excel ou Power BI.

## Possíveis Melhorias
- Dashboard interativo com Flask ou Streamlit para visualização de falhas.
- Notificações automáticas via e-mail ou Slack para falhas críticas.
- Integração com APIs de validação externa para dados bancários brasileiros.
- Exportação de relatórios em PDF usando LaTeX.

## Contato
Desenvolvido por **Paulo Xavier**. Entre em contato via [admin@px.dev.br](mailto:admin@px.dev.br) ou [LinkedIn](https://www.linkedin.com/in/seu-perfil) para colaborações, oportunidades de trabalho ou serviços de consultoria em integração de sistemas de pagamento.

## Licença
MIT License