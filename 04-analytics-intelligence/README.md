# 🧠 Analytics & Lead Intelligence Engine

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

Motor analítico avançado focado na inteligência de dados, prospecção e modelagem preditiva para o mercado de crédito e serviços financeiros.

## 🎯 Problema de Negócio

No mercado de crédito, a taxa de conversão depende criticamente da qualidade do contato e do perfil do cliente. O negócio enfrentava os seguintes desafios:
- Falta de dados cadastrais atualizados, exigindo pesquisas manuais demoradas.
- Dificuldade em priorizar leads (clientes com maior propensão à compra).
- Esforço massivo na coleta de dados dispersos em portais bancários.
- Ausência de ferramentas para medir a efetividade das campanhas e lotes de forma rápida.

## ⚡ Solução Desenvolvida

Foi desenvolvido um **Lead Intelligence Engine** robusto que automatiza o fluxo de prospecção do começo ao fim: desde a coleta de informações até o escore preditivo de clientes.

### 🌟 Destaques & Funcionalidades
- **Motor de Enriquecimento:** `Enriquecer_app.py` e `clientes_enriquecer.py` realizam aumentos massivos de dados via APIs e web scraping.
- **Modelagem Preditiva:** Treinamento de modelos em Scikit-Learn (`treino_modelos.py`) de classificação e regressão para prever propensão a produtos de crédito consignado.
- **Análise de Efetividade:** Scripts de análise em lote e via app (`efetividade_app.py`) processando milhares de registros para calcular conversão de campanhas.
- **Info DB Analytics:** Sistema robusto (`Info_db_app.py`) com mais de 13 mil linhas para extração de insights gerenciais.
- **Framework de Scraping Avançado:** Módulos que substituem consultas manuais em portais e recuperam dados estruturados em tempo real.

## 🏗️ Arquitetura

```text
       [Fontes Iniciais]
        (Bases Locais)
              |
              v
  +-----------------------+      Web Scraping Avançado /
  | Motor de Enriquecim.  | <--- Integrações de APIs (REST)
  |  (clientes_enriquecer)|
  +-----------+-----------+
              |
              v
    +-------------------+        +----------------------+
    | Processamento Analítico |  |  Machine Learning  |
    | (Pandas / SQL / DBs)    |--| (Scikit-Learn)     |
    +---------+---------+        +----------------------+
              |                             |
              v                             v
   [Dashboards / Efetividade]      [Scoring / Priorização]
```

## 🛠️ Tecnologias Utilizadas

- **Linguagens & Frameworks:** Python, Pandas, Scikit-Learn
- **Coleta de Dados:** Selenium, Requests, BeautifulSoup, APIs REST
- **Bancos de Dados:** SQL (SQLite / Context Managers Customizados)
- **Machine Learning:** Modelos de classificação/regressão, Feature Engineering

## 📊 Impacto / Resultados / Métricas

- **Automação de Enriquecimento:** Eliminação de 100% da busca manual por dados cadastrais, acelerando a régua de relacionamento.
- **Lead Scoring (ML):** Aumento da assertividade das equipes de vendas, priorizando contatos com maior probabilidade de conversão.
- **Escalabilidade:** Processamento analítico em lote validado para dezenas de milhares de registros através do `efetividade_lote.py`.

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte interno, credenciais, URLs de APIs proprietárias e regras de negócio específicas foram omitidos ou mockados neste repositório visando proteção de propriedade intelectual e conformidade com a LGPD. O repositório atua estritamente como um portfólio de arquitetura e tecnologia.
