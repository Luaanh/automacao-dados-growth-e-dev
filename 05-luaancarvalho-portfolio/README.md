# 🌐 Portfolio Web Dinâmico & Profile Routing

![PHP](https://img.shields.io/badge/PHP-777BB4?style=for-the-badge&logo=php&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)
![Google Analytics](https://img.shields.io/badge/GA4-E37400?style=for-the-badge&logo=googleanalytics&logoColor=white)

Website de portfólio profissional e dinâmico, renderizado no lado do servidor (SSR), capaz de adaptar seu conteúdo automaticamente para diferentes perfis de recrutadores (Engenharia de Dados, Desenvolvimento, Growth, etc).

## 🎯 Problema de Negócio

Profissionais multidisciplinares possuem dificuldade em apresentar um currículo/portfólio focado. Um recrutador buscando um Engenheiro de Dados não quer ler primariamente sobre Frontend, e vice-versa. 
O desafio era construir um portfólio único, otimizado para SEO, que adaptasse o discurso e o destaque dos projetos baseando-se no interesse de quem o acessa.

## ⚡ Solução Desenvolvida

Um portfólio web construído em **PHP** (`index.php`), utilizando um sistema de Dynamic Routing via query parameters (`?s=dev`, `?s=dados`, etc.).

### 🌟 Destaques & Funcionalidades
- **Dynamic Profile Routing:** O herói do site, as barras de skills e a ordenação dos projetos mudam conforme a URL que o recrutador acessa.
- **Design Moderno:** Implementação de Dark Mode, efeitos de Glassmorphism, e animações de scroll revelando os elementos gradativamente (via `IntersectionObserver`).
- **Arquitetura de Dados:** Separação lógica entre UI e conteúdo. As skills e os case studies de projetos estão estruturados como bases de dados locais no PHP, facilitando manutenção.
- **Estudos de Caso Aprofundados:** Páginas detalhadas de projetos (`projeto-crm.php`, `projeto-data-viz.php`) destacando desafio, solução técnica e métricas.
- **SEO & Tracking:** Reescrevimento de URLs amigáveis (`.htaccess`), Server-Side Rendering (SSR) e monitoramento comportamental via Google Analytics 4 (GA4) / Tag Manager (GTM).

## 🏗️ Arquitetura

```text
                         [ URL: /portfolio?s=dados ]
                                      |
                           +----------------------+
                           |  Router Dinâmico PHP |
                           +----------------------+
                                      |
               +----------------------+----------------------+
               |                                             |
    +-------------------+                           +-------------------+
    | Skills Engine     |                           | Projects Engine   |
    | (Filtra Data Eng.)|                           | (Prioriza Dados)  |
    +-------------------+                           +-------------------+
               |                                             |
               +----------------------+----------------------+
                                      |
                           +----------------------+
                           |  View Engine (HTML)  |
                           |  CSS3 Glassmorphism  |
                           |  JS Scroll Reveal    |
                           +----------------------+
```

## 🛠️ Tecnologias Utilizadas

- **Backend:** PHP 8+ (Server-Side Rendering e Lógica de roteamento)
- **Frontend Core:** HTML5 Semântico, CSS3 (Custom Properties, Flexbox, CSS Grid)
- **Interatividade UI:** JavaScript puro (IntersectionObserver, Event Listeners)
- **Servidor:** Apache (`.htaccess` para reescrita de URL amigável)
- **Tracking / Analytics:** Google Analytics 4 (GA4) e Google Tag Manager (GTM)
- **Tipografia:** Google Fonts (Inter e Montserrat)

## 📊 Impacto / Resultados / Métricas

- **Engajamento Específico:** Direcionamento inteligente da atenção do recrutador, aumentando as chances de match com as vagas enviando o link correto.
- **Performance e SEO:** Renderização SSR que garante rápida indexação pelos motores de busca (Lighthouse com excelente pontuação).
- **Métricas Comportamentais:** Capacidade de acompanhar exatamente quais páginas e projetos os visitantes dedicam mais tempo lendo.

---

> 🔒 **Nota de Segurança e Privacidade:** O código-fonte interno, credenciais, URLs de APIs proprietárias e regras de negócio específicas foram omitidos ou mockados neste repositório visando proteção de propriedade intelectual e conformidade com a LGPD. O repositório atua estritamente como um portfólio de arquitetura e tecnologia.
