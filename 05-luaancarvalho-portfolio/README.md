# 🌐 Engine de Roteamento Analítico, Personalização Web & Web Analytics Tagging (PoC)

![PHP](https://img.shields.io/badge/PHP-777BB4?style=for-the-badge&logo=php&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)
![Google Analytics](https://img.shields.io/badge/GA4-E37400?style=for-the-badge&logo=googleanalytics&logoColor=white)

Prova de Conceito (PoC) de um website de portfólio profissional dinâmico estruturado para **Personalização de Experiência (CRO) e Tagging Analítico Avançado (Web Analytics)** via Server-Side Rendering (SSR).

---

## 🎯 Problema de Negócio

Profissionais que atuam na intersecção de dados e automação lidam com diferentes perfis de interlocutores: um recrutador técnico busca detalhes de arquitetura de dados (ETL, Airflow, SQL), enquanto um gerente de negócios busca resultados financeiros (LTV, CAC, automatizações). 

Apresentar um portfólio genérico e estático reduz o engajamento e a conversão do visitante (CRO). O desafio consistia em criar uma aplicação web única que adaptasse sua narrativa dinamicamente e rastreasse de ponta a ponta o comportamento do usuário para avaliar o interesse por tema.

---

## ⚡ Solução Desenvolvida

Um motor de personalização dinâmico em **PHP** que intercepta parâmetros de tráfego e ajusta a renderização do conteúdo (ordenando projetos, alterando palavras-chave e habilidades em destaque) no lado do servidor, associado a um plano de tags analíticas robusto no **Google Tag Manager & GA4**.

### 🌟 Destaques & Funcionalidades
- **🎯 Dynamic Profile Routing (Engine de Personalização):** Roteamento no PHP (`index.php`) interceptando query parameters (`?s=dados`, `?s=growth`, `?s=automacao`) para modificar dinamicamente a barra de skills e dar destaque prioritário aos projetos daquele perfil específico.
- **🏷️ Rastreamento Analítico Ponta a Ponta (Web Analytics):** Integração avançada de tags via GTM. Envio de eventos customizados para o Google Analytics 4 (GA4) mapeando scrolls de leitura (`IntersectionObserver` no JS), tempo de tela em cada seção e cliques nos estudos de caso de projetos.
- **⚡ Arquitetura Desacoplada de Dados Locais:** Estruturação das habilidades e dos projetos em arrays associativos (agindo como base de dados estruturada no backend) para que a lógica de ordenação e filtros analíticos seja limpa e modular.
- **🎨 UX/UI Otimizada com CSS Puro:** Implementação de layouts responsivos (CSS Grid/Flexbox), efeitos de Glassmorphism (efeito vidro transparente com blur) e transições suaves de Dark/Light mode sem peso de bibliotecas extras, mantendo o carregamento ultrarrápido (foco em métricas de Core Web Vitals para SEO).

---

## 🏗️ Arquitetura de Roteamento Dinâmico

```text
                     [ Acesso: /portfolio?s=dados ]
                                   |
                         +-------------------+
                         | Router Server PHP |
                         +---------+---------+
                                   |
             +---------------------+---------------------+
             |                                           |
    +--------+----------+                       +--------+----------+
    | Filtro de Skills  |                       | Ordenador de Case |
    | (prioriza dados)  |                       | (foco engenharia) |
    +--------+----------+                       +--------+----------+
             |                                           |
             +---------------------+---------------------+
                                   |
                         +---------v---------+
                         | View SSR + Tagging| ---> [ Cliques/Scrolls ]
                         | (GTM / GA4 Setup) |      (Eventos customizados)
                         +-------------------+
```

---

## 🛠️ Tecnologias Utilizadas

- **Backend / Router:** PHP 8+ (Processamento de variáveis de query string, SSR de blocos condicionais)
- **Frontend Core:** HTML5 Semântico, CSS3 (Custom Properties para temas, CSS Grid, Flexbox)
- **Interatividade & Tracking:** JavaScript Moderno (IntersectionObserver API, DataLayer Pushes)
- **Servidor:** Apache (`.htaccess` para reescrita e limpeza de rotas URL)
- **Web Analytics:** Google Analytics 4 (GA4), Google Tag Manager (GTM), UTM parameters mapping

---

## 📊 Aplicação das Competências de Analytics

Este projeto demonstra a habilidade prática do profissional em **não apenas consumir dados estruturados, mas também projetar e implementar a própria coleta de dados na ponta (Front-end Tagging & Tracking Architecture)**. 

Ao mapear a entrada de tráfego (UTMs), o comportamento de navegação (cliques e scrolls) e conectar esses dados ao GA4, demonstra-se a capacidade técnica de criar o fluxo de dados do zero absoluta, garantindo a qualidade da informação de Growth Marketing desde o seu nascimento.

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte deste portfólio web foi adaptado para fins de demonstração arquitetural, omitindo chaves de acompanhamento específicas.
