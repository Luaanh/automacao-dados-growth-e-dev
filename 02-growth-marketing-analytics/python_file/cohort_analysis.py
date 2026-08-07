import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import utils_core
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')
def normalizar_telefone(numero):
    if pd.isna(numero):
        return None
    numero = ''.join(filter(str.isdigit, str(numero)))
    if not numero:
        return None
    return numero
def remover_terceiro_nove(numero):
    if numero is None:
        return None
    if len(numero) >= 11 and numero[2] == '9':
        return numero[:2] + numero[3:]
    return numero
def classificar_bucket(x):
    if pd.isna(x): return None
    if x < 0: return '<D0'
    if x == 0: return 'D0'
    if x == 1: return 'D1'
    if x == 2: return 'D2'
    if x == 3: return 'D3'
    if x == 4: return 'D4'
    if x == 5: return 'D5'
    return 'D6+'
def classificar_dia_50(x):
    if pd.isna(x): return None
    if x < 0: return '<D0_50m'
    if x == 0: return 'D0_50m'
    if x == 1: return 'D1_50m'
    if x == 2: return 'D2_50m'
    return 'D3+_50m'

def classificar_dia_100(x):
    if pd.isna(x): return None
    if x < 0: return '<D0_100m'
    if x == 0: return 'D0_100m'
    if x == 1: return 'D1_100m'
    if x == 2: return 'D2_100m'
    return 'D3+_100m'

query_crm = """
    SELECT
        a.id AS atendimento_id,
        a.contato_id,
        cc.contato,
        primeiro_out_sistema.data_out_sistema AS data_inicio,
        COALESCE(w.mensagem,0) AS total_mensagens,
        crm_etiq.etiqueta_id
    FROM crm_atendimentos a
    JOIN contato_cliente cc ON cc.id = a.contato_id

    LEFT JOIN (
        SELECT atendimento_id, COUNT(*) AS mensagem
        FROM crm_whatsapp
        GROUP BY atendimento_id
    ) w ON w.atendimento_id = a.id

    LEFT JOIN (
        SELECT atendimento_id, MIN(criado_em) AS data_out_sistema
        FROM crm_whatsapp
        WHERE direcao = 'out'
        AND (tipo <> 'aviso' OR tipo IS NULL)
        GROUP BY atendimento_id
    ) primeiro_out_sistema ON primeiro_out_sistema.atendimento_id = a.id

    LEFT JOIN (
        SELECT ce.contato_id, ce.etiqueta_id
        FROM crm_contato_etiquetas ce
        INNER JOIN (
            SELECT contato_id, MAX(data_etiqueta) AS max_id
            FROM crm_contato_etiquetas
            WHERE etiqueta_id IN (30,20,15)
            GROUP BY contato_id
        ) x ON x.max_id = ce.data_etiqueta
    ) crm_etiq ON crm_etiq.contato_id = a.contato_id

    WHERE primeiro_out_sistema.data_out_sistema IS NOT NULL;
"""

with utils_core.Database('APP_DB') as conn:
    crm = pd.read_sql(query_crm, conn)
print("CRM:", len(crm))
query_cockpit = """
    SELECT
        nc.id, nc.telefone, nc.data_chegada, nc.data_insercao,
        nc.ano, nc.valor, nc.tipo_veiculo, nc.classificacao_ticket,
        nc.estado, nc.genero, ipc.semelhanca, ipc.data_nascimento, nc.canal
    FROM negociacao_cockpit nc
    LEFT JOIN info_panorama_cockpit ipc ON ipc.negociacao_id = nc.id
    WHERE nc.telefone IS NOT NULL
"""
with utils_core.Database('APP_DB_PORTAL') as conn:
    cockpit = pd.read_sql(query_cockpit, conn)
print("COCKPIT:", len(cockpit))
query_producao = """
    SELECT 
        c.celular AS telefone_cliente,
        p.valor_veiculo,
        p.valor_comissao,
        p.comissao_estimada_total,
        p.comissao_agente
    FROM producao_fin_banco p
    JOIN clientes c ON c.id = p.cliente_id
    WHERE p.origem_venda = 'CAMPANHA' 
    AND p.data_cancelamento IS NULL;
"""
with utils_core.Database('APP_DB') as conn:
    producao = pd.read_sql(query_producao, conn)
