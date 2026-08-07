import os
import re
import time
import math
import random
import logging
import datetime
import traceback
import numpy as np
import pandas as pd
from joblib import dump, load
from dotenv import load_dotenv

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from mysql.connector.errors import DatabaseError, InterfaceError

import panorama as pan
import payment_records as ecb
import utils_core

load_dotenv()
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Model:
    def RandomForests(self, dados_treino: pd.DataFrame, colunas_treino: list[str], coluna_target: str):
        dados = dados_treino.copy()
        X = dados[colunas_treino]
        y = dados[coluna_target]
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        modelo = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
        modelo.fit(X_train, y_train)
        
        importancia = pd.Series(modelo.feature_importances_, index=X.columns).sort_values(ascending=False)
        print("Importância das variáveis:\n", importancia)
        
        scores_roc = cross_val_score(modelo, X, y, cv=5, scoring="roc_auc")
        print(f"Random Forest: AUC-ROC médio = {np.mean(scores_roc):.4f}")
        
        print(f"Acurácia no Treino: {modelo.score(X_train, y_train):.4f}")
        print(f"Acurácia no Teste: {modelo.score(X_test, y_test):.4f}")
        print(classification_report(y_test, modelo.predict(X_test)))
        
        return modelo


class Qualificacao:
    class Enriquecer:
        def __init__(self, df_enriquecer: pd.DataFrame):
            self.df_enriquecer = df_enriquecer

        def trocar_df(self, df_enriquecer: pd.DataFrame):
            self.df_enriquecer = df_enriquecer
        
        def executa_em_lotes(self, cursor, conn, sql, dados, descricao, tamanho_lote=1000):
            num_dez_porc = max(1, int(len(dados) * 0.1))
            for i in range(0, len(dados), tamanho_lote):
                lote = dados[i:i + tamanho_lote]
                cursor.executemany(sql, lote)
                conn.commit()
                if (i + tamanho_lote) % num_dez_porc == 0:
                    print(f'Processados {descricao}: ', min(i + tamanho_lote, len(dados)))
                    
            warnings = cursor.fetchwarnings()
            if warnings:
                print("\n⚠️  Alertas do MySQL encontrados:")
                for warning in warnings:
                    print(f"  - Nível: {warning[0]}, Código: {warning[1]}, Mensagem: {warning[2]}")

        def gerar_contratos(self, data_inicio: datetime.datetime):
            try:
                data_inicio_ultimo_ano = data_inicio - datetime.timedelta(days=366)
                data_fim_ultimo_ano = data_inicio - datetime.timedelta(days=1)

                with utils_core.Database('APP_DB_ANALYTICS') as conn:
                    query_ultimo_ano = f"""
                        SELECT cliente_id as cpf 
                        FROM producao_extenso 
                        WHERE data_contrato >= '{data_inicio_ultimo_ano.strftime('%Y-%m-%d')}' 
                          AND data_contrato <= '{data_fim_ultimo_ano.strftime('%Y-%m-%d')}'
                    """
                    df_producao_ultimo_ano = pd.read_sql(query_ultimo_ano, conn)
                
                df_contratos_ultimo_ano = df_producao_ultimo_ano.groupby("cpf").size().reset_index(name="qtd_contratos_ultimo_ano")
                
                data_inicio_contratos_totais = datetime.datetime(1990, 1, 1)
                
                with utils_core.Database('APP_DB_ANALYTICS') as conn:
                    query_anteriores = f"""
                        SELECT cliente_id as cpf 
                        FROM producao_extenso 
                        WHERE data_contrato >= '{data_inicio_contratos_totais.strftime('%Y-%m-%d')}' 
                          AND data_contrato <= '{(data_inicio_ultimo_ano - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}'
                    """
                    df_producao_anteriores = pd.read_sql(query_anteriores, conn)
                    
                df_contratos_totais_anteriores = df_producao_anteriores.groupby("cpf").size().reset_index(name="qtd_contratos_company")

                return df_contratos_ultimo_ano, df_contratos_totais_anteriores
            except Exception:
                logging.exception("Erro Gerar contratos")
                return pd.DataFrame(), pd.DataFrame()

        def treinar_modelo_chance_conversao(self):
            try:
                data_inicio = datetime.datetime.now() - datetime.timedelta(days=540)
                data_fim = datetime.datetime.now()
                
                with utils_core.Database('APP_DB_ANALYTICS') as conn:
                    query_convertidos = f"""
                        SELECT cliente_id as cpf 
                        FROM producao_extenso 
                        WHERE data_contrato >= '{data_inicio.strftime('%Y-%m-%d')}' 
                          AND data_contrato <= '{(data_fim - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}'
                    """
                    df_convertidos = pd.read_sql(query_convertidos, conn)
                    
                df_convertidos['convertidos'] = 1
                df_contratos_ultimo_ano, df_contratos_totais_anteriores = self.gerar_contratos(data_inicio)
                df_contratos_totais_anteriores.rename(columns={"qtd_contratos_company": "qtd_contratos_anteriores"}, inplace=True)
                
                df_tabulacoes = pan.Relatorios(data_inicio=data_inicio, data_fim=data_fim).tabulacoes_df(tipo='efetiva') 
                
                dfs_apply = (df_convertidos, df_contratos_ultimo_ano, df_tabulacoes, df_contratos_totais_anteriores)
                for df in dfs_apply:
                    if 'cpf' in df.columns:
                        df['cpf'] = df['cpf'].apply(utils_core.Geral.formatar_cpf)
                        
                df_resultado = df_tabulacoes[['cpf']].copy()
                df_resultado = utils_core.Geral.merge_em_lote(df_base=df_resultado, dfs=dfs_apply, how_pos='left', left_on='cpf', right_on='cpf')

                colunas = ['convertidos', 'qtd_contratos_anteriores', 'tabulacoes_efetivas', 'qtd_contratos_ultimo_ano']
                df_resultado[colunas] = df_resultado[colunas].fillna(0)
                
                colunas_treino = ['tabulacoes_efetivas', 'qtd_contratos_anteriores', 'qtd_contratos_ultimo_ano']
                modelo = Model().RandomForests(df_resultado, colunas_treino, 'convertidos')
                dump(modelo, 'chance_conversao_model.joblib')
                return True
            except Exception:
                logging.exception("Erro Treinar modelo")
                return False

        def gerar_df_necessarios_chance_conversao(self, lista_cpf: list[str], data_inicio: datetime.datetime) -> tuple[pd.DataFrame]:
            try:
                df_cliente_tabulacoes_efetivas = pan.Relatorios(lista_cpf=lista_cpf).tabulacoes_df('efetiva')
                df_contratos_ultimo_ano, df_contratos_totais_anteriores = self.gerar_contratos(data_inicio)
                return df_cliente_tabulacoes_efetivas, df_contratos_ultimo_ano, df_contratos_totais_anteriores
            except Exception:
                logging.exception("Erro Gerar df necessarios chance conversao")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        def calcular_chance_conversao(self, df_dados: pd.DataFrame):
            try:
                if not os.path.exists('chance_conversao_model.joblib'):
                    self.treinar_modelo_chance_conversao()
                    
                modelo = load('chance_conversao_model.joblib')
                lista_cpf = df_dados['cpf'].tolist()
                
                df_tabs, df_ultimo_ano, df_anteriores = self.gerar_df_necessarios_chance_conversao(lista_cpf, datetime.datetime.now())
                df_anteriores.rename(columns={"qtd_contratos_company": "qtd_contratos_anteriores"}, inplace=True)
                
                df_temp = pd.DataFrame({'cpf': [str(c) for c in lista_cpf]})
                
                for df in [df_tabs, df_ultimo_ano, df_anteriores]:
                    df['cpf'] = df['cpf'].astype(str)
                    df_temp = df_temp.merge(right=df, on='cpf', how='left')

                colunas_treino = ['tabulacoes_efetivas', 'qtd_contratos_anteriores', 'qtd_contratos_ultimo_ano']
                X_novos = df_temp[colunas_treino].fillna(0)

                df_dados["chance_de_conversao"] = modelo.predict_proba(X_novos)[:, 1] * 100
                return df_dados
            except Exception:
                logging.exception("Erro Calcular Chance Conversão")
                return df_dados

        def cliente_scoring(self, df: pd.DataFrame) -> pd.DataFrame:
            try:
                df['cpf'] = df['cpf'].apply(utils_core.Geral.formatar_cpf)
                lista_cpfs = df['cpf'].tolist()
                
                dfs_resultados = []
                tamanho_bloco = 1000
                
                with utils_core.Database('APP_DB_PORTAL') as conn_portal:
                    for i in range(0, len(lista_cpfs), tamanho_bloco):
                        cpfs_bloco = lista_cpfs[i:i+tamanho_bloco]
                        cpfs_formatados = ','.join(f"'{cpf}'" for cpf in cpfs_bloco)
                        query = f"SELECT * FROM cliente WHERE id IN ({cpfs_formatados})"
                        dfs_resultados.append(pd.read_sql(query, conn_portal))

                if dfs_resultados:
                    df_pontuacao = pd.concat(dfs_resultados, ignore_index=True)
                    df = df.merge(df_pontuacao, left_on='cpf', right_on='id', how='left').drop(columns=['id'])
                return df
            except Exception:
                logging.exception("Erro Cliente Scoring")
                return df


