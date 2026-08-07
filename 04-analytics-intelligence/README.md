# 🧠 Predictive Analytics, AI Automation & Lead Intelligence Engine

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

Motor analítico avançado focado em **inteligência cadastral de leads, enriquecimento automatizado de dados (Data Quality) e modelagem estatística preditiva (Machine Learning)** para otimização de conversão no mercado financeiro.

---

## 🎯 Problema de Negócio

No mercado de crédito e serviços financeiros, a eficiência comercial é altamente sensível à qualidade dos dados cadastrais (telefones válidos, e-mails, dados empregatícios) e à capacidade de prever quais leads possuem real interesse e aderência.

A operação enfrentava gargalos cruciais:
- **Dados Cadastrais Desatualizados:** Elevado tempo gasto por operadores buscando informações adicionais de clientes manualmente em portais públicos e privados.
- **Falta de Priorização Inteligente:** Lista de leads abordada de forma sequencial linear, gastando tempo com contatos frios (baixa propensão) e demorando para acionar os leads mais quentes.
- **Falta de Métricas de Efetividade:** Dificuldade em analisar a performance real de conversão de grandes lotes de campanhas de forma rápida e parametrizada.

---

## ⚡ Solução Desenvolvida

Desenvolvimento de um **Lead Intelligence & Analytics Engine** em Python, que integra rotinas inteligentes de enriquecimento de dados por automação (Web Scraping / APIs REST), modelos preditivos de classificação para Lead Scoring e relatórios estatísticos de conversão em lote.

### 🌟 Destaques & Funcionalidades
- **🤖 Motor de Enriquecimento Automatizado:** Os scripts `Enriquecer_app.py` e `clientes_enriquecer.py` automatizam a coleta de dados e sanitização cadastral a partir de consultas programadas (via Selenium headless e requisições HTTP), atualizando telefones e indicadores no banco de dados SQLite local de forma massiva.
- **🔮 Modelagem Preditiva (Machine Learning):** O módulo [`treino_modelos.py`](./utils_analytics.py) treina algoritmos em **Scikit-Learn** (como Decision Trees, Random Forests ou Regressões Logísticas), utilizando técnicas de Feature Engineering para atribuir um escore de propensão de compra a cada cliente da base.
- **📊 Análise de Conversão de Campanhas em Lote:** O script `efetividade_app.py` e rotinas de lote calculam estatísticas de efetividade comercial de campanhas de telemarketing, automatizando o agrupamento de contatos e gerando visões claras de conversão por carteira de clientes.
- **📈 Engine de Relatórios Info DB:** Módulo robusto de consulta local (`Info_db_app.py`) contendo lógica para busca ágil de insights cruzados de clientes e métricas gerenciais.

---

## 🏗️ Fluxo do Motor de Inteligência

```text
       [ Leads Brutos ]
        (Bases Locais)
               |
               v
   +-----------------------+      Web Scraping Automatizado /
   | Motor de Enriquecim.  | <--- Integração via APIs REST
   | (clientes_enriquecer) |      (Telefones / Cadastros Atualizados)
   +-----------+-----------+
               |
               v
     +-------------------+        +----------------------------+
     | Processamento &   |        |   Modelos de Propensão     |
     | Tratamento Pandas |------->|  (Scikit-Learn ML Training)|
     +---------+---------+        +--------------+-------------+
               |                                 |
               v                                 v
   [ Estatísticas de Lotes ]             [ Lead Scoring / ]
    (efetividade_app.py)                 (Priorização do Funil)
```

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem & Bibliotecas:** Python 3.x, Pandas, NumPy
- **Inteligência Artificial & Estatística:** Scikit-Learn (Classificação, Regressão, Feature Engineering, Validação)
- **Extração & Automação Web:** Selenium WebDriver, Requests, BeautifulSoup (Scrapers customizados)
- **Armazenamento Local & SQL:** MySQL Local

---

## 📊 Impacto & Resultados de Negócio

- **Automação Cadastral Completa:** Eliminação do tempo operacional de pesquisa de telefones manuais, gerando dados de qualidade com economia direta de tempo.
- **Eficácia de Abordagem (Lead Scoring):** Ao priorizar os leads classificados no topo do score preditivo pelo modelo de ML, o time comercial direciona esforços aos clientes com maior probabilidade de conversão.
- **Visibilidade de Performance:** Capacidade de gerar análises de efetividade de campanhas de dezenas de milhares de leads em segundos com o script de lote analítico.

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte interno, credenciais, URLs de APIs proprietárias e regras de negócio específicas foram omitidos ou mockados neste repositório visando proteção de propriedade intelectual e conformidade com a LGPD.
