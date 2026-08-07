WITH base_calculada AS (
    SELECT
        p.segurado,
        p.cpfcnpj_do_cliente,
        p.data_da_operacao,
        m.primeira_parcela_devedora,
        (
            (2026 - YEAR(STR_TO_DATE(p.data_da_operacao, '%d/%m/%Y'))) * 12
            + (5 - MONTH(STR_TO_DATE(p.data_da_operacao, '%d/%m/%Y')))
            + 1
        ) AS parcela_esperada,
        ps.telefone_venda
    FROM comissao_seguro_auto p
    INNER JOIN (
        SELECT
            cpfcnpj_do_cliente,
            MIN(CAST(SUBSTRING_INDEX(parcela, '/', 1) AS UNSIGNED)) AS primeira_parcela_devedora
        FROM comissao_seguro_auto
        WHERE status = 'PENDENTE PAGAMENTO'
        GROUP BY cpfcnpj_do_cliente
    ) m
        ON p.cpfcnpj_do_cliente = m.cpfcnpj_do_cliente
    LEFT JOIN producao_seguros ps
        ON ps.cliente_id = m.cpfcnpj_do_cliente
    GROUP BY
        p.segurado,
        p.cpfcnpj_do_cliente,
        p.data_da_operacao,
        m.primeira_parcela_devedora,
        ps.telefone_venda
)

SELECT
    segurado,
    cpfcnpj_do_cliente,
    data_da_operacao,
    primeira_parcela_devedora,
    parcela_esperada,
    CASE
        WHEN primeira_parcela_devedora > parcela_esperada THEN 'Em Dia'
        WHEN primeira_parcela_devedora = parcela_esperada THEN '1 Parcela Atrasada (Mês Atual)'
        WHEN primeira_parcela_devedora < parcela_esperada THEN CONCAT(
            (parcela_esperada - primeira_parcela_devedora) + 1,
            ' Parcelas Atrasadas'
        )
    END AS situacao_do_cliente,
    telefone_venda
FROM base_calculada;