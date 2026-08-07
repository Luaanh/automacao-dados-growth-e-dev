# ⚙️ ETL/ELT Pipeline Architecture & Data Warehouse (Analytics Infrastructure)

![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-017CEE?style=for-the-badge&logo=apache-airflow&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-00000F?style=for-the-badge&logo=mysql&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Advanced-lightgrey?style=for-the-badge&logo=database&logoColor=white)

Infraestrutura centralizada de engenharia e modelagem de dados orquestrada por **Apache Airflow**, projetada para unificar ingestão multi-fonte, transformações analíticas e consolidação em um Data Warehouse estruturado.

---

## 🎯 Problema de Negócio

O ecossistema operacional apresentava fontes de dados fragmentadas e pulverizadas (Bancos transacionais de CRMs, planilhas Excel financeiras, portais de parceiros via web scraping, APIs REST e marketplaces de leads). 

O processamento ocorria através de scripts locais descentralizados executando loops frágeis (`while True: schedule.run_pending()`), resultando em:
- Dificuldade em debugar falhas de execução e gargalos de processamento.
- Perda de histórico de execuções e ausência de retentativas (retries) automáticas em falhas de rede.
- Inconsistência na consolidação de dados de comissionamento de vendas devido a dados nulos e formatos de data divergentes.
- Falta de uma fonte única da verdade para alimentar ferramentas de Business Intelligence (BI).

---

## ⚡ Solução Desenvolvida

Migração e refatoração completa da infraestrutura de agendamento de tarefas para **Apache Airflow (DAGs)**. Desenvolvemos pipelines de dados resilientes, idempotentes e monitorados que constroem as tabelas fatos e dimensões do Data Warehouse.

### 🌟 Destaques & Funcionalidades
- **Orquestração de Dados Profissional:** Centralização dos fluxos em DAGs com monitoramento visual de dependências, tratamento automático de falhas e alertas.
- **Ingestão Multi-Fonte & Pipelines ELT:** Ingestão de leads em formato JSON, propostas de crédito consignado multibancos (Santander, BV, etc.) e scraping robusto de mais de 6 portais de parceiros.
- **Mecanismos de Carga Idempotentes:** Scripts estruturados para garantir que reexecuções da mesma DAG não dupliquem dados no Data Warehouse.
- **Camada de Compartilhamento (`utils_core.py`):** Desenvolvimento de uma biblioteca interna reutilizável contendo gerenciadores de contexto (Context Managers) para conexões seguras de banco de dados, funções de log e utilitários de sanitização.

---

## 🏗️ Arquitetura do Ecossistema de Dados

```text
[ Data Sources ]       [ Ingestion & Orchestration ]       [ Transformation ]       [ Serving / DWH ]
                               (Apache Airflow)               (Python & SQL)

  APIs REST        ---+                      
  Marketplaces JSON---+--> raw_leads ------------+--> Limpeza & Joins (SQL)  --+--> PostgreSQL / MySQL
  Web Scraping     ---+--> raw_propostas --------|                         |   (Modelagem Star Schema)
  DBs Relacionais  ---+--> raw_repasses ---------+--> Validação (Pandas) ---+--> SQLite (Local Serving)
  Planilhas/CSVs   ---+--> raw_metas
```

---

## 🛠️ Tecnologias Utilizadas

- **Orquestração & Agendamento:** Apache Airflow 2.x (DAGs, PythonOperator, TaskFlow API, Task Groups)
- **Manipulação & Engenharia:** Python 3.x (Pandas, NumPy, SQLAlchemy, OpenPyXL)
- **Bancos de Dados & Armazenamento:** MySQL, PostgreSQL, SQLite
- **Transformação de Dados:** SQL Avançado (CTEs, Window Functions, Joins complexos, views materializadas)
- **Coleta de Dados (Scraping):** Selenium, Requests (Ingestão programada de portais de terceiros)

---

## 📊 Integração Downstream (Business Intelligence)

Os dados limpos e modelados nesta etapa de infraestrutura são a espinha dorsal que alimenta diretamente as soluções visuais de inteligência de negócios. As tabelas analíticas deste Data Warehouse abastecem:

1. **[Pipeline de Reconciliação Financeira de Comissões](../03-comissoes-remuneracao-variavel/README.md):** Alimentando painéis de conciliação de repasses com detecção automática de divergências.
2. **[Engine de Growth Analytics](../02-growth-marketing-analytics/README.md):** Viabilizando a geração de dashboards de funil de vendas, ROAS e safras (cohortes).

### Showcase dos Dashboards Alimentados:

#### 📈 Painel Geral de Growth Analytics
![Performance Geral de Growth](../imgs/resultado-geral.png)

#### 💸 Painel de Reconciliação por Convênios & Evolução de Receita
![Análise de Resultados por Convênio](../imgs/analise-resultado-convenio.png)
![Evolução de Comissões Mês a Mês](../imgs/mes-mes-analise-resultado.png)

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte interno, credenciais, URLs de APIs proprietárias e regras de negócio específicas foram omitidos ou mockados neste repositório visando proteção de propriedade intelectual e conformidade com a LGPD. O repositório atua estritamente como um portfólio de arquitetura e tecnologia.
