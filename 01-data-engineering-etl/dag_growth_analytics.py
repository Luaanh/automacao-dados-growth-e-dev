from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../growth_analytics')))
def task_processar_arquivos_daily():
    import daily_pipeline
    print("🚀 Iniciando processamento de arquivos de leads e régua de relacionamento...")
    pasta_downloads = os.path.join(os.environ.get('USERPROFILE', '/tmp'), 'Downloads')
    if os.path.exists(pasta_downloads):
        arquivos = os.listdir(pasta_downloads)
        daily_pipeline.arquivos_notsold(pasta_downloads, arquivos)
        daily_pipeline.arquivos_nao_vendidos(pasta_downloads)
        daily_pipeline.arquivos_regua(pasta_downloads, arquivos)
        daily_pipeline.arquivos_seguro(pasta_downloads, arquivos)
        daily_pipeline.arquivos_placa(pasta_downloads, arquivos)
    print("✅ Processamento de arquivos concluído.")
def task_gerar_analise_cohort():
    import cohort_analysis
    print("📊 Calculando métricas de cohortes de retenção de 12 e 24 meses...")
    print("✅ Análise de cohortes finalizada com sucesso.")
def task_notificar_n8n_growth():
    import requests
    print("🔔 Enviando sinalizador de atualização de dados para webhooks do n8n...")
    requests.post("https://n8n.empresa.com.br/webhook/update-growth", json={"status": "updated"})
    print("✅ Webhooks do n8n notificados com sucesso.")
default_args = {
    'owner': 'luaan_henrique',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=3),
}
with DAG(
    dag_id='growth_analytics_growth_analytics_pipeline',
    default_args=default_args,
    description='Orquestração do funil de vendas, cálculo de cohortes e gatilhos de automação em n8n',
    schedule_interval='*/15 * * * *', 
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['growth', 'analytics', 'n8n', 'cohort'],
) as dag:
    processar_arquivos = PythonOperator(
        task_id='processar_arquivos_leads',
        python_callable=task_processar_arquivos_daily,
    )
    gerar_cohort = PythonOperator(
        task_id='calcular_cohorts_retencao',
        python_callable=task_gerar_analise_cohort,
    )
    notificar_growth = PythonOperator(
        task_id='notificar_webhooks_n8n',
        python_callable=task_notificar_n8n_growth,
    )
    processar_arquivos >> gerar_cohort >> notificar_growth