print("PRODUÇÃO:", len(producao))
crm['telefone'] = crm['contato'].apply(normalizar_telefone)
cockpit['telefone'] = cockpit['telefone'].apply(normalizar_telefone)
producao['telefone'] = producao['telefone_cliente'].apply(normalizar_telefone)
crm['telefone_sem9'] = crm['telefone'].apply(remover_terceiro_nove)
cockpit['telefone_sem9'] = cockpit['telefone'].apply(remover_terceiro_nove)
producao['telefone_sem9'] = producao['telefone'].apply(remover_terceiro_nove)
crm['data_inicio'] = pd.to_datetime(crm['data_inicio'])
cockpit['data_chegada'] = pd.to_datetime(cockpit['data_chegada'])
cockpit = cockpit.sort_values(['telefone', 'data_chegada', 'data_insercao'], ascending=[True, False, False])
cockpit = cockpit.drop_duplicates(subset=['telefone'], keep='first')
producao_consolidada = producao.groupby('telefone', as_index=False).agg(receita_total=('valor_comissao', 'sum'))
producao_consolidada_sem9 = producao.groupby('telefone_sem9', as_index=False).agg(receita_total=('valor_comissao', 'sum'))
colunas_cockpit = [
    'telefone', 'data_chegada', 'ano', 'valor', 'tipo_veiculo', 
    'classificacao_ticket', 'estado', 'genero', 'semelhanca', 'data_nascimento','canal'
]
match1 = crm.merge(cockpit[colunas_cockpit], how='left', on='telefone')
sem_match = match1['data_chegada'].isna()
colunas_cockpit_sem9 = [col for col in colunas_cockpit if col != 'telefone'] + ['telefone_sem9']
match2 = crm.loc[sem_match].merge(cockpit[colunas_cockpit_sem9], how='left', on='telefone_sem9')
for col in colunas_cockpit:
    if col != 'telefone':
        match1.loc[sem_match, col] = match2[col].values
resultado = match1[match1['data_chegada'].notna()].copy()
resultado = resultado.merge(producao_consolidada, how='left', on='telefone')
sem_receita = resultado['receita_total'].isna()
if sem_receita.any():
    match_receita_sem9 = resultado.loc[sem_receita, ['telefone_sem9']].merge(
        producao_consolidada_sem9, how='left', on='telefone_sem9'
    )
    resultado.loc[sem_receita, 'receita_total'] = match_receita_sem9['receita_total'].values
