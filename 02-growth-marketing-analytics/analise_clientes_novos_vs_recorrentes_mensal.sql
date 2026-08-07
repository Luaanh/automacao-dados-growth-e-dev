WITH contratos AS (
    SELECT DISTINCT cliente_id, data_contrato
    FROM producao
    WHERE data_cancelamento IS NULL
    UNION ALL
    SELECT DISTINCT cliente_id, data_contrato
    FROM producao_cadastro_unico
    WHERE data_cancelamento IS NULL
    UNION ALL
    SELECT DISTINCT cliente_id, data_contrato
    FROM producao_fgts
    WHERE data_cancelamento IS NULL
    UNION ALL
    SELECT DISTINCT cliente_id, data_contrato
    FROM producao_banco_consig
    WHERE data_cancelamento IS NULL
    UNION ALL
    SELECT DISTINCT
        cliente_id,
        data_cartao AS data_contrato
    FROM producao_cartao
    WHERE data_cancelamento IS NULL
    UNION ALL
    SELECT DISTINCT cliente_id, data_contrato
    FROM producao_cp
    WHERE data_cancelamento IS NULL

),
primeiros_contratos AS (
    SELECT
        cliente_id,
        MIN(data_contrato) AS primeira_data
    FROM contratos
    GROUP BY cliente_id
)
SELECT
    DATE_FORMAT(c.data_contrato, '%Y-%m') AS mes_ano,
    COUNT(DISTINCT CASE
        WHEN DATE(c.data_contrato) = DATE(pc.primeira_data)
        THEN c.cliente_id
    END) AS contagem_novos,
    COUNT(DISTINCT CASE
        WHEN c.data_contrato > pc.primeira_data
        THEN c.cliente_id
    END) AS contagem_recorrentes,
    COUNT(DISTINCT CASE
        WHEN DATE(c.data_contrato) = DATE(pc.primeira_data)
        THEN c.cliente_id
    END) * 1.0
    / COUNT(DISTINCT c.cliente_id) AS proporcao_novos,
    COUNT(DISTINCT CASE
        WHEN c.data_contrato > pc.primeira_data
        THEN c.cliente_id
    END) * 1.0
    / COUNT(DISTINCT c.cliente_id) AS proporcao_recorrentes
FROM contratos c
INNER JOIN primeiros_contratos pc
    ON c.cliente_id = pc.cliente_id
GROUP BY
    mes_ano
ORDER BY
    mes_ano;