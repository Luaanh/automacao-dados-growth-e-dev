WITH primeira_compra AS (
    SELECT
        cliente_id,
        MIN(data_contrato) AS data_primeira_compra
    FROM producao_cadastro_unico
    GROUP BY cliente_id
),
base AS (
    SELECT
        p.cliente_id,
        DATE_FORMAT(pc.data_primeira_compra, '%Y-%m') AS safra,
        TIMESTAMPDIFF(
            MONTH,
            pc.data_primeira_compra,
            p.data_contrato
        ) AS idade_meses,
        p.valor_comissao
    FROM producao_cadastro_unico p
    INNER JOIN primeira_compra pc
        ON p.cliente_id = pc.cliente_id
),
safra_resumo AS (
    SELECT
        safra,
        idade_meses,
        COUNT(DISTINCT cliente_id) AS clientes,
        SUM(valor_comissao) AS receita

    FROM base

    GROUP BY
        safra,
        idade_meses
)
SELECT
    safra,
    CONCAT('M', idade_meses) AS mes,
    idade_meses,
    clientes,
    receita
FROM safra_resumo
ORDER BY
    safra,
    idade_meses;