resultado['receita_total'] = resultado['receita_total'].fillna(0)
print("Encontrados no funil completo:", len(resultado))
resultado['mais_50'] = resultado['total_mensagens'] >= 50
resultado['mais_100'] = resultado['total_mensagens'] >= 100
resultado['mais_200'] = resultado['total_mensagens'] >= 200
resultado['converteu_etiqueta'] = resultado['etiqueta_id'].notna()
resultado['dias_desde_chegada'] = (resultado['data_inicio'].dt.normalize() - resultado['data_chegada'].dt.normalize()).dt.days
resultado['bucket'] = resultado['dias_desde_chegada'].apply(classificar_bucket)
resultado['bucket_50'] = np.where(resultado['mais_50'], resultado['dias_desde_chegada'].apply(classificar_dia_50), None)
resultado['bucket_100'] = np.where(resultado['mais_100'], resultado['dias_desde_chegada'].apply(classificar_dia_100), None)
resultado['ano'] = pd.to_numeric(resultado['ano'].astype(str).str.split('/').str[0], errors='coerce')
resultado['valor'] = pd.to_numeric(resultado['valor'], errors='coerce')
resultado['semelhanca'] = pd.to_numeric(resultado['semelhanca'], errors='coerce')
resultado['data_nascimento'] = pd.to_datetime(resultado['data_nascimento'], errors='coerce')
resultado['idade'] = np.floor((resultado['data_chegada'] - resultado['data_nascimento']).dt.days / 365.25)
bins_ano = [1900, 2005, 2010, 2015, 2020, 2026]
labels_ano = ['< 2005', '2006-2010', '2011-2015', '2016-2020', '2021-2026']
resultado['cat_ano'] = pd.cut(resultado['ano'], bins=bins_ano, labels=labels_ano)
bins_valor = [0, 30000, 60000, 100000, 150000, 250000, np.inf]
labels_valor = ['Ate 30k', '30k-60k', '60k-100k', '100k-150k', '150k-250k', '> 250k']
resultado['cat_valor'] = pd.cut(resultado['valor'], bins=bins_valor, labels=labels_valor)
bins_idade = [17, 25, 35, 45, 55, 65, 120]
labels_idade = ['18-25', '26-35', '36-45', '46-55', '56-65', '> 65']
resultado['cat_idade'] = pd.cut(resultado['idade'], bins=bins_idade, labels=labels_idade)
bins_semelhanca = [-1, 30, 60, 80, 95, 100]
labels_semelhanca = ['0-30', '31-60', '61-80', '81-95', '96-100']
resultado['cat_semelhanca'] = pd.cut(resultado['semelhanca'], bins=bins_semelhanca, labels=labels_semelhanca)
total_atendimentos_base = len(resultado)
tx_global_50 = max(resultado['mais_50'].sum() / total_atendimentos_base, 1e-9)
tx_global_100 = max(resultado['mais_100'].sum() / total_atendimentos_base, 1e-9)
tx_global_200 = max(resultado['mais_200'].sum() / total_atendimentos_base, 1e-9)
tx_global_etiqueta = max(resultado['converteu_etiqueta'].sum() / total_atendimentos_base, 1e-9)
atributos_analise = ['cat_ano', 'cat_valor', 'tipo_veiculo', 'classificacao_ticket', 'estado', 'cat_idade', 'cat_semelhanca', 'genero', 'canal']
print("\n\n" + "#" * 100)
print(" INICIANDO ESTUDO DE MENSAGENS E RECEITA POR ATRIBUTOS")
print("#" * 100)
with pd.ExcelWriter('matrizes_unica_lift_e_receita.xlsx', engine='openpyxl') as writer_interacao:
    for attr in atributos_analise:
        nome_exibicao = attr.replace('cat_', '').upper()
        print(f"\n==========================================================")
        print(f" ANÁLISE POR: {nome_exibicao}")
        print(f"==========================================================")
        
        df_agrupado = resultado.groupby(attr, dropna=False).agg(
            volume=('atendimento_id', 'count'),
            casos_50=('mais_50', 'sum'),
            casos_100=('mais_100', 'sum'),
            casos_200=('mais_200', 'sum'),
            casos_etiqueta=('converteu_etiqueta', 'sum'),
            receita_gerada=('receita_total', 'sum')
        ).copy()
        
        df_agrupado = df_agrupado[df_agrupado['volume'] > 0].copy()
        
        df_agrupado['50+/1000'] = (df_agrupado['casos_50'] / df_agrupado['volume'] * 1000).round(1)
        df_agrupado['100+/1000'] = (df_agrupado['casos_100'] / df_agrupado['volume'] * 1000).round(1)
        df_agrupado['200+/1000'] = (df_agrupado['casos_200'] / df_agrupado['volume'] * 1000).round(1)
        df_agrupado['Etiq/1000'] = (df_agrupado['casos_etiqueta'] / df_agrupado['volume'] * 1000).round(1)
        
        df_agrupado['Lift_50'] = ((df_agrupado['casos_50'] / df_agrupado['volume']) / tx_global_50).round(2)
        df_agrupado['Lift_100'] = ((df_agrupado['casos_100'] / df_agrupado['volume']) / tx_global_100).round(2)
        df_agrupado['Lift_200'] = ((df_agrupado['casos_200'] / df_agrupado['volume']) / tx_global_200).round(2)
        df_agrupado['Lift_Etiq'] = ((df_agrupado['casos_etiqueta'] / df_agrupado['volume']) / tx_global_etiqueta).round(2)
        df_agrupado['Receita_Por_Lead'] = (df_agrupado['receita_gerada'] / df_agrupado['volume']).round(2)
        df_agrupado = df_agrupado.sort_values('Receita_Por_Lead', ascending=False)
        print(df_agrupado.to_string())
        df_agrupado.to_excel(writer_interacao, sheet_name=nome_exibicao)
