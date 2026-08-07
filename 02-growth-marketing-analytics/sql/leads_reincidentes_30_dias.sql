WITH leads_ranqueados AS (
    SELECT 
        nc.id,
        nc.telefone,
        nc.nome,
        nc.data_chegada,
        nc.valor,
        nc.ano,
        nc.tipo_envio,
        COUNT(nc.id) OVER (PARTITION BY nc.telefone) AS qtd_total_historico,
        ROW_NUMBER() OVER (PARTITION BY nc.telefone ORDER BY nc.data_chegada DESC, nc.id DESC) AS rn,
        LEAD(nc.data_chegada) OVER (PARTITION BY nc.telefone ORDER BY nc.data_chegada DESC, nc.id DESC) AS data_simulacao_anterior
    FROM portal.negociacao_cockpit nc
    WHERE nc.telefone IS NOT NULL AND nc.telefone <> ''
)
SELECT 
    id,
    telefone,
    nome,
    data_chegada AS data_ultima_simulacao,
    data_simulacao_anterior,
    DATEDIFF(data_chegada, data_simulacao_anterior) AS diferenca_dias,
    qtd_total_historico,
    valor,
    ano,
    CASE WHEN valor BETWEEN 30000 AND 60000 THEN 1 ELSE 0 END AS flag_30k_60k,
    CASE WHEN LEFT(ano, 4) >= '2016' THEN 1 ELSE 0 END AS flag_pos_2016
FROM leads_ranqueados
WHERE rn = 1
  AND qtd_total_historico > 1
  AND tipo_envio = 'CRM'
  AND data_chegada >= CURRENT_DATE - INTERVAL 30 DAY
ORDER BY data_chegada DESC;