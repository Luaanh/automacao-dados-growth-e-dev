# ⚙️ ETL/ELT Pipeline Architecture & Data Warehouse

![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-017CEE?style=for-the-badge&logo=apache-airflow&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-00000F?style=for-the-badge&logo=mysql&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Advanced-lightgrey?style=for-the-badge&logo=database&logoColor=white)

Infraestrutura centralizada de Engenharia de Dados orquestrada por **Apache Airflow**, unificando ingestão, transformação e consolidação em um Data Warehouse.

## 🎯 Problema de Negócio

O ecossistema de dados da operação apresentava fontes altamente pulverizadas (Bancos relacionais, Excel, portais web, APIs, marketplaces como WebMotors). O processamento ocorria por scripts descentralizados rodando em loops frágeis (`while True: schedule.run_pending()`), resultando em:
- Dificuldade em debugar falhas e gargalos.
- Alta manutenção operacional.
- Ausência de retentativas automáticas e alertas consistentes.
- Bases fragmentadas dificultando geração de relatórios massivos de comissão.

## ⚡ Solução Desenvolvida

Migração completa da infraestrutura de agendamento para **Apache Airflow DAGs**, implementando fluxos de ETL/ELT resilientes e idempotentes, alimentando um Data Warehouse estruturado.

### 🌟 Destaques & Funcionalidades
- **Orquestração Profissional:** Substituição do modelo legado (`schedule`) por um hub centralizado usando Airflow (`dags/`).
- **Ingestão Multi-Fonte:** Capacidade de extrair JSON da WebMotors, ler propostas de bancos (Santander, BV), coletar margens de mais de 6 portais via scraping (Consignet, SmartConsig, etc).
- **Processamento Massivo:** Pipelines gigantes como o `relatorios_comissao.py` (50K bytes) e automações do CRM Automotivo (`daily_ecoagile.py`).
- **Utilitários Core:** Biblioteca interna (`utils_ramos.py` e `utils_analytics.py`) para context managers de banco de dados e transformações padronizadas.

## 🏗️ Arquitetura

```text
[ Data Sources ]       [ Staging Area ]        [ Transformation ]         [ Serving / DWH ]
                                                (Airflow DAGs)

 APIs REST        ---+                      +--> Validação (Pandas) --+
 WebMotors JSON   ---+--> Raw Files / S3 ---|                         |--> PostgreSQL / MySQL
 Web Scraping     ---+   (Propostas/Margens)+--> Limpeza e Joins  ----+    (Data Warehouse)
 DBs Relacionais  ---+                      |    (SQL Advanced)       |--> Excel Consolidado
 Excel/CSV        ---+                      +--> Alertas/Logs     ----+
```

## 🛠️ Tecnologias Utilizadas

- **Orquestração:** Apache Airflow 2.x (DAGs, PythonOperator, Task Groups)
- **Linguagem:** Python (Pandas, SQLAlchemy, OpenPyXL)
- **Bancos de Dados:** MySQL, PostgreSQL, SQLite
- **Transformação de Dados:** SQL Advanced (CTEs, Window Functions, Joins complexos)
- **Ingestão:** Selenium, Requests (Scraping de múltiplos portais)

## 📊 Impacto / Resultados / Métricas

- **Economia de Tempo:** Mais de 100+ horas/mês economizadas devido à automação dos fluxos operacionais e relatórios gerenciais.
- **Resiliência:** A adoção do Airflow garantiu retentativas automáticas, histórico de execuções e monitoramento robusto.
- **Data Quality:** Padronização da entrada de dados das propostas multibancos, reduzindo erros de consolidação de faturamento.

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte interno, credenciais, URLs de APIs proprietárias e regras de negócio específicas foram omitidos ou mockados neste repositório visando proteção de propriedade intelectual e conformidade com a LGPD. O repositório atua estritamente como um portfólio de arquitetura e tecnologia.
