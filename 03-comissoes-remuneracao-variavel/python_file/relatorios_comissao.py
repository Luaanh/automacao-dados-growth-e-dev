import os
import re
import math
import json
from datetime import datetime, timedelta

import pandas as pd
import holidays

import utils_core

USER_MAQUINA = os.environ.get('USERPROFILE', '')
PASTA_DOWNLOADS = os.path.join(USER_MAQUINA, 'Downloads')
DIAS_RETROATIVOS = 30
DATA_INICIO = datetime(2025, 12, 1).date()
BR_FERIADOS = holidays.Brazil()

class Sanitizar:
    @staticmethod
    def validar_data(d):
        if pd.isna(d): return None
        try:
            d = pd.to_datetime(d, errors='coerce')
            return d if not pd.isna(d) else None
        except Exception:
            return None

    @staticmethod
    def _clean_key_col(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip()
        s = s.str.replace(r'\.0$', '', regex=True)
        return s.replace(['', 'None', 'nan', 'NULL', 'null', '<NA>'], pd.NA).fillna('<NA>')

    @staticmethod
    def _to_num_valor_series(s):
        s = s.fillna('').astype(str).str.strip()
        s = s.str.replace(r'[^\d,.\-]', '', regex=True).str.replace(',', '.', regex=False)
        return pd.to_numeric(s.replace('', pd.NA), errors='coerce')

    @staticmethod
    def _nan_to_none(x):
        if x is None or pd.isna(x) or (isinstance(x, float) and math.isnan(x)):
            return None
        return x

    @staticmethod
    def extrair_info_produto(texto):
        if pd.isna(texto):
            return pd.Series([None, None, None])

        texto = str(texto).upper()
        regra = re.search(r'^(.*?)\s*-\s*TAXA', texto)
        taxa = re.search(r'TAXA\s+([\d,]+)%', texto)
        codigo = re.search(r'C[ÓO]D\.?\s*(\d+)', texto)

        return pd.Series([
            regra.group(1).strip() if regra else None,
            float(taxa.group(1).replace(',', '.')) if taxa else None,
            codigo.group(1) if codigo else None
        ])

    @staticmethod
    def normalizar_str(s):
        return s.astype(str).str.upper().str.strip()

class GerarDados:
    @staticmethod
    def gerar_dados_contratos():
        with utils_core.Database('APP_DB') as conn:
            query = """
                SELECT 
                    nom_banco, num_proposta, num_contrato, cod_cpf_cliente cliente_id, val_repasse, 
                    val_comissao, dat_emprestimo, dsc_situacao_emprestimo status_producao, dat_confirmacao, banco_id,
                    'NOVA' as plataforma, dsc_tipo_proposta_emprestimo as tipo_operacao, val_repasse val_liberado, 
                    dat_credito, cod_produto, dsc_produto, qtd_parcela prazo, dsc_convenio, val_bruto
                FROM vw_contratos_nova 
                WHERE UPPER(dsc_situacao_emprestimo) LIKE '%PAGO%'
                
                UNION ALL
                
                SELECT
                    nom_banco, num_proposta, num_contrato, cod_cpf_cliente cliente_id, val_repasse, 
                    val_comissao, dat_emprestimo, status_producao, NULL as dat_confirmacao, 3 as banco_id,
                    'BB' as plataforma, NULL as tipo_operacao, val_liberado, dat_credito, NULL as cod_produto, 
                    NULL as dsc_produto, prazo, NULL as dsc_convenio, val_bruto
                FROM vw_contratos_bb
                WHERE UPPER(status_producao) = 'PRODUÇÃO'
            """
            return pd.read_sql(query, conn)

    @staticmethod
    def gerar_dados_producao(data_min: str, data_max: str):
        with utils_core.Database('APP_DB') as conn:
            query = f"""
                SELECT p.*, c.convenio 
                FROM producao_cadastro_unico p
                JOIN convenios_padronizados c ON c.id = p.convenio_id
                WHERE p.data_contrato BETWEEN '{data_min}' AND '{data_max}' 
            """
            return pd.read_sql(query, conn)

    @staticmethod
    def get_tabelas_bancos():
        with utils_core.Database('APP_DB') as conn:
            query = """
                SELECT id as tabela_id, banco_id, codigo, regra, prazo, execution_date, data_fim 
                FROM tabelas_bancos
            """
            return pd.read_sql(query, conn)

    @staticmethod
    def gerar_dados_contratos_financiamento():
        with utils_core.Database('APP_DB') as conn:
            query = """
                SELECT idcontrato, nrcpfcnpj, nrchassi, numero_da_proposta numero_proposta, 
                       vlliquido_txa valor_txa_comissao, vlliquido_plu valor_plu_comissao, 
                       soma_ambos val_comissao, valor_liberado
                FROM vw_contratos_financiamento
            """
            return pd.read_sql(query, conn)

    @staticmethod
    def gerar_dados_producao_financiamento():
        with utils_core.Database('APP_DB') as conn:
            query = "SELECT p.* FROM producao_fin_banco p WHERE p.data_contrato >= '2025-01-01'"
            return pd.read_sql(query, conn)

class ContratosProcessor:
    ETAPAS_MATCHING = [
        {'nome': 'Etapa 1: CPF + Número Proposta', 'chaves': ['cliente_id', 'numero_proposta']},
        {'nome': 'Etapa 2: CPF + Número Contrato', 'chaves': ['cliente_id', 'numero_contrato']},
        {'nome': 'Etapa 3: Banco + Número Proposta', 'chaves': ['banco_id', 'numero_proposta']},
        {'nome': 'Etapa 4: Banco + Número Contrato', 'chaves': ['banco_id', 'numero_contrato']},
        {'nome': 'Etapa 5: CPF + Valor Liberado', 'chaves': ['cliente_id', 'valor_liberado']},
    ]

    def __init__(self, pasta_downloads: str):
        self.pasta_downloads = pasta_downloads
        self.df_origem = None
        self.df_db = None
        self.estatisticas = {}
        self.updates_para_fazer = []
        self.mapeamento_encontrados = []
        self.indices_origem_pareados = set()
        self.ids_db_pareados = set()

    def carregar_arquivos(self):
        self.df_origem = GerarDados.gerar_dados_contratos().drop_duplicates().reset_index()
        if self.df_origem.empty: return False
        
        self.data_min = self.df_origem['dat_emprestimo'].min()
        self.data_max = self.df_origem['dat_emprestimo'].max()
        return True

    def preparar_origem(self):
        rename_map = {
            'cod_cpf_cliente': 'cliente_id', 'num_proposta': 'numero_proposta',
            'num_contrato': 'numero_contrato', 'val_base_comissao': 'base_comissao',
            'dat_emprestimo': 'data_emprestimo', 'dat_credito': 'data_contrato'
        }
        self.df_origem.rename(columns=rename_map, inplace=True)
        
        self.df_origem['data_emprestimo'] = self.df_origem['data_emprestimo'].apply(Sanitizar.validar_data)
        self.df_origem['data_contrato'] = self.df_origem['data_contrato'].apply(Sanitizar.validar_data)
        
        self.df_origem['numero_proposta'] = Sanitizar._clean_key_col(self.df_origem['numero_proposta'])
        self.df_origem['numero_contrato'] = Sanitizar._clean_key_col(self.df_origem['numero_contrato'])
        
        self.df_origem['cliente_id'] = self.df_origem['cliente_id'].apply(utils_core.Geral.formatar_cpf).fillna('<NA>')
        self.df_origem['banco_id'] = self.df_origem['banco_id'].astype('Int64')

    def vincular_id_tabela(self):
        df_ref = GerarDados.get_tabelas_bancos() 
        if df_ref.empty:
            self.df_origem['tabela_id_encontrado'] = None
            return

        df_ref['execution_date'] = df_ref['execution_date'].apply(Sanitizar.validar_data)
        df_ref['data_fim'] = df_ref['data_fim'].apply(Sanitizar.validar_data).fillna(pd.Timestamp('2099-12-31'))

        for df in [self.df_origem, df_ref]:
            df['key_banco'] = pd.to_numeric(df['banco_id'], errors='coerce')
            df['key_codigo'] = df.get('cod_produto', df.get('codigo')).astype(str).str.strip()
            df['key_regra'] = df.get('dsc_produto', df.get('regra')).astype(str).str.strip().str.upper()
            df['key_prazo'] = pd.to_numeric(df['prazo'], errors='coerce')
            df['key_convenio_id'] = df['convenio_id'].astype(str).str.strip()
            df['key_produto_id'] = df['produto_id'].astype(str).str.strip()

        cols_ref = ['key_banco', 'key_codigo', 'key_regra', 'key_convenio_id', 'key_prazo', 'key_produto_id', 'tabela_id', 'execution_date', 'data_fim']
        
        df_merged = self.df_origem.merge(df_ref[cols_ref], on=cols_ref[:-3], how='left')
        mask_vigencia = (df_merged['data_emprestimo'] >= df_merged['execution_date']) & (df_merged['data_emprestimo'] <= df_merged['data_fim'])
        
        df_validos = df_merged[mask_vigencia].sort_values('execution_date', ascending=False).drop_duplicates(subset=['index']) 
        self.df_origem['tabela_id_encontrado'] = self.df_origem['index'].map(dict(zip(df_validos['index'], df_validos['tabela_id'])))
        self.df_origem.drop(columns=cols_ref[:-3], inplace=True)

    def carregar_dados_banco(self):
        try:
            self.df_db = GerarDados.gerar_dados_producao(self.data_min, self.data_max)
            self.df_db['data_contrato'] = self.df_db['data_contrato'].apply(Sanitizar.validar_data)
        except Exception:
            return False

        self.df_db['numero_proposta'] = Sanitizar._clean_key_col(self.df_db['numero_proposta'])
        self.df_db['numero_contrato'] = Sanitizar._clean_key_col(self.df_db['numero_contrato'])
        self.df_db['banco_id'] = self.df_db['banco_id'].astype('Int64')
        return True

    def executar_matching(self):
        df_match = self.df_origem.copy()
        df_match[['regra_extraida', 'taxa_extraida', 'codigo_extraido']] = df_match['dsc_produto'].apply(Sanitizar.extrair_info_produto)
        
        if 'index' not in df_match.columns:
            df_match = df_match.reset_index(drop=False)

        with utils_core.Database('APP_DB') as conn:
            df_tabela = pd.read_sql("""
                SELECT descricao_banco AS regra, taxa_total AS taxa_com_seguro, taxa_vista AS taxa_sem_seguro,
                       codigo AS inicio_regra, comissao_vista AS perc_empresa_avista, data_inicio, data_fim
                FROM tabela_taxas
            """, conn)

        df_tabela['data_inicio'] = df_tabela['data_inicio'].apply(Sanitizar.validar_data)
        df_tabela['data_fim'] = df_tabela['data_fim'].apply(Sanitizar.validar_data).fillna(pd.Timestamp('2099-12-31'))

        df_tabela['regra'] = Sanitizar.normalizar_str(df_tabela['regra'])
        df_match['regra_extraida'] = Sanitizar.normalizar_str(df_match['regra_extraida'])
        df_tabela['inicio_regra'] = Sanitizar.normalizar_str(df_tabela['inicio_regra'])
        df_match['codigo_extraido'] = Sanitizar.normalizar_str(df_match['codigo_extraido'])

        for col in ['taxa_com_seguro', 'taxa_sem_seguro', 'perc_empresa_avista']:
            df_tabela[col] = Sanitizar._to_num_valor_series(df_tabela[col])

        df_merge = df_match.merge(df_tabela, left_on=['regra_extraida', 'codigo_extraido'], right_on=['regra', 'inicio_regra'], how='left')
        
        df_merge['match_taxa'] = (df_merge['taxa_extraida'].round(2) == df_merge['taxa_com_seguro'].round(2)) | (df_merge['taxa_extraida'].round(2) == df_merge['taxa_sem_seguro'].round(2))
        df_merge['data_emprestimo'] = pd.to_datetime(df_merge['data_emprestimo'], errors='coerce')
        
        mask_vigencia = (df_merge['data_emprestimo'] >= df_merge['data_inicio']) & (df_merge['data_emprestimo'] <= df_merge['data_fim'])
        df_merge = df_merge[mask_vigencia].sort_values(['index', 'match_taxa', 'perc_empresa_avista'], ascending=[True, False, False]).drop_duplicates(subset='index')

        condicao = df_merge['nom_banco'].str.contains('SANTANDER', case=False, na=False) & df_merge[['val_repasse', 'val_comissao', 'perc_empresa_avista']].notna().all(axis=1)
        df_merge['__VAL_COMISSAO_TOTAL'] = df_merge['val_comissao']
        df_merge.loc[condicao, '__VAL_COMISSAO_TOTAL'] = (df_merge.loc[condicao, 'val_liberado'] * (df_merge.loc[condicao, 'perc_empresa_avista'] / 100)).round(2)

        df_match = df_match.merge(df_merge[['index', '__VAL_COMISSAO_TOTAL']], on='index', how='left', suffixes=('', '_novo'))
        df_match['__VAL_COMISSAO_TOTAL'] = df_match['__VAL_COMISSAO_TOTAL_novo'].fillna(df_match['__VAL_COMISSAO_TOTAL'])
        
        df_match['__VAL_BASE_COMISSAO'] = df_match['val_repasse']
        df_match['__VAL_LIBERADO'] = df_match['val_repasse']
        df_match['__VAL_FINANCIADO'] = df_match['val_bruto']
        df_match['__PRAZO'] = df_match['prazo']
        df_match['__TABELA'] = df_match['dsc_produto']
        
        df_match['valor_liberado'] = Sanitizar._to_num_valor_series(df_match.get('val_liberado', pd.Series([pd.NA]*len(df_match)))).round(2)
        
        if 'valor_liberado' not in self.df_db.columns:
            self.df_db['valor_liberado'] = self.df_db.get('base_comissao', pd.Series([pd.NA]*len(self.df_db)))
        
        self.df_db['valor_liberado'] = Sanitizar._to_num_valor_series(self.df_db['valor_liberado']).round(2)
        self.df_db['cliente_id'] = self.df_db['cliente_id'].apply(utils_core.Geral.formatar_cpf).fillna('<NA>')

        for etapa in self.ETAPAS_MATCHING:
            chaves = etapa['chaves']
            df_origem_pendente = df_match[~df_match['index'].isin(self.indices_origem_pareados)]
            df_db_pendente = self.df_db[~self.df_db['id'].isin(self.ids_db_pareados)]

            df_merged = pd.merge(
                df_origem_pendente.dropna(subset=chaves)[['index', '__VAL_BASE_COMISSAO', '__VAL_COMISSAO_TOTAL', '__VAL_LIBERADO', '__VAL_FINANCIADO', '__PRAZO', '__TABELA'] + chaves],
                df_db_pendente.dropna(subset=chaves)[['id'] + chaves],
                on=chaves, how='inner'
            )

            for _, row in df_merged.iterrows():
                if row['index'] not in self.indices_origem_pareados and row['id'] not in self.ids_db_pareados:
                    val_lib = row['__VAL_LIBERADO'] if row['__VAL_LIBERADO'] != 0 else None
                    val_fin = row['__VAL_FINANCIADO'] if row['__VAL_FINANCIADO'] != 0 else None

                    self.updates_para_fazer.append((
                        row['__VAL_BASE_COMISSAO'], row['__VAL_COMISSAO_TOTAL'], val_lib, val_fin, row['__PRAZO'], row['__TABELA'], row['id']
                    ))
                    self.mapeamento_encontrados.append({'index': row['index'], 'id': row['id']})
                    self.indices_origem_pareados.add(row['index'])
                    self.ids_db_pareados.add(row['id'])

    def atualizar_banco(self):
        if not self.updates_para_fazer: return

        update_query = """
            UPDATE producao_cadastro_unico
            SET base_comissao = %s, valor_comissao = %s, valor_liberado = COALESCE(%s, valor_liberado),
                valor_financiado = COALESCE(%s, valor_financiado), prazo = %s, tabela = %s
            WHERE id = %s AND data_contrato >= '2026-04-01'
        """
        tuplas_adicionar = [tuple(Sanitizar._nan_to_none(v) for v in row) for row in self.updates_para_fazer]

        with utils_core.Database('APP_DB') as conn:
            cur = conn.cursor()
            cur.executemany(update_query, tuplas_adicionar)
            conn.commit()

    @staticmethod
    def _padronizar_dataframe(df, nome_tabela):
        df = df.copy()
        cols_drop = []
        if 'nom_banco' in df.columns and 'banco' in df.columns: cols_drop.append('banco')
        if 'num_proposta' in df.columns and 'numero_proposta' in df.columns: cols_drop.append('numero_proposta')
        if 'val_comissao' in df.columns and 'valor_comissao' in df.columns: cols_drop.append('valor_comissao')
        if 'val_liberado' in df.columns and 'Total_Liberado' in df.columns: cols_drop.append('Total_Liberado')
        if 'dat_credito' in df.columns and 'data_contrato' in df.columns: cols_drop.append('data_contrato')
        
        df.drop(columns=cols_drop, inplace=True, errors='ignore')
        df.rename(columns={'banco': 'nom_banco', 'numero_proposta': 'num_proposta', 'valor_comissao': 'val_comissao', 'Total_Liberado': 'val_liberado', 'data_contrato': 'dat_credito'}, inplace=True)
        df['tabela'] = nome_tabela
        
        if 'dat_credito' in df.columns:
            df['dat_credito'] = pd.to_datetime(df['dat_credito'], errors='coerce')
        return df

    def criar_dataframes(self):
        df_map = pd.DataFrame(self.mapeamento_encontrados)
        indices_encontrados = set(df_map['index']) if not df_map.empty else set()
        ids_db_encontrados = set(df_map['id']) if not df_map.empty else set()

        df_nao_encontrados_full = self.df_origem[~self.df_origem['index'].isin(indices_encontrados)]
        df_nao_ecb_full = self.df_db[~self.df_db['id'].isin(ids_db_encontrados)]

        filtro_datas = ((self.df_origem['data_contrato'].dt.date >= (datetime.today() - timedelta(days=DIAS_RETROATIVOS)).date()) & 
                        (self.df_origem['data_contrato'].dt.date >= DATA_INICIO)) | self.df_origem['data_contrato'].isna()

        df_comissao_nula = self.df_origem[self.df_origem['val_comissao'].isna() & filtro_datas].copy()
        df_comissao_zero = self.df_origem[(pd.to_numeric(self.df_origem['val_comissao'], errors='coerce') == 0) & filtro_datas].copy()
        
        atraso_pgto = Atrasopgto().gerar_atraso_pgto()

        df_pagamentos = self._padronizar_dataframe(atraso_pgto, 'PAGAMENTOS')
        df_nao_ecb = self._padronizar_dataframe(df_nao_ecb_full, 'NAO_ENCONTRADOS_ECB')
        df_comissao_nula = self._padronizar_dataframe(df_comissao_nula, 'COMISSAO_NULA')
        df_comissao_zero = self._padronizar_dataframe(df_comissao_zero, 'COMISSAO_ZERO')
        df_pago = self._padronizar_dataframe(self.df_origem[~self.df_origem['val_comissao'].isna() & (self.df_origem['status_producao'] == 'pago')], 'PAGO')

        df_pagamentos['prioridade'] = 1
        df_nao_ecb['prioridade'] = 2
        df_comissao_nula['prioridade'] = 3
        df_comissao_zero['prioridade'] = 4
        df_pago['prioridade'] = 5

        df_empilhado = pd.concat([df_pagamentos, df_nao_ecb, df_comissao_nula, df_comissao_zero, df_pago], ignore_index=True)
        df_empilhado = df_empilhado[(df_empilhado['dat_credito'].notna()) & (df_empilhado['dat_credito'] >= datetime.now() - timedelta(days=63))]

        cols_report = ['nom_banco', 'num_proposta', 'num_contrato', 'val_comissao', 'status_producao', 'tipo_operacao', 'val_liberado', 'dat_credito', 'data_esperada_pgto', 'status_pgto', 'tabela']
        df_report_nova = df_empilhado.sort_values('prioridade').drop_duplicates(subset=['num_proposta']).drop(columns=['prioridade'])[cols_report]
        df_report_nova = df_report_nova[~df_report_nova['nom_banco'].isin(['BANCO DO BRASIL', 'SABEMI'])]

        df_convenio = self.df_db.merge(df_map, on='id').merge(self.df_origem, on='index')
        df_convenio = utils_core.Geral.calcular_semelhanca_nomes(df_convenio, 'dsc_convenio', 'convenio')

        return {
            'RESUMO': pd.DataFrame(list(self.estatisticas.items()), columns=['Etapa', 'Registros']),
            'NAO_ENCONTRADOS_BANCOS': df_nao_encontrados_full.drop(columns=['index'], errors='ignore'),
            'NAO_ENCONTRADOS_ECB': df_nao_ecb_full,
            'COMISSAO_NULA': df_comissao_nula,
            'COMISSAO_ZERO': df_comissao_zero,
            'CONVENIOS': df_convenio,
            'REPORT NOVA': df_report_nova
        }

    def executar(self):
        if not self.carregar_arquivos() or not self.carregar_dados_banco(): return
        self.preparar_origem()
        self.executar_matching()
        dict_df = self.criar_dataframes()
        self.atualizar_banco()
        return dict_df

class ContratosGrowthProcessor(ContratosProcessor):
    ETAPAS_MATCHING = [{'nome': 'Etapa 1: Número Proposta', 'chaves': ['numero_proposta']}]

    def carregar_arquivos(self):
        self.df_origem = GerarDados.gerar_dados_contratos_financiamento().drop_duplicates().reset_index()
        return not self.df_origem.empty

    def preparar_origem(self):
        self.df_origem['numero_proposta'] = Sanitizar._clean_key_col(self.df_origem['numero_proposta'].astype('Int64').astype(str))

    def carregar_dados_banco(self):
        try:
            self.df_db = GerarDados.gerar_dados_producao_financiamento()
            self.df_db['numero_proposta'] = self.df_db['numero_proposta'].astype('Int64').astype(str)
            return True
        except Exception:
            return False

    def executar_matching(self):
        df_match = self.df_origem.copy()
        df_match['__VAL_BASE_COMISSAO'] = df_match['valor_liberado']
        df_match['__VAL_COMISSAO_TOTAL'] = df_match['val_comissao']
        df_match['__VAL_COMISSAO_PLU'] = df_match['valor_plu_comissao']
        df_match['__VAL_COMISSAO_TXA'] = df_match['valor_txa_comissao']

        for etapa in self.ETAPAS_MATCHING:
            chaves = etapa['chaves']
            df_origem_pendente = df_match[~df_match['index'].isin(self.indices_origem_pareados)]
            df_db_pendente = self.df_db[~self.df_db['id'].isin(self.ids_db_pareados)]

            df_merged = pd.merge(
                df_origem_pendente.dropna(subset=chaves)[['index', '__VAL_BASE_COMISSAO', '__VAL_COMISSAO_TOTAL', '__VAL_COMISSAO_PLU', '__VAL_COMISSAO_TXA'] + chaves],
                df_db_pendente.dropna(subset=chaves)[['id'] + chaves],
                on=chaves, how='inner'
            )

            for _, row in df_merged.iterrows():
                if row['index'] not in self.indices_origem_pareados and row['id'] not in self.ids_db_pareados:
                    self.updates_para_fazer.append((row['__VAL_BASE_COMISSAO'], row['__VAL_COMISSAO_TOTAL'], row['__VAL_COMISSAO_PLU'], row['__VAL_COMISSAO_TXA'], row['id']))
                    self.mapeamento_encontrados.append({'index': row['index'], 'id': row['id']})
                    self.indices_origem_pareados.add(row['index'])
                    self.ids_db_pareados.add(row['id'])

    def atualizar_banco(self):
        if not self.updates_para_fazer: return
        update_query = """
            UPDATE producao_fin_banco
            SET base_comissao = %s, valor_comissao = %s, valor_plu_comissao = %s, valor_txa_comissao = %s
            WHERE id = %s AND data_contrato >= '2025-01-01'
        """
        tuplas = [tuple(Sanitizar._nan_to_none(v) for v in row) for row in self.updates_para_fazer]
        with utils_core.Database('APP_DB') as conn:
            cur = conn.cursor()
            cur.executemany(update_query, tuplas)
            conn.commit()

    def criar_dataframes(self):
        df_map = pd.DataFrame(self.mapeamento_encontrados)
        indices_encontrados = set(df_map['index']) if not df_map.empty else set()
        ids_db_encontrados = set(df_map['id']) if not df_map.empty else set()

        df_nao_ecb = self._padronizar_dataframe(self.df_db[~self.df_db['id'].isin(ids_db_encontrados)], 'NAO_ENCONTRADOS_ECB')
        df_comissao_nula = self._padronizar_dataframe(self.df_origem[self.df_origem['val_comissao'].isna()], 'COMISSAO_NULA')
        df_comissao_zero = self._padronizar_dataframe(self.df_origem[pd.to_numeric(self.df_origem['val_comissao'], errors='coerce') == 0], 'COMISSAO_ZERO')
        df_origem_padrao = self._padronizar_dataframe(self.df_origem, 'PAGO')

        df_nao_ecb['prioridade'], df_comissao_nula['prioridade'], df_comissao_zero['prioridade'], df_origem_padrao['prioridade'] = 1, 2, 3, 4
        
        df_empilhado = pd.concat([df_nao_ecb, df_comissao_nula, df_comissao_zero, df_origem_padrao], ignore_index=True)
        cols_report = ['num_proposta', 'val_liberado', 'val_comissao', 'valor_txa_comissao', 'valor_plu_comissao', 'tabela']
        
        df_report = df_empilhado.sort_values('prioridade').drop_duplicates(subset=['num_proposta']).drop(columns=['prioridade'])
        df_report = df_report[[c for c in cols_report if c in df_report.columns]]

        return {
            'RESUMO': pd.DataFrame(list(self.estatisticas.items()), columns=['Etapa', 'Registros']),
            'NAO_ENCONTRADOS_ORIGEM': self.df_origem[~self.df_origem['index'].isin(indices_encontrados)],
            'NAO_ENCONTRADOS_ECB': df_nao_ecb,
            'COMISSAO_NULA': df_comissao_nula,
            'COMISSAO_ZERO': df_comissao_zero,
            'REPORT GROWTH ANALYTICS': df_report
        }

class Atrasopgto:
    def adicionar_dias_uteis(self, data_inicial: datetime, dias: int) -> datetime:
        data_atual = data_inicial
        adicionados = 0
        while adicionados < dias:
            data_atual += timedelta(days=1)
            if data_atual.weekday() < 5 and data_atual.date() not in BR_FERIADOS:
                adicionados += 1
        return data_atual

    def proximo_dia_util(self, data_inicial: datetime) -> datetime:
        data = data_inicial + timedelta(days=1)
        while data.weekday() >= 5 or data.date() in BR_FERIADOS:
            data += timedelta(days=1)
        return data

    def calcular_data_confirmacao(self, data_emprestimo: datetime, banco: str, sla_config: dict, tipo_operacao: str = None) -> datetime:
        if banco not in sla_config or data_emprestimo is None or pd.isna(data_emprestimo):
            return self.proximo_dia_util(data_emprestimo) if not pd.isna(data_emprestimo) else None

        regra = sla_config[banco].copy()
        
        if tipo_operacao and "regras_extras" in regra:
            regras_por_oper = regra["regras_extras"].get("tipo_operacao", {})
            if tipo_operacao in regras_por_oper:
                regra_oper = regras_por_oper[tipo_operacao]
                if regra_oper.get("tipo_sla") == "mensal" or regra_oper.get("mensal", {}).get("ativo"):
                    dia_limite_ref = regra_oper.get("mensal", {}).get("dia_limite", 16)
                    mes, ano = data_emprestimo.month, data_emprestimo.year
                    if data_emprestimo.day > dia_limite_ref:
                        mes = mes + 1 if mes < 12 else 1
                        ano = ano + 1 if mes == 1 else ano
                    return datetime(ano, mes, dia_limite_ref)
                regra.update(regra_oper)

        extras_globais = regra.get("regras_extras", {})
        data_limite_val = extras_globais.get("data_limite")
        
        if data_limite_val and data_emprestimo.day >= data_limite_val:
            acao = extras_globais.get("acao_pos_limite")
            if acao == "adiar_pagamento": return None
            if acao == "adicionar_dias": data_emprestimo += timedelta(days=1)

        dias_pt = ["segunda", "terça", "quarta", "quinta", "sexta", "sabado", "domingo"]
        dia_envio_chave = dias_pt[data_emprestimo.weekday()]
        
        if dia_envio_chave in extras_globais.get("dia_envio_proposta", {}):
            regra.update(extras_globais["dia_envio_proposta"][dia_envio_chave])
            extras_globais = regra.get("regras_extras", {})

        tipo = regra.get("tipo_sla")
        data_calculada = None

        if tipo == "dias_uteis":
            data_calculada = self.adicionar_dias_uteis(data_emprestimo, regra.get("dias", 1)) if regra.get("usar_dias_uteis", True) else data_emprestimo + timedelta(days=regra.get("dias", 1))
        elif tipo == "dias_corridos":
            data_calculada = data_emprestimo + timedelta(days=regra.get("dias", 1))
        elif tipo in ["dia_semana", "dia_semana_multiplo"]:
            dias_semana_map = {"segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4}
            alvo = dias_semana_map.get(regra.get("dia_semana", "").lower())
            dias_validos = [alvo] if alvo is not None else [dias_semana_map[d.lower()] for d in regra.get("dias_semana", []) if d.lower() in dias_semana_map]
            
            data_calculada = data_emprestimo
            while data_calculada.weekday() not in dias_validos or data_calculada.date() in BR_FERIADOS:
                data_calculada += timedelta(days=1)
        elif tipo == "semanal":
            data_calculada = self.proximo_dia_util(data_emprestimo + timedelta(weeks=regra.get("intervalo_semanas", 1)))
        elif tipo == "mensal":
            dia_limite = regra.get("dia_limite", 16)
            mes, ano = data_emprestimo.month, data_emprestimo.year
            if data_emprestimo.day > dia_limite:
                mes = mes + 1 if mes < 12 else 1
                ano = ano + 1 if mes == 1 else ano
            data_calculada = datetime(ano, mes, dia_limite)
        else:
            data_calculada = self.proximo_dia_util(data_emprestimo)

        if extras_globais.get("mensal", {}).get("ativo") and tipo != "mensal":
            dia_limite_m = extras_globais["mensal"].get("dia_limite", 16)
            mes, ano = data_emprestimo.month, data_emprestimo.year
            if data_emprestimo.day > dia_limite_m:
                mes = mes + 1 if mes < 12 else 1
                ano = ano + 1 if mes == 1 else ano
            data_calculada = datetime(ano, mes, dia_limite_m)

        if extras_globais.get("data_limite") and data_emprestimo.day >= extras_globais.get("data_limite"):
            if extras_globais.get("acao_pos_limite") == "adiar_pagamento": return None
            if extras_globais.get("acao_pos_limite") == "adicionar_dias": data_calculada += timedelta(days=1)

        return data_calculada

    def gerar_atraso_pgto(self):
        with open('bancos_sla.json', 'r', encoding='utf-8') as f:
            sla_config = json.load(f)

        df = GerarDados.gerar_dados_contratos()
        df = df[(df['dat_confirmacao'].isna()) & (df['plataforma'] == 'NOVA')].copy()
        df['nom_banco'] = df['nom_banco'].astype(str).str.strip()
        if 'tipo_operacao' not in df.columns: df['tipo_operacao'] = None
        
        df['dat_credito'] = df['dat_credito'].apply(Sanitizar.validar_data)
        df = df[(df['dat_credito'] >= '2025-12-01') | df['dat_credito'].isna()]

        df['data_esperada_pgto'] = df.apply(lambda r: self.calcular_data_confirmacao(r['dat_credito'], r['nom_banco'], sla_config, r.get('tipo_operacao')), axis=1)
        df['data_esperada_pgto'] = df['data_esperada_pgto'].apply(Sanitizar.validar_data)

        hoje = pd.Timestamp.today().normalize()
        df['status_pgto'] = 'EM DIA'
        df.loc[df['data_esperada_pgto'].isna(), 'status_pgto'] = 'AGUARDANDO RELATÓRIO'
        df.loc[df['data_esperada_pgto'] == hoje, 'status_pgto'] = 'PAGAR HOJE'
        df.loc[(df['data_esperada_pgto'] < hoje) & (~df['data_esperada_pgto'].isna()), 'status_pgto'] = 'ATRASO'
        return df

if __name__ == "__main__":
    dict_df = ContratosProcessor(PASTA_DOWNLOADS).executar()
    if dict_df:
        dict_df['PAGAMENTOS'] = Atrasopgto().gerar_atraso_pgto()
        dict_df['EXPLICAÇÃO'] = pd.DataFrame(list({
            'RESUMO': 'Resumo das Propostas procuradas',
            'ENCONTRADOS': 'Propostas dos Bancos que foram encontradas no Payment_records',
            'NAO_ENCONTRADOS_BANCOS': 'Propostas dos Bancos que NÃO foram encontradas no Payment_records',
            'NAO_ENCONTRADOS_ECB': 'Propostas do Payment_records que não foram encontradas nos Bancos',
            'PAGAMENTOS': 'Data esperada e status dos pagamentos de comissão'
        }.items()), columns=['Aba', 'Explicação'])
        utils_core.GerarRelatorios(dict_df, PASTA_DOWNLOADS).gerar_relatorios()