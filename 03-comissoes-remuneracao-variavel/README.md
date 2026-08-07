# 🔄 Pipeline ETL Automatizado & Reconciliação Financeira de Comissões via Apache Airflow

![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-Orchestration-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-ETL-150458?style=flat-square&logo=pandas&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Advanced-4479A1?style=flat-square&logo=sqlite&logoColor=white)
![Power BI](https://img.shields.io/badge/Power_BI-Dashboards-F2C811?style=flat-square&logo=powerbi&logoColor=black)

Pipeline de Engenharia de Dados orquestrado via **Apache Airflow (DAGs)** em Python e SQL para extração, limpeza, conciliação e reconciliação automatizada de repasses financeiros e comissões provenientes de múltiplas fontes heterogêneas.

---

## 🎯 Problema de Negócio

Discrepâncias entre os valores previstos de comissão (registrados no CRM/ERP) e os valores efetivamente pagos pelas instituições parceiras geravam retrabalho manual massivo, vulnerabilidade a perdas financeiras e atraso na consolidação dos relatórios para a diretoria.

---

## ⚡ Solução Desenvolvida

Construção de uma solução automatizada em Python (Pandas) e SQL orquestrada por **DAGs no Apache Airflow**, que consolida dados de **4 fontes distintas** (banco do CRM, banco do ERP, banco local SQLite/MySQL e relatórios em planilhas Excel/CSV), executando validações cruzadas, retentativas automáticas e alimentando um Dashboard Executivo no Power BI.

### 🌟 Destaques & Funcionalidades

- **⚙️ Orquestração com Apache Airflow:** DAGs configuradas com agendamento diário, controle de dependências entre tarefas (`extrair >> reconciliar >> exportar`), políticas de retry (`retries=2`) e monitoramento centralizado.
- **📥 Ingestão & Limpeza Multi-Fonte:** Módulos de sanitização de dados com regex e regras para tratamento de datas, valores numéricos, caracteres especiais e chaves nulas.
- **⚖️ Motor de Conciliação e Reconciliação:** Algoritmo que cruza registros operacionais com relatórios de repasse financeiro para identificar divergentemente:
  - Comissões pagas a menor ou a maior;
  - Operações pagas sem registro no CRM;
  - Status de propostas não atualizadas.
- **📆 Tratamento de Calendário de Negócios:** Integração com bibliotecas de feriados nacionais (`holidays`) e dias úteis para cálculo preciso de datas de repasse (`D+0`, `D+1`).
- **📊 Exportação e Integração BI:** Geração automática de tabelas higienizadas para consumo direto por modelos dimensionais no Power BI (DAX / Power Query).

---

## 🏗️ Arquitetura do Pipeline no Apache Airflow

```
 ┌───────────────────────────────────────────────────────────────────┐
 │                   DAG Apache Airflow (`etl_comissoes`)            │
 └─────────────────────────────────┬─────────────────────────────────┘
                                   │
  ┌────────────────────────────────▼────────────────────────────────┐
  │  Task 1: extrair_dados_multi_fonte                              │
  │  (CRM Database, ERP Database, Local SQLite, Planilhas Excel)    │
  └────────────────────────────────┬────────────────────────────────┘
                                   │
  ┌────────────────────────────────▼────────────────────────────────┐
  │  Task 2: reconciliar_e_sanitizar_comissoes                      │
  │  (Engine ETL Python Pandas / Reconciliação Cruzada de Valores)  │
  └────────────────────────────────┬────────────────────────────────┘
                                   │
  ┌────────────────────────────────▼────────────────────────────────┐
  │  Task 3: exportar_tabelas_powerbi                               │
  │  (Data Warehouse Final & Dashboards Power BI)                   │
  └─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tecnologias Utilizadas

- **Orquestrador:** Apache Airflow 2.x (DAGs, PythonOperator)
- **Linguagem:** Python 3.x
- **Manipulação de Dados:** Pandas, NumPy, OpenPyXL
- **Banco de Dados & SQL:** MySQL, PostgreSQL, SQLite, SQLAlchemy
- **Visualização de Dados:** Power BI (Modelagem Star Schema, DAX, Power Query)

---

## 📈 Resultados De Impacto

- ⏱️ **-91% no Tempo de Processamento:** Consolidação financeira reduzida de **2 horas para apenas 10 minutos**.
- ⌛ **100+ Horas Mensais Salvas:** Eliminação total de cruzamentos manuais via PROCV em planilhas.
- 🎯 **100% de Confiabilidade:** Zero margem de erro na identificação de comissões não pagas ou divergentes.

---

> *Nota: Dados sensíveis, nomes de clientes e chaves de acesso foram completamente anonimizados.*