class NovosDados:
    def executa_em_lotes(self, cursor, conn, sql, dados, descricao, tamanho_lote=1000):
        num_dez_porc = max(1, int(len(dados) * 0.1))
        for i in range(0, len(dados), tamanho_lote):
            cursor.executemany(sql, dados[i:i + tamanho_lote])
            conn.commit()
            if (i + tamanho_lote) % num_dez_porc == 0:
                print(f'Processados {descricao}: ', min(i + tamanho_lote, len(dados)))

    def _processar_telefones(self, df_origem: pd.DataFrame, descricao: str):
        df = df_origem.copy()
        df['telefone'] = df['telefone'].apply(utils_core.Geral.normalizar_numero)
        df['cpf'] = df['cpf'].apply(utils_core.Geral.formatar_cpf)

        df = df.dropna(subset=['telefone', 'cpf'])
        df = df[(df['telefone'].str.len() == 11) & (df['cpf'].str.len() == 14)].copy()

        tuplas_adicionar = list(df[['cpf', 'telefone']].itertuples(index=False, name=None))
        tuplas_clientes = [(cpf,) for cpf in df['cpf'].unique()]
        tuplas_telefone = [(tel,) for tel in df['telefone'].unique()]

        with utils_core.Database('APP_DB_PORTAL') as conn:
            while True:
                try:
                    cur = conn.cursor()
                    self.executa_em_lotes(cur, conn, 'INSERT IGNORE INTO cliente(id) VALUES (%s)', tuplas_clientes, f'{descricao} cliente_scoring')
                    self.executa_em_lotes(cur, conn, 'INSERT IGNORE INTO telefone_scoring(id) VALUES (%s)', tuplas_telefone, f'{descricao} telefone_scoring')
                    self.executa_em_lotes(cur, conn, 'INSERT IGNORE INTO cliente_telefone(cliente_id, telefone_id) VALUES (%s,%s)', tuplas_adicionar, f'{descricao} cliente_telefone')
                    cur.close()
                    break
                except DatabaseError:
                    logging.exception(f"Erro {descricao} novos dados")
                    conn.rollback()
                    time.sleep(random.uniform(30, 60))

    def pan_adicionar_cliente_telefone(self):
        limite, offset = 100000, 0
        try:
            while True:  
                cliente_telefone = pan.Relatorios.lote_cliente_telefone(limite, offset)
                if cliente_telefone.empty: break
                
                self._processar_telefones(cliente_telefone, "NovosDados PAN")
                print(f'Processados: {offset}')
                offset += limite
            return True
        except Exception:
            logging.exception("Erro Panorama Novos dados")
            return False

    def ecb_adicionar_cliente_telefone(self):
        try:
            cliente_telefone = ecb.Relatorios().clientes_telefone().drop_duplicates()
            self._processar_telefones(cliente_telefone, "NovosDados ECB")
            return True
        except Exception:
            logging.exception("Erro Ecb novos dados")
            return False

    def contatos_panorama(self):
        try:
            agora = datetime.datetime.now()
            for ano in range(2000, agora.year + 1):
                for mes in range(1, 13):
                    if ano == agora.year and mes > agora.month:
                        return True
                    
                    ano_fim, mes_fim = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
                    data_inicio, data_fim = f'{ano}-{mes:02d}-01', f'{ano_fim}-{mes_fim:02d}-01'
                    
                    query = f"""
                        WITH telefone_extraido AS (
                            SELECT 
                                t.id AS telemarketing_id,
                                CASE WHEN TRIM(SUBSTR(t.texto, LOCATE('>(', t.texto))) IS NULL THEN NULL
                                     ELSE REPLACE(SUBSTRING(TRIM(SUBSTR(t.texto, LOCATE('>(', t.texto))), 3, 2), '<', '') END AS ddd,
                                CASE WHEN TRIM(SUBSTR(t.texto, LOCATE('>(', t.texto))) IS NULL THEN NULL
                                     ELSE REPLACE(SUBSTRING(TRIM(SUBSTR(t.texto, LOCATE('>(', t.texto))), 6, 9), '<', '') END AS numero
                            FROM telemarketing t
                            WHERE t.relacao='cliente' AND t.dataregistro >= '{data_inicio}' AND t.dataregistro <= '{data_fim}'
                        )
                        SELECT 
                            t.id as telemarketing_id, c.cpf as cliente_id, 
                            CASE WHEN te.ddd IS NULL THEN te.numero ELSE CONCAT(te.ddd, te.numero) END AS telefone_id,
                            st.descricao as status_tabulacao, t.dataregistro as data_tabulacao
                        FROM cliente c  
                        LEFT JOIN telemarketing t ON t.relacao_id = c.id 
                        LEFT JOIN telefone_extraido te ON te.telemarketing_id = t.id
                        LEFT JOIN status_telemarketing st ON t.status_telemarketing_id = st.id 
                        LEFT JOIN usuario u ON t.usuario_id = u.id  
                        WHERE t.relacao='cliente' 
                          AND t.dataregistro >= '{data_inicio}' AND t.dataregistro <= '{data_fim}'
                          AND u.login NOT IN ('luaan.silva','higor.andrade')
                    """ 
                    
                    with pan.db_panorama_connect() as conn:
                        dados = pd.read_sql(query, conn)
                        
                    if dados.empty: continue
                        
                    dados['cliente_id'] = dados['cliente_id'].apply(utils_core.Geral.formatar_cpf)
                    dados['telefone_id'] = dados['telefone_id'].apply(utils_core.Geral.normalizar_numero)
                    dados['data_tabulacao'] = pd.to_datetime(dados['data_tabulacao'], errors='coerce')
                    dados = dados.where(pd.notnull(dados), None)
                    
                    tuplas_adicionar = [
                        (row.telemarketing_id, row.cliente_id, row.telefone_id, row.status_tabulacao, 
                         row.data_tabulacao.to_pydatetime() if isinstance(row.data_tabulacao, pd.Timestamp) else row.data_tabulacao)
                        for row in dados.itertuples(index=False)
                    ]
                    
                    with utils_core.Database('APP_DB_PORTAL') as conn_portal:
                        while True:
                            try:
                                cur = conn_portal.cursor()
                                sql = 'INSERT IGNORE INTO contatos_panorama(telemarketing_id, cliente_id, telefone_id, status_tabulacao, data_tabulacao) VALUES (%s,%s,%s,%s,%s)'
                                self.executa_em_lotes(cur, conn_portal, sql, tuplas_adicionar, 'NovosDados Contatos Panorama')
                                cur.close()
                                break
                            except (DatabaseError, InterfaceError):
                                logging.exception("Erro Contatos Novos dados: Portal 1")
                                time.sleep(random.uniform(30, 60))
            return True
        except Exception:
            logging.exception("Erro Contatos Novos dados")
            return False


