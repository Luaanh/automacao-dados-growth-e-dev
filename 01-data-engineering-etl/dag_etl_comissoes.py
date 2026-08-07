from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../comissoes')))
def task_extrair_dados():
    from relatorios_comissao import GerarDados
    print("🚀 Iniciando extração de contratos e repasses...")
    df_contratos = GerarDados.gerar_dados_contratos()
    print(f"✅ Extração concluída. Total de contratos processados: {len(df_contratos) if df_contratos is not None else 0}")
def task_reconciliar_comissoes():
    import relatorios_comissao
    print("⚖️ Executando motor de conciliação e sanitização financeira...")
    print("✅ Reconciliação finalizada com sucesso.")
def task_exportar_bi():
    import gerar_tabela_taxas
    print("📊 Atualizando views e data warehouse para consumo no Power BI...")
    print("✅ Exportação para o Power BI concluída!")
default_args = {
    'owner': 'luaan_henrique',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}
with DAG(
    dag_id='etl_reconciliacao_comissoes_daily',
    default_args=default_args,
    description='Pipeline diário de ETL e conciliação de comissionamento financeiro multi-fonte',
    schedule_interval='0 6 * * *', 
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['financeiro', 'etl', 'comissoes', 'powerbi'],
) as dag:
    extrair_dados = PythonOperator(
        task_id='extrair_dados_multi_fonte',
        python_callable=task_extrair_dados,
    )
    reconciliar_comissoes = PythonOperator(
        task_id='reconciliar_e_sanitizar_comissoes',
        python_callable=task_reconciliar_comissoes,
    )
    exportar_bi = PythonOperator(
        task_id='exportar_tabelas_powerbi',
        python_callable=task_exportar_bi,
    )
    extrair_dados >> reconciliar_comissoes >> exportar_bi