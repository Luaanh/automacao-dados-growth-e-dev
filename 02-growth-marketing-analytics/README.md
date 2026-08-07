# 🎯 Engine de Growth Analytics, Atribuição de Funil & Automação via Apache Airflow

![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-Orchestration-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)
![Python](https://img.shields.io/badge/Python-Analytics-3776AB?style=flat-square&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-Advanced_Queries-4479A1?style=flat-square&logo=postgresql&logoColor=white)
![Google Analytics 4](https://img.shields.io/badge/GA4-Tracking-E37400?style=flat-square&logo=googleanalytics&logoColor=white)
![Google Tag Manager](https://img.shields.io/badge/GTM-Event_Tracking-246FDB?style=flat-square&logo=googletagmanager&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-Automation-FF6D5A?style=flat-square&logo=n8n&logoColor=white)

Solução de Growth & Marketing Analytics orquestrada via **Apache Airflow**, focada na atribuição multi-canal de leads, otimização de funil comercial, análise de cohortes de retenção e automação de fluxos operacionais de atendimento.

---

## 🎯 Problema de Negócio

Empresas com múltiplas origens de tráfego (Google Ads, Meta Ads, orgânico e indicações) frequentemente enfrentam cegueira de atribuição (não sabendo qual canal gera rentabilidade real), alto tempo de espera de resposta ao lead e distribuição ineficiente do orçamento de marketing.

---

## ⚡ Solução Desenvolvida

Implementação de um ecossistema orquestrado pelo **Apache Airflow (DAG `growth_analytics_ecoagile_pipeline`)**, substituindo rotinas baseadas em loops e agendadores locais por pipelines robustos com rastreamento via **GTM/GA4**, modelos de atribuição em **SQL**, esteiras de automação de lead scoring via **n8n** e análises estatísticas de **Cohortes** e **Unit Economics (CAC, LTV, ROI, ROAS)** em Python.

### 🌟 Destaques & Funcionalidades

- **⚙️ Orquestração Enterprise no Airflow:** Execução programada a cada 15 minutos de tarefas encadeadas (`processar_arquivos >> calcular_cohorts >> notificar_n8n`), garantindo resiliência, logs centralizados e relances automáticos em falhas de rede.
- **🎯 Rastreamento & Atribuição Multi-Canal:** Configuração de disparos de eventos de formulário e cliques via GTM/GA4 integrados ao CRM via SQL, mapeando a jornada completa do lead desde a origem (UTMs) até a conversão (MQL ➔ SQL ➔ Venda).
- **📊 Análise de Cohortes & Retenção:** Tasks no Airflow para cálculo de taxas de retenção, recompra e comportamento de clientes em janelas de 12 a 24 meses.
- **⚡ Automação de Funil via n8n & WhatsApp API:** Workflows de distribuição automatizada de leads para corretores em menos de 1 minuto, acionados via webhooks após atualização das DAGs.
- **💰 Unit Economics & Rentabilidade:** Estruturação de relatórios e projeções de Breakeven, Ticket Médio, ROI/ROAS e relação LTV/CAC por carteira e produto.

---

## 🏗️ Workflow da DAG no Apache Airflow

```
┌───────────────────────────────────────────────────────────────────┐
│               DAG Airflow (`growth_analytics_pipeline`)           │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────┐
 │ Task 1: processar_arquivos_leads                                │
 │ (Ingestão de réguas, veículos, seguros e no-sold)               │
 └────────────────────────────────┬────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────┐
 │ Task 2: calcular_cohorts_retencao                               │
 │ (Análise estatística de retenção 12/24 meses em Python)         │
 └────────────────────────────────┬────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────┐
 │ Task 3: notificar_webhooks_n8n                                  │
 │ (Gatilhos automatizados para réguas de atendimento no WhatsApp) │
 └─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack de Tecnologias

- **Orquestrador:** Apache Airflow 2.x (DAGs, PythonOperator)
- **Analytics & Tracking:** Google Analytics 4 (GA4), Google Tag Manager (GTM), UTM Parameterization
- **Automação & Growth Ops:** n8n, Webhooks, WhatsApp Cloud API, REST APIs
- **Linguagens & Consultas:** SQL (Window Functions, CTEs, Agrupamentos de Funil), Python (Pandas, Statsmodels)
- **Visualização:** Power BI & Metabase

---

## 📊 Métricas & Resultados Alcançados

- 🎯 **Relação LTV/CAC > 7x:** Identificação e priorização de canais com LTV médio de **~R$ 1.200** e CAC médio de **~R$ 170**.
- ⚡ **Redução de 80% no Tempo de Resposta:** Lead distribuído e abordado pelo vendedor em média de **10 minutos** (antigos 50 minutos).
- 📈 **Otimização de ROI:** Realocação eficiente do orçamento de tráfego baseada em margem real e não apenas em volume de cadastros.

---

> *Nota: Os datasets e relatórios apresentados neste repositório utilizam dados sintéticos para demonstração das metodologias analíticas.*