print("\n\n" + "#" * 100)
print(" INICIANDO ESTUDO DE INTERAÇÕES (COMBINAÇÃO DE VARIÁVEIS)")
print("#" * 100)
interacoes_para_testar = [
    ['bucket', 'cat_ano'], ['bucket', 'cat_valor'], ['cat_ano', 'cat_valor'],
    ['cat_idade', 'cat_valor'], ['cat_ano', 'classificacao_ticket'], ['estado', 'cat_ano'],
    ['cat_idade','cat_ano'], ['genero','cat_ano'], ['genero', 'cat_valor'],
    ['genero','bucket'], ['genero', 'tipo_veiculo'], ['genero', 'cat_idade'],
    ['tipo_veiculo', 'cat_ano'], ['tipo_veiculo', 'cat_valor'],
]
with pd.ExcelWriter('matrizes_interacao_lift.xlsx', engine='openpyxl') as writer_interacao:
    for cols in interacoes_para_testar:
        nome_exibicao_1 = cols[0].replace('cat_', '').upper()
        nome_exibicao_2 = cols[1].replace('cat_', '').upper()
        print(f"\n==========================================================")
        print(f" INTERAÇÃO: {nome_exibicao_1} + {nome_exibicao_2}")
        print(f"==========================================================")
        df_interacao = resultado.groupby(cols, dropna=False).agg(
            volume=('atendimento_id', 'count'),
            casos_100=('mais_100', 'sum'),
            casos_200=('mais_200', 'sum'),
            casos_etiqueta=('converteu_etiqueta', 'sum'),
            receita_gerada=('receita_total', 'sum')
        ).copy()
        df_interacao = df_interacao[df_interacao['volume'] >= 10].copy()
        
        df_interacao['100+/1000'] = (df_interacao['casos_100'] / df_interacao['volume'] * 1000).round(1)
        df_interacao['200+/1000'] = (df_interacao['casos_200'] / df_interacao['volume'] * 1000).round(1)
        df_interacao['Etiq/1000'] = (df_interacao['casos_etiqueta'] / df_interacao['volume'] * 1000).round(1)
        
        df_interacao['Lift_100'] = ((df_interacao['casos_100'] / df_interacao['volume']) / tx_global_100).round(2)
        df_interacao['Lift_200'] = ((df_interacao['casos_200'] / df_interacao['volume']) / tx_global_200).round(2)
        df_interacao['Lift_Etiq'] = ((df_interacao['casos_etiqueta'] / df_interacao['volume']) / tx_global_etiqueta).round(2)
        df_interacao['Receita_Por_Lead'] = (df_interacao['receita_gerada'] / df_interacao['volume']).round(2)
        
        df_interacao = df_interacao.sort_values('Receita_Por_Lead', ascending=False)
        print(df_interacao.to_string())
        
        nome_aba = f"{nome_exibicao_1[:13]}_{nome_exibicao_2[:13]}"
        df_interacao.to_excel(writer_interacao, sheet_name=nome_aba)
        
        df_heat = df_interacao.reset_index()
        try:
            pivot_table_200 = df_heat.pivot(index=cols[0], columns=cols[1], values='Lift_200')
            plt.figure(figsize=(10, 6))
            sns.heatmap(pivot_table_200, annot=True, cmap='RdYlGn', center=1.0, fmt=".2f")
            plt.title(f'Mapa de Calor: Conversão Lift_200 ({nome_exibicao_1} vs {nome_exibicao_2})')
            plt.ylabel(nome_exibicao_1)
            plt.xlabel(nome_exibicao_2)
            plt.tight_layout()
            plt.savefig(f"heatmap_{cols[0]}_{cols[1]}_lift200.png")
            plt.close()
        except Exception as e:
            plt.close()
        try:
            pivot_table_etiq = df_heat.pivot(index=cols[0], columns=cols[1], values='Lift_Etiq')
            plt.figure(figsize=(10, 6))
            sns.heatmap(pivot_table_etiq, annot=True, cmap='RdYlGn', center=1.0, fmt=".2f")
            plt.title(f'Mapa de Calor: Conversão Etiqueta Lift ({nome_exibicao_1} vs {nome_exibicao_2})')
            plt.ylabel(nome_exibicao_1)
            plt.xlabel(nome_exibicao_2)
            plt.tight_layout()
            plt.savefig(f"heatmap_{cols[0]}_{cols[1]}_etiqueta.png")
            plt.close()
        except Exception as e:
            plt.close()
print("\n" + "=" * 100)
print(" GERANDO EXPORTAÇÕES CONSOLIDADAS EM ABAS...")
print("=" * 100 + "\n")
cohort = resultado.groupby(resultado['data_chegada'].dt.date).agg(
    total_atendimentos=('atendimento_id', 'count'),
    atendimentos_50=('mais_50', 'sum'),
    atendimentos_100=('mais_100', 'sum'),
    atendimentos_etiqueta=('converteu_etiqueta', 'sum'),
    receita_total=('receita_total', 'sum')
)
cohort['taxa_50'] = (cohort['atendimentos_50'] / cohort['total_atendimentos']) * 100
cohort['taxa_100'] = (cohort['atendimentos_100'] / cohort['total_atendimentos']) * 100
cohort['taxa_etiqueta'] = (cohort['atendimentos_etiqueta'] / cohort['total_atendimentos']) * 100
cohort['receita_por_lead'] = cohort['receita_total'] / cohort['total_atendimentos']
cohort = cohort.sort_index()
plt.figure(figsize=(18, 8))
cohort[['taxa_50', 'taxa_100', 'taxa_etiqueta']].plot(kind='bar', figsize=(18, 8))
plt.title('% de Conversão por data_chegada (Volume de Mensagens vs Presença de Etiquetas)')
plt.ylabel('%')
plt.xlabel('Data Chegada')
plt.tight_layout()
plt.savefig("grafico_taxa.png")
plt.close()
arquivo_relatorio = 'analise_conversao_completa.xlsx'
with pd.ExcelWriter(arquivo_relatorio, engine='openpyxl') as writer:
    cohort.to_excel(writer, sheet_name='Resumo_Cohort_Diario')
    resultado.to_excel(writer, sheet_name='Dados_Brutos_Detalhado', index=False)
print(f"Sucesso! Relatórios gerados com as métricas de receita:\n-> '{arquivo_relatorio}'\n-> 'matrizes_unica_lift_e_receita.xlsx'\n-> 'matrizes_interacao_lift.xlsx'")