class Mensuracao:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def mensurar_efetividade_clientes(self, data_inicio: datetime.datetime, data_fim: datetime.datetime):
        df = self.df.copy()
        df['cliente_id_mensurar_efetividade'] = df['cliente_id_mensurar_efetividade'].apply(utils_core.Geral.formatar_cpf)
        
        tabulacoes_df = pan.Relatorios(data_inicio=data_inicio, data_fim=data_fim).tabulacoes_df(tipo='total')
        tabulacoes_efetivas_df = pan.Relatorios(data_inicio=data_inicio, data_fim=data_fim).tabulacoes_df(tipo='efetiva')
        
        with utils_core.Database('APP_DB_ANALYTICS') as conn:
            query = f"""
                SELECT * FROM producao_extenso 
                WHERE data_contrato >= '{data_inicio.strftime('%Y-%m-%d')}' 
                  AND data_contrato <= '{(data_fim - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}'
            """
            producao_df = pd.read_sql(query, conn)
            
        tabulacoes_df['cpf'] = tabulacoes_df['cpf'].apply(utils_core.Geral.formatar_cpf)
        producao_df['cliente_id'] = producao_df['cliente_id'].apply(utils_core.Geral.formatar_cpf)
        tabulacoes_efetivas_df['cpf'] = tabulacoes_efetivas_df['cpf'].apply(utils_core.Geral.formatar_cpf)
        
        contagem_tabulacoes = tabulacoes_df['cpf'].value_counts().reset_index(name='tabulacoes')
        contagem_tab_efetivas = tabulacoes_efetivas_df['cpf'].value_counts().reset_index(name='tabulacoes_efetivas')
        
        prod_agrupada = producao_df.groupby('cliente_id').agg({
            'Total_Liberado': 'sum',
            'valor_comissao': 'sum',
            'base_comissao': 'sum'
        }).reset_index()
        
        qtd_contratos = producao_df[producao_df['produto'] != 'SEGURO PRESTAMISTA'].groupby('cliente_id').size().reset_index(name='Contratos')

        df = df.merge(contagem_tabulacoes, left_on='cliente_id_mensurar_efetividade', right_on='cpf', how='left').drop(columns=['cpf'])
        df = df.merge(prod_agrupada, left_on='cliente_id_mensurar_efetividade', right_on='cliente_id', how='left').drop(columns=['cliente_id'])
        df = df.merge(contagem_tab_efetivas, left_on='cliente_id_mensurar_efetividade', right_on='cpf', how='left').drop(columns=['cpf'])
        df = df.merge(qtd_contratos, left_on='cliente_id_mensurar_efetividade', right_on='cliente_id', how='left').drop(columns=['cliente_id'])
        
        colunas_fillna = ['tabulacoes', 'Total_Liberado', 'tabulacoes_efetivas', 'Contratos', 'valor_comissao', 'base_comissao']
        df[colunas_fillna] = df[colunas_fillna].fillna(0)
        
        somas = df[colunas_fillna].sum()
        df_resumo = pd.DataFrame({'Campo': somas.index, 'Soma': somas.values.round(2)})
        
        total_linhas = len(df)
        total_tabulados = len(contagem_tabulacoes[contagem_tabulacoes['cpf'].isin(df['cliente_id_mensurar_efetividade'])])
        total_tab_efetivos = len(contagem_tab_efetivas[contagem_tab_efetivas['cpf'].isin(df['cliente_id_mensurar_efetividade'])])
        
        df_resumo['Proporção'] = None
        df_resumo.loc[df_resumo['Campo'] == 'tabulacoes', 'Proporção'] = (total_tabulados / total_linhas) * 100 if total_linhas else 0
        
        df_resumo['Clientes Tabulados'] = None
        df_resumo.loc[df_resumo['Campo'] == 'tabulacoes', 'Clientes Tabulados'] = total_tabulados
        df_resumo.loc[df_resumo['Campo'] == 'tabulacoes_efetivas', 'Clientes Tabulados'] = total_tab_efetivos
        
        rentabilidade = df['valor_comissao'].sum() / df['base_comissao'].sum() if df['base_comissao'].sum() != 0 else 0
        df_resumo['Rentabilidade %'] = None
        df_resumo.loc[df_resumo['Campo'] == 'valor_comissao', 'Rentabilidade %'] = rentabilidade * 100

        return df, df_resumo