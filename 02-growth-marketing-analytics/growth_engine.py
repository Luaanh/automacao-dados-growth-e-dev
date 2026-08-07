import os
import re
import time
import json
import hmac
import hashlib
import datetime
import random
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from selenium.webdriver.common.by import By

import utils_core
import panorama as pan
import disparos

DDD_ESTADO = {
    11: "SP", 12: "SP", 13: "SP", 14: "SP", 15: "SP", 16: "SP", 17: "SP", 18: "SP", 19: "SP",
    21: "RJ", 22: "RJ", 24: "RJ", 27: "ES", 28: "ES",
    31: "MG", 32: "MG", 33: "MG", 34: "MG", 35: "MG", 37: "MG", 38: "MG",
    41: "PR", 42: "PR", 43: "PR", 44: "PR", 45: "PR", 46: "PR",
    47: "SC", 48: "SC", 49: "SC",
    51: "RS", 53: "RS", 54: "RS", 55: "RS",
    61: "DF", 62: "GO", 64: "GO", 63: "TO",
    65: "MT", 66: "MT", 67: "MS", 68: "AC", 69: "RO",
    71: "BA", 73: "BA", 74: "BA", 75: "BA", 77: "BA", 79: "SE",
    81: "PE", 87: "PE", 82: "AL", 83: "PB", 84: "RN",
    85: "CE", 88: "CE", 86: "PI", 89: "PI",
    91: "PA", 93: "PA", 94: "PA", 92: "AM", 97: "AM",
    95: "RR", 96: "AP", 98: "MA", 99: "MA"
}

def _extrair_numeros(valor):
    if pd.isna(valor) or valor is None:
        return None
    val_str = str(valor).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    val_limpo = re.sub(r'\D', '', val_str)
    return val_limpo if val_limpo else None

def _eh_valido(v):
    if pd.isna(v) or v is None:
        return False
    if str(v).strip().lower() in ['nan', 'nat', 'none', '']:
        return False
    return True

class DataEnrichment:
    def __init__(self):
        self.BASE = "https://app.example.com/" 
        
    def criar_sessao_api(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": "Python-GrowthEngine-API-Client"})
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return session

    def selenium_login_to_requests(self):
        load_dotenv()
        creds = os.getenv('APP_GROWTH_USER').split(',')
        login_page = f"{self.BASE}verifica.php"
        payload = {"user": creds[0], "pass": creds[1]}
        
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Chrome)"})
        session.post(login_page, data=payload)
        return session, False

    def consultar_telefone(self, session: requests.Session, cliente_id: str, telefone_exato: str) -> tuple[str, bool]:
        cliente_id_limpo = _extrair_numeros(str(cliente_id).split('.')[0])
        telefone_limpo = _extrair_numeros(str(telefone_exato).split('.')[0])
        
        secret = utils_core.Geral.retornar_valor_env('app_growth_token')
        token_integracao = utils_core.Geral.retornar_valor_env('APP_TOKEN_INTEGRACAO')
        timestamp = int(time.time())
        token = hmac.new(secret.encode(), str(timestamp).encode(), hashlib.sha256).hexdigest()

        payload = {
            "cliente_id": cliente_id_limpo,
            "telefone_exato": telefone_limpo,
            "timestamp": timestamp,
            "token": token,
            "tipo_pesquisa": "telefone",
            "origem": "telefone",
            "tipo": "telefone",
            "token_integracao": token_integracao,
            "utilidade": "enriquecer_dados_growth_analytics"
        }

        url = f"{self.BASE}app-v3/mods/crm/credlink_integrar.php"
        
        try:
            r = session.post(url, data=payload, timeout=20, allow_redirects=True)
            if "1213" in r.text.lower() or "deadlock" in r.text.lower():
                time.sleep(1)
                return cliente_id_limpo, False
            if not r.ok:
                return cliente_id_limpo, False
            dados = r.json()
            return cliente_id_limpo, (dados.get('sucesso') is True)
        except Exception:
            return cliente_id_limpo, False

    def enriquecer_telefones(self, session, lista_dados: list, workers=4) -> dict:
        resultados = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.consultar_telefone, session, cid, tel): cid for cid, tel in lista_dados}
            for future in as_completed(futures):
                try:
                    cid, status = future.result()
                    resultados[cid] = status
                except Exception:
                    resultados[futures[future]] = None
        return resultados

    def info_cliente(self, lista_telefones: list) -> pd.DataFrame:
        if not lista_telefones:
            return pd.DataFrame()
        
        lista_telefones = [_extrair_numeros(t) for t in lista_telefones]
        placeholders = ','.join(['%s'] * len(lista_telefones))
        query = f"""
            SELECT 
                cc.idTabela AS cliente_id, 
                cc.id AS cpf,
                COALESCE(
                    (SELECT l.uf FROM logradouro l WHERE l.cliente_id = cc.idTabela ORDER BY l.id DESC LIMIT 1), 
                'ND') AS UF,
                cc.genero AS SEXO, 
                cc.data_nasc AS DATANASCIMENTO, 
                cc.nome AS nome_cliente_panorama, 
                c.telefone
            FROM (
                SELECT DISTINCT cliente_id, telefone, cpf 
                FROM (
                    SELECT idTabela AS cliente_id, id AS cpf, telefone FROM clientes WHERE telefone IN ({placeholders})
                    UNION ALL
                    SELECT idTabela, id, celular FROM clientes WHERE celular IN ({placeholders})
                    UNION ALL
                    SELECT cc_extra.cliente_id, 99999999999 AS cpf, co.contato AS telefone
                    FROM cliente_contato cc_extra
                    JOIN contato_cliente co ON co.id = cc_extra.contato_id
                    WHERE co.contato IN ({placeholders})
                ) sb
            ) c
            JOIN clientes cc ON cc.idTabela = c.cliente_id
            ORDER BY cc.id DESC
        """
        with utils_core.Database('APP_DB_ANALYTICS') as conn:
            return pd.read_sql(query, conn, params=lista_telefones * 3)

    def consultar_nome(self, session: requests.Session, cliente_id: str) -> tuple[str, bool]:
        cliente_id_limpo = _extrair_numeros(str(cliente_id).split('.')[0]) 
        secret = utils_core.Geral.retornar_valor_env('app_growth_token')
        timestamp = int(time.time())
        token = hmac.new(secret.encode(), str(timestamp).encode(), hashlib.sha256).hexdigest()

        payload = {
            "cliente_id": cliente_id_limpo,
            "timestamp": timestamp,
            "token": token,
            "tipo_pesquisa": "nome",
            "origem": "nome",
            "tipo": "nome",
            "token_integracao": utils_core.Geral.retornar_valor_env('APP_TOKEN_INTEGRACAO'),
            "utilidade": 'enriquecer_dados_growth_analytics'
        }

        url = f"{self.BASE}app-v3/mods/crm/credlink_integrar.php"
        try:
            r = session.post(url, data=payload, timeout=20, allow_redirects=True)
            if "1213" in r.text.lower() or "deadlock" in r.text.lower():
                time.sleep(1)
                return cliente_id_limpo, False
            if not r.ok:
                return cliente_id_limpo, False
            return cliente_id_limpo, (r.json().get('sucesso') is True)
        except Exception:
            return cliente_id_limpo, False

    def enriquecer_nomes(self, session, lista_cliente_id: list, workers=4) -> dict:
        resultados = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.consultar_nome, session, cid): cid for cid in lista_cliente_id}
            for future in as_completed(futures):
                try:
                    cid, status = future.result()
                    resultados[cid] = status
                except Exception:
                    pass
        return resultados

    def cpf_existentes(self, lista_cpfs: list):
        lista_cpfs = [utils_core.Geral.formatar_cpf(cpf) for cpf in lista_cpfs]
        if not lista_cpfs:
            return pd.DataFrame()
        placeholders = ','.join(['%s'] * len(lista_cpfs))
        query = f"SELECT c.id, c.cpf FROM cliente c WHERE c.cpf IN ({placeholders})"
        with utils_core.Database(pan.db_teste_connect()) as conn:
            return pd.read_sql(query, conn, params=lista_cpfs)

    def enriquecer_cpfs(self, driver, dados: pd.DataFrame):
        lista_cpfs = dados['cpf'].apply(utils_core.Geral.formatar_cpf).tolist()
        df_existentes = self.cpf_existentes(lista_cpfs)
        lista_ids_clientes = df_existentes['id'].tolist()
        lista_cpfs_existentes_clientes = df_existentes['cpf'].tolist()
        lista_cpfs = [cpf for cpf in lista_cpfs if cpf not in lista_cpfs_existentes_clientes]
        
        try:
            driver = self.login(headless=False)
            for cpf_cadastrar in lista_cpfs:
                df_cpf_pesquisa = dados[dados['cpf'] == cpf_cadastrar]
                nome = df_cpf_pesquisa['nome'].iloc[0]
                celular = df_cpf_pesquisa['celular'].iloc[0]

                driver.get('https://rs.panoramaemprestimos.com.br/clienteInterno.do?action=novo')
                driver.find_element(By.NAME,'nome').send_keys(nome)
                driver.find_element(By.NAME,'celular').send_keys(re.sub(r'\D', '', celular))
                driver.find_element(By.NAME,'cpf').send_keys(cpf_cadastrar)
                driver.execute_script("enviar_click('clienteInterno.do','salvar')")
                
            df_existentes = self.cpf_existentes(lista_cpfs)
            lista_ids_clientes = df_existentes['id'].tolist()
            for id_cliente in lista_ids_clientes:
                driver.get(f'https://rs.panoramaemprestimos.com.br/clienteInterno.do?action=exibir&codigo={id_cliente}')
                driver.execute_script(f"integrarBanco('{id_cliente}','credlink')'")
        finally:
            if driver:
                driver.quit()
        return lista_ids_clientes

class GrowthEngine:
    def __init__(self):
        importacao_id = 8357
        self.link_inserir = f'http://rs.panoramaemprestimos.com.br/html.do?action=adicionarLeads&idImportacao={importacao_id}&dados='

    def limpeza_leads_enriquecer_panorama(self, df: pd.DataFrame):
        df = df.dropna(subset=['telefone'])
        df['telefone'] = df['telefone'].astype(str).str.replace(r'\D', '', regex=True)
        df = df[(df['telefone'].str.len() >= 10) & (df['telefone'].str.len() <= 11)]
        return df

    def gerar_leads_enriquecer_panorama(self):
        with utils_core.Database('APP_DB_PORTAL') as conn:
            query = """
                SELECT
                    nc.*,
                    nc2.max_valor_fipe,
                    (COALESCE(nc2.max_valor_fipe, nc.valor) - nc.valor) AS diferenca_fipe
                FROM portal.negociacao_cockpit nc
                LEFT JOIN portal.info_panorama_cockpit ipc ON ipc.negociacao_id = nc.id
                LEFT JOIN (
                    SELECT veiculo, MAX(valor_fipe) AS max_valor_fipe
                    FROM portal.negociacao_cockpit
                    WHERE valor_fipe IS NOT NULL
                    GROUP BY veiculo
                ) nc2 ON nc2.veiculo = nc.veiculo
                WHERE
                    nc.enviado IS NULL
                    AND ipc.negociacao_id IS NULL
                    AND nc.telefone IS NOT NULL
                    AND nc.abriu_regua = 'NAO TESTADO'
                    AND nc.canal NOT LIKE '%seguro%'
                    AND LOWER(nc.canal) NOT LIKE '%quitados%'
                    AND nc.ano IS NOT NULL
                    AND nc.veiculo IS NOT NULL
                    AND nc.marca IS NOT NULL
                    AND nc.valor IS NOT NULL
                    AND nc.classificacao_ticket IN ('BAIXO','MÉDIO', 'ALTO','MUITO ALTO')
                    AND nc.tipo_veiculo IN ('MOTO', 'CARRO')
                    AND nc.data_chegada = (SELECT MAX(data_chegada) FROM negociacao_cockpit)
            """
            return pd.read_sql(query, conn)

    def enriquecer_info(self):
        panorama = DataEnrichment()
        LIMITE_PACOTE = 5000
        consultas_realizadas = 0
        session = panorama.criar_sessao_api()

        while True:
            if consultas_realizadas >= LIMITE_PACOTE:
                break 
                
            df = pd.DataFrame()
            try:
                df = self.gerar_leads_enriquecer_panorama()
                df = self.limpeza_leads_enriquecer_panorama(df)
                
                if df.empty:
                    time.sleep(60)
                    continue

                lista_telefones = df['telefone'].unique().tolist()
                consultas_realizadas += len(lista_telefones)
                
                df_info_panorama = panorama.info_cliente(lista_telefones)
                if not df_info_panorama.empty and 'telefone' in df_info_panorama.columns:
                    df_info_panorama = df_info_panorama.drop_duplicates(subset=['telefone'], keep='first')
                
                df_telefones = df.merge(df_info_panorama, how='left', on='telefone')
                df_faltante = df_telefones[df_telefones['cliente_id'].isna()].copy()
                
                def classificar_telefone(telefone: str) -> str:
                    tel = _extrair_numeros(telefone)
                    if not tel: return 'invalido'
                    if len(tel) == 11 and tel[2] == '9': return 'celular'
                    if len(tel) == 10: return 'telefone'
                    return 'invalido'
                
                df_faltante['tipo_contato'] = df_faltante['telefone'].apply(classificar_telefone)
                df_faltante = df_faltante[df_faltante['tipo_contato'] != 'invalido']
                df_celular = df_faltante[df_faltante['tipo_contato'] == 'celular']
                df_fixo = df_faltante[df_faltante['tipo_contato'] == 'telefone']
                
                with utils_core.Database('APP_DB') as conn:
                    cur = conn.cursor()
                    cur.executemany("INSERT INTO clientes (celular) VALUES (%s)", [(_extrair_numeros(t),) for t in df_celular['telefone']])
                    cur.executemany("INSERT INTO clientes (telefone) VALUES (%s)", [(_extrair_numeros(t),) for t in df_fixo['telefone']])
                    conn.commit()

                if not df_info_panorama.empty and 'cliente_id' in df_info_panorama.columns:
                    df_pares = df_info_panorama.dropna(subset=['cliente_id'])[['cliente_id', 'telefone']].drop_duplicates(subset=['cliente_id'])
                    lista_dados = list(df_pares.itertuples(index=False, name=None))
                    if lista_dados:
                        panorama.enriquecer_telefones(session, lista_dados)

                df_info_panorama = panorama.info_cliente(lista_telefones)
                if not df_info_panorama.empty and 'telefone' in df_info_panorama.columns:
                    df_info_panorama = df_info_panorama.drop_duplicates(subset=['telefone'], keep='first')
                    
                df = df.merge(df_info_panorama, how='left', on='telefone')
                df['nome'] = df['nome'].str.upper()
                df['nome_cliente_panorama'] = df['nome_cliente_panorama'].str.upper()
                df = utils_core.Geral.calcular_semelhanca_nomes(df, 'nome', 'nome_cliente_panorama')
                
            finally:
                if not df.empty:
                    colunas_necessarias = ['cpf', 'nome_cliente_panorama', 'SEXO', 'UF', 'semelhanca', 'DATANASCIMENTO']
                    for col in colunas_necessarias:
                        if col not in df.columns:
                            df[col] = None

                    mask_sem_cpf = df['cpf'].isna() | (df['cpf'].astype(str).str.strip() == '') | (df['cpf'].astype(str).str.lower() == 'nan')
                    df.loc[mask_sem_cpf, 'semelhanca'] = 0
                    df.loc[mask_sem_cpf, 'nome_cliente_panorama'] = None

                    try:
                        self.salvar_info_cliente(df)
                    except Exception as erro_db:
                        print(traceback.format_exc())       

    def salvar_info_cliente(self, df):
        df_salvar = df[['id', 'cpf', 'nome_cliente_panorama', 'SEXO', 'UF', 'semelhanca', 'DATANASCIMENTO']].copy()
        df_salvar = df_salvar.sort_values(by='cpf', na_position='first')
        df_salvar["cpf"] = df_salvar["cpf"].apply(_extrair_numeros)

        tuplas_adicionar = [tuple(None if pd.isna(x) else x for x in row) for row in df_salvar.itertuples(index=False, name=None)]

        with utils_core.Database('APP_DB_PORTAL') as conn:
            cur = conn.cursor()
            query = """
                INSERT INTO info_panorama_cockpit (negociacao_id, cpf, nome, genero, estado, semelhanca, data_nascimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    cpf = VALUES(cpf), nome = VALUES(nome), genero = VALUES(genero),
                    estado = VALUES(estado), semelhanca = VALUES(semelhanca), data_nascimento = VALUES(data_nascimento)
            """
            cur.executemany(query, tuplas_adicionar)
            conn.commit()

class DailyReports:
    def __init__(self):
        self.CANAIS_RECOMENDADOS = ['C2C', 'APROVADO NÃO EFETIVADO', 'SIMULAÇÃO DIGITAL - C2C', 'C2C NÃO CONVERTIDO', 'C2C - NAO CORRENTISTA NOVO']
        self.CANAIS_PROIBIDOS = ['QUITADOS - C2C', 'LIQUIDANTES - C2C', 'Quitados', 'Liquidantes']  
        self.COLUNAS = ['nome_cockpit', 'veiculo', 'ano', 'valor', 'telefone', 'email', 'canal', 'cpf', 'semelhanca_nomes', 'classificacao_ticket', 'pontuacao_final', 'ultima_simulacao', 'penultima_simulacao', 'antepenultima_simulacao']
        
        hoje_num = datetime.date.today().strftime('%Y%m%d')
        self.nome_campanha_meta = f'COCKPIT - WHATSAPP - APROVADO NAO EFETIVADO - {hoje_num}'
        self.nome_campanha_meta2 = f'COCKPIT - WHATSAPP - C2C - {hoje_num}'
        self.nome_campanha_meta3 = f'COCKPIT - WHATSAPP - PRIORIDADE 3 - {hoje_num}'
        self.nome_campanha_meta4 = f'COCKPIT - WHATSAPP - PRIORIDADE 4 - {hoje_num}' 
        self.nome_campanha_meta5 = f'COCKPIT - WHATSAPP - PRIORIDADE 5 - {hoje_num}' 
        self.nome_campanha_meta6 = f'COCKPIT - WHATSAPP - PRIORIDADE 6 - {hoje_num}' 
        self.nome_campanha_meta7 = f'COCKPIT - WHATSAPP - PRIORIDADE 7 - {hoje_num}' 

    def gerar_dados(self):
        query = """
            WITH historico_telefones AS (
                SELECT 
                    telefone,
                    COUNT(*) AS qtd_total_historico,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 3 MONTH THEN 1 ELSE 0 END) AS qtd_3_meses,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 1 YEAR THEN 1 ELSE 0 END) AS qtd_1_ano
                FROM portal.negociacao_cockpit
                GROUP BY telefone
            )
            SELECT
                nc.id, nc.nome nome_cockpit, nc.veiculo, nc.ano, nc.valor, nc.data_chegada, nc.data_insercao,
                nc.telefone, nc.email, nc.canal, nc.propostas_enviadas_minha_loja, nc.propostas_enviadas_outras_lojas,
                nc.buscas_portal_wm, ipc.cpf, ipc.nome nome_panorama, nc.marca, nc.genero, nc.estado,
                ipc.data_nascimento, ipc.semelhanca semelhanca_nomes, nc.abriu_regua, nc.valor_fipe, nc.fipe,
                NOW() as data_hora_enviado, nc.ofertas_json, COALESCE(ht.qtd_3_meses, 0) AS qtd_3_meses,
                COALESCE(ht.qtd_1_ano, 0) AS qtd_1_ano, COALESCE(ht.qtd_total_historico, 0) AS qtd_total_historico,
                nc.prioridade, nc.classificacao_ticket, nc.tipo_lead
            FROM portal.negociacao_cockpit AS nc
            JOIN portal.info_panorama_cockpit AS ipc ON nc.id = ipc.negociacao_id
            LEFT JOIN historico_telefones AS ht ON nc.telefone = ht.telefone
            WHERE nc.data_chegada >= NOW() - INTERVAL 15 DAY
            AND nc.enviado IS NULL AND nc.telefone IS NOT NULL
            ORDER BY valor DESC;
        """
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df = pd.read_sql(query, conn)
            
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        if df.empty: return pd.DataFrame()
        
        telefones = df['telefone'].unique().tolist()
        placeholders = ','.join(['%s'] * len(telefones))
        query_tel = f"SELECT contato, tipo_contato, whatsapp FROM contato_cliente WHERE contato IN ({placeholders})"
        
        with utils_core.Database('APP_DB') as conn:
            df_telefones = pd.read_sql(query_tel, conn, params=telefones)
            
        df_telefones['whatsapp'] = df_telefones['whatsapp'].map({1: 'SIM', 0: 'NÃO'})
        df = df.merge(df_telefones, left_on='telefone', right_on='contato', how='left').drop(columns=['contato'])
        return df

    def remarketing(self):
        query = """
            WITH historico_telefones AS (
                SELECT 
                    telefone, COUNT(*) AS qtd_total_historico,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 3 MONTH THEN 1 ELSE 0 END) AS qtd_3_meses,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 1 YEAR THEN 1 ELSE 0 END) AS qtd_1_ano
                FROM portal.negociacao_cockpit
                GROUP BY telefone
            )
            SELECT
                nc.id, nc.nome nome_cockpit, nc.veiculo, nc.ano, nc.valor, nc.data_chegada, nc.data_insercao,
                nc.telefone, nc.email, nc.canal, nc.propostas_enviadas_minha_loja, nc.propostas_enviadas_outras_lojas,
                nc.buscas_portal_wm, ipc.cpf, ipc.nome nome_panorama, nc.genero, nc.estado, ipc.data_nascimento,
                ipc.semelhanca semelhanca_nomes, nc.abriu_regua, nc.valor_fipe, nc.fipe, NOW() as data_hora_enviado,
                nc.ofertas_json, COALESCE(ht.qtd_3_meses, 0) AS qtd_3_meses, COALESCE(ht.qtd_1_ano, 0) AS qtd_1_ano,
                COALESCE(ht.qtd_total_historico, 0) AS qtd_total_historico, nc.remarketing, nc.contagem_remarketing
            FROM portal.negociacao_cockpit AS nc
            JOIN portal.info_panorama_cockpit AS ipc ON nc.id = ipc.negociacao_id
            LEFT JOIN historico_telefones AS ht ON nc.telefone = ht.telefone
            WHERE nc.data_chegada >= '2025-12-03'
            AND nc.enviado IS NULL AND nc.telefone IS NOT NULL AND data_hora_enviado is not null
            ORDER BY valor DESC;
        """
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df = pd.read_sql(query, conn)
            
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        telefones = df['telefone'].unique().tolist()
        placeholders = ','.join(['%s'] * len(telefones))
        query_tel = f"SELECT contato, tipo_contato, whatsapp FROM contato_cliente WHERE contato IN ({placeholders})"
        
        with utils_core.Database('APP_DB') as conn:
            df_telefones = pd.read_sql(query_tel, conn, params=telefones)
            
        df_telefones['whatsapp'] = df_telefones['whatsapp'].map({1: 'SIM', 0: 'NÃO'})
        df = df.merge(df_telefones, left_on='telefone', right_on='contato', how='left').drop(columns=['contato'])
        return df

    def gerar_arquivos_diarios(self, tipo=False, modo_planilha='integrada', usuarios_alvo=None):
        df = self.gerar_dados()
        if tipo == 'CRM':
            dfs_saida = self.gerar_leads_crm_planilha(df, usuarios_alvo)
        else:
            dfs_saida = self.gerar_dataframes_limpeza_diario(df, usuarios_alvo)
            
        CAMINHO_REDE = self.pasta_destino()
        mapa_campanhas = {
            'CRM': 9011,
            'CRM_CONSULTOR': 9014,
            'CRM_PLANILHA': 15422,
            'CRM_WHATSAPP': self.nome_campanha_meta,
            'CRM_WHATSAPP2': self.nome_campanha_meta2,
            'CRM_WHATSAPP3': self.nome_campanha_meta3,
            'CRM_WHATSAPP4': self.nome_campanha_meta4,
            'CRM_WHATSAPP5': self.nome_campanha_meta5,
            'CRM_WHATSAPP6': self.nome_campanha_meta6,
            'CRM_WHATSAPP7': self.nome_campanha_meta7
        }

        for plataforma, df_saida in dfs_saida.items():
            if plataforma in ['Consultores', 'Consultores_CRM'] or modo_planilha == 'pura':
                for (nome_consultor, usuario_id), df_consultor in df_saida.groupby(['consultor', 'usuario_id']):
                    nome = nome_consultor.split(' ')
                    nome_arquivo = f"leads_{plataforma}_{nome[0]}_{nome[1]}"
                    caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                    indice_arquivo = 1
                    
                    while os.path.exists(caminho_arquivo):
                        indice_arquivo += 1
                        nome_arquivo = f"leads_{plataforma}_{nome[0]}_{nome[1]}_{indice_arquivo}"
                        caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                        
                    colunas = ['nome_cockpit', 'veiculo', 'ano', 'valor', 'telefone', 'email', 'canal', 'cpf', 'nome_panorama', 'genero', 'estado', 'data_nascimento', 'semelhanca_nomes', 'classificacao_ticket', 'pontuacao_final', 'usuario_id', 'data_chegada', 'marca']
                    df_arquivo = df_consultor[colunas]
                    utils_core.GerarRelatorios({'LEADS': df_arquivo}, CAMINHO_REDE, nome_arquivo).gerar_relatorios()
                    self.gerar_envio(df_consultor, num_enviado=1, tipo_envio='CONSULTOR')

            elif plataforma in ['CRM_PLANILHA1', 'CRM_PLANILHA2']:
                for nome_campanha, df_consultor in df_saida.groupby(['nome_campanha']):
                    nome_arquivo = f"leads_{nome_campanha[0]}"
                    caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                    indice_arquivo = 1
                    
                    while os.path.exists(caminho_arquivo):
                        indice_arquivo += 1
                        nome_arquivo = f"leads_{nome_campanha[0]}_{indice_arquivo}"
                        caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                        
                    utils_core.GerarRelatorios({'LEADS': df_consultor}, CAMINHO_REDE, nome_arquivo).gerar_relatorios()
                    self.gerar_envio(df_consultor, num_enviado=1, tipo_envio='CRM')

            elif plataforma in mapa_campanhas:
                crm_whatsapp = 'WHATSAPP' in plataforma
                alvo = mapa_campanhas[plataforma]
                
                with utils_core.Database('APP_DB') as conn:
                    cur = conn.cursor()
                    if isinstance(alvo, str):
                        cur.execute("SELECT id FROM campanha WHERE descricao = %s", (alvo,))
                        row = cur.fetchone()
                        if not row:
                            raise Exception('ERRO CAMPANHA META')
                        campanha_alvo = row[0]
                    else:
                        campanha_alvo = alvo

                    fazer_integracao = not (plataforma == 'CRM_PLANILHA' and modo_planilha == 'pura')
                    
                    if fazer_integracao:
                        usuarios_campanha = usuarios_alvo if usuarios_alvo else []
                        if plataforma != 'CRM_PLANILHA' and not usuarios_campanha:
                            cur.execute("SELECT usuario_id FROM campanha_usuario WHERE campanha_id = %s", (campanha_alvo,))
                            usuarios_campanha = [r[0] for r in cur.fetchall()]
                            if usuarios_campanha:
                                random.shuffle(usuarios_campanha)

                        total_usuarios = len(usuarios_campanha)
                        idx_usuario = 0

                        df_saida['cpf_limpo'] = df_saida['cpf'].apply(_extrair_numeros)
                        df_saida['telefone_limpo'] = df_saida['telefone'].apply(_extrair_numeros)
                        cpfs = [c for c in df_saida['cpf_limpo'].unique() if c]
                        telefones = [t for t in df_saida['telefone_limpo'].unique() if t]

                        query_clientes = "SELECT c.idTabela, COALESCE(c.celular, c.telefone) telefone FROM clientes c JOIN campanha_cliente cc ON cc.cliente_id = c.idTabela AND cc.campanha_id = %s"
                        df_clientes = pd.read_sql(query_clientes, conn, params=[campanha_alvo])
                        telefones_clientes = [_extrair_numeros(t) for t in df_clientes['telefone'].unique() if t]
                        
                        df_negociacao = pd.DataFrame(columns=['id', 'telefone', 'data_chegada'])
                        if telefones_clientes:
                            with utils_core.Database('APP_DB_PORTAL') as conn_portal:
                                p2 = ','.join(['%s'] * len(telefones_clientes))
                                filtro = "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '')"
                                df_negociacao = pd.read_sql(f"SELECT id, telefone, data_chegada FROM negociacao_cockpit WHERE {filtro} IN ({p2})", conn_portal, params=telefones_clientes)
                        
                        df_negociacao['telefone_merge'] = df_negociacao['telefone'].apply(_extrair_numeros)
                        df_clientes['telefone_merge'] = df_clientes['telefone'].apply(_extrair_numeros)
                        df_merge = df_clientes.merge(df_negociacao, on='telefone_merge', how='left')

                        hoje = pd.Timestamp.today().normalize()
                        df_merge['data_chegada'] = pd.to_datetime(df_merge['data_chegada'], errors='coerce').dt.normalize()
                        df_merge = df_merge.dropna(subset=['data_chegada'])
                        
                        if not df_merge.empty:
                            df_merge['dias_uteis'] = np.busday_count(df_merge['data_chegada'].values.astype('datetime64[D]'), hoje.to_datetime64().astype('datetime64[D]'))
                            df_filtrado = df_merge[df_merge['dias_uteis'] > 1]
                            lista_cliente_id = df_filtrado['idTabela'].tolist()
                            
                            if lista_cliente_id:
                                placeholders_ids = ','.join(['%s'] * len(lista_cliente_id))
                                cur.execute(f"SELECT DISTINCT relacao_id FROM telemarketing WHERE relacao_id IN ({placeholders_ids}) AND campanha_id IN (9011, 9014, 15422)", lista_cliente_id)
                                clientes_com_contato = [r[0] for r in cur.fetchall()]
                                
                                df_realmente_sem_contato = df_filtrado[~df_filtrado['idTabela'].isin(clientes_com_contato)]
                                lista_sem_contato = df_realmente_sem_contato['idTabela'].tolist()
                                ids_neg_sem_contato = df_realmente_sem_contato['id'].dropna().astype(int).tolist()
                                
                                if lista_sem_contato and not crm_whatsapp and campanha_alvo != 15422:
                                    p_del = ','.join(['%s'] * len(lista_sem_contato))
                                    cur.execute(f"DELETE FROM campanha_cliente WHERE cliente_id IN ({p_del}) AND campanha_id = %s", lista_sem_contato + [campanha_alvo])
                                    
                                    if ids_neg_sem_contato:
                                        p_up = ','.join(['%s'] * len(ids_neg_sem_contato))
                                        with utils_core.Database('APP_DB_PORTAL') as conn_portal:
                                            cur_p = conn_portal.cursor()
                                            cur_p.execute(f"UPDATE negociacao_cockpit SET tipo_envio = NULL, data_hora_enviado = NULL, enviado = NULL WHERE id IN ({p_up})", ids_neg_sem_contato)
                                            conn_portal.commit()

                        mapa_clientes = {}
                        if cpfs:
                            cur.execute(f"SELECT id, idTabela FROM clientes WHERE id IN ({','.join(['%s'] * len(cpfs))})", cpfs)
                            for cid, idTabela in cur.fetchall():
                                mapa_clientes[str(cid)] = idTabela

                        if telefones:
                            ptel = ','.join(['%s'] * len(telefones))
                            f_tel = "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '')"
                            f_cel = "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(celular, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '')"
                            cur.execute(f"SELECT idTabela, {f_tel} as tel, {f_cel} as cel FROM clientes WHERE {f_tel} IN ({ptel}) OR {f_cel} IN ({ptel})", telefones + telefones)
                            for idTabela, tel, cel in cur.fetchall():
                                if tel: mapa_clientes[str(tel)] = idTabela
                                if cel: mapa_clientes[str(cel)] = idTabela

                        clientes_ids_encontrados = list(set(mapa_clientes.values()))
                        clientes_bloqueados = set()
                        
                        if clientes_ids_encontrados:
                            p_chk = ','.join(['%s'] * len(clientes_ids_encontrados))
                            cur.execute(f"SELECT DISTINCT cc.cliente_id FROM campanha_cliente cc JOIN campanha c ON c.id = cc.campanha_id WHERE cc.cliente_id IN ({p_chk}) AND (cc.campanha_id IN (9011, 9014, 15422) OR c.descricao LIKE 'COCKPIT - WHATSAPP%')", clientes_ids_encontrados)
                            clientes_bloqueados = {r[0] for r in cur.fetchall()}
                        conn.commit()

                        dict_batch_dados, dict_batch_campanha, batch_telemarketing = {}, {}, []

                        for row in df_saida.itertuples(index=False):
                            cpf = getattr(row, 'cpf_limpo', '')
                            telefone = getattr(row, 'telefone_limpo', '')
                            data_nasc = getattr(row, 'data_nascimento', '').strftime('%d/%m/%Y') if getattr(row, 'data_nascimento', None) else ''
                            
                            if crm_whatsapp:
                                cpf_aviso = utils_core.Geral.formatar_cpf(cpf) if cpf else ''
                                dados_aviso = {
                                    "utilidade": 'disparo_meta_whatsapp_growth_analytics',
                                    "telefone": telefone,
                                    "mensagem": f"O cliente {getattr(row, 'nome_cockpit', '')} recebeu um disparo whatsapp, segue dados: \n"
                                                f"Abriu régua: {getattr(row, 'abriu_regua', '')}\nVeículo - Ano: {getattr(row, 'veiculo', '')} - {getattr(row, 'ano', '')}\n"
                                                f"Marca: {getattr(row, 'marca', '')}\ncpf: {cpf_aviso}\nData Nascimento: {data_nasc}\nValor: {getattr(row, 'valor', '')}\n"
                                                f"Canal: {getattr(row, 'canal', '')}\nTelefone: {telefone}\nSemelhança: {getattr(row, 'semelhanca_nomes', '')}"
                                }
                                try:
                                    disparos.Disparo().enviar_aviso(dados_aviso)
                                    time.sleep(1)
                                except Exception:
                                    disparos.Disparo().enviar_aviso(dados_aviso)

                            cliente_id = mapa_clientes.get(cpf) or mapa_clientes.get(telefone)
                            if not cliente_id or cliente_id in clientes_bloqueados:
                                continue

                            nome_cockpit = getattr(row, 'nome_cockpit', '')
                            primeiro_nome = nome_cockpit.split()[0].capitalize() if nome_cockpit else ''
                            
                            dados = {
                                "Nome Cockpit": {"valor": nome_cockpit, "mapeamento": "Nome Cockpit"},
                                "Primeiro Nome Cockpit": {"valor": primeiro_nome, "mapeamento": "Primeiro Nome Cockpit"},
                                "Veículo": {"valor": getattr(row, 'veiculo', ''), "mapeamento": "Veículo"},
                                "Ano": {"valor": getattr(row, 'ano', ''), "mapeamento": "Ano"},
                                "Valor": {"valor": str(getattr(row, 'valor', '')), "mapeamento": "Valor"},
                                "Canal": {"valor": getattr(row, 'canal', ''), "mapeamento": "Canal"},
                                "Semelhança": {"valor": getattr(row, 'semelhanca_nomes', ''), "mapeamento": "Semelhança"}
                            }
                            
                            if campanha_alvo == 9011 or crm_whatsapp:
                                val_entrada = getattr(row, 'entrada_recomendada', None)
                                val_minimo = getattr(row, 'valor_minimo', None)
                                modelo_sel = getattr(row, 'modeloSelecionado', None)
                                dados['Entrada Recomendada'] = {"valor": str(val_entrada) if _eh_valido(val_entrada) else 'R$ 0,00', "mapeamento": "Entrada"} 
                                dados["Valor Mínimo"] = {"valor": str(val_minimo) if _eh_valido(val_minimo) else 'R$ 0,00', "mapeamento": "Valor Mínimo"}
                                dados["Modelo Selecionado"] = {"valor": str(modelo_sel) if _eh_valido(modelo_sel) else 'ERRO MODELO', "mapeamento": "Modelo Selecionado"}
                                
                                for i in range(1, 5):
                                    qtd = getattr(row, f'oferta_{i}_quantidade', None)
                                    val = getattr(row, f'oferta_{i}_valor_parcela', None)
                                    if _eh_valido(qtd) and _eh_valido(val):
                                        try: qtd_int = int(float(qtd))
                                        except Exception: qtd_int = qtd
                                        dados[f"Oferta {i}"] = {"valor": f"{qtd_int}x de {val}", "mapeamento": f"Parcela_{i}"}

                            dict_batch_dados[cliente_id] = (cliente_id, json.dumps(dados, ensure_ascii=False))

                            if cliente_id not in dict_batch_campanha:
                                if plataforma == 'CRM_PLANILHA':
                                    uid = getattr(row, 'usuario_id', None)
                                    dict_batch_campanha[cliente_id] = (campanha_alvo, cliente_id, uid)
                                    if pd.notna(uid):
                                        batch_telemarketing.append((campanha_alvo, int(uid), cliente_id))
                                else:
                                    uid = usuarios_campanha[idx_usuario] if total_usuarios > 0 else None
                                    dict_batch_campanha[cliente_id] = (campanha_alvo, cliente_id, uid)
                                    if total_usuarios > 0: idx_usuario = (idx_usuario + 1) % total_usuarios

                        if dict_batch_dados:
                            b_dados = list(dict_batch_dados.values())
                            p_del = ','.join(['%s'] * len(b_dados))
                            cur.execute(f"DELETE FROM clientes_dados_extras WHERE cliente_id IN ({p_del}) AND tipo = 'prioridade'", [str(i[0]) for i in b_dados])
                            cur.executemany("INSERT INTO clientes_dados_extras (cliente_id, tipo, dados_json, dataregistro) VALUES (%s, 'prioridade', %s, NOW())", b_dados)

                        if dict_batch_campanha:
                            cur.executemany("INSERT INTO campanha_cliente (campanha_id, cliente_id, usuario_id) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE usuario_id = IF(usuario_id IS NULL, VALUES(usuario_id), usuario_id)", list(dict_batch_campanha.values()))

                        if plataforma == 'CRM_PLANILHA' and batch_telemarketing:
                            cur.executemany("INSERT INTO telemarketing (campanha_id, usuario_id, relacao_id, texto, status_telemarketing_id, datacontato, dataregistro, relacao) VALUES (%s, %s, %s, 'ENVIADO PLANILHA', 499, NOW(), NOW(), 'cliente')", batch_telemarketing)

                        conn.commit()

                if plataforma == 'CRM_PLANILHA':
                    for (nome_consultor, usuario_id), df_consultor in df_saida.groupby(['consultor', 'usuario_id']):
                        nome = nome_consultor.split(' ')
                        nome_arquivo = f"leads_{plataforma}_{nome[0]}_{nome[1]}"
                        caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                        indice_arquivo = 1
                        
                        while os.path.exists(caminho_arquivo):
                            indice_arquivo += 1
                            nome_arquivo = f"leads_{plataforma}_{nome[0]}_{nome[1]}_{indice_arquivo}"
                            caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
                            
                        cols = ['nome_cockpit', 'veiculo', 'ano', 'valor', 'telefone', 'email', 'canal', 'cpf', 'data_chegada', 'nome_panorama', 'genero', 'estado', 'data_nascimento', 'semelhanca_nomes', 'classificacao_ticket', 'usuario_id']
                        utils_core.GerarRelatorios({'LEADS': df_consultor[cols]}, CAMINHO_REDE, nome_arquivo).gerar_relatorios()
                        self.gerar_envio(df_consultor, num_enviado=1, tipo_envio='CONSULTOR')
                else:
                    self.gerar_envio(df_saida, num_enviado=1, tipo_envio='CRM')
                    
            elif plataforma in ['SMS', 'SMS_IPVA', 'SMS_ABRIU_NAO_CONTATADO', 'SMS_REMARKETING']:
                if 'remarketing' in plataforma.lower():
                    self.gerar_remarketing(df_saida)
                else:
                    self.gerar_envio(df_saida, num_enviado=1, tipo_envio='SMS')

            nome_arquivo = f"df_consulta_{plataforma}.xlsx"
            caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)
            indice_arquivo = 1
            
            while os.path.exists(caminho_arquivo):
                indice_arquivo += 1
                nome_arquivo = f"df_consulta_{plataforma}_{indice_arquivo}.xlsx"
                caminho_arquivo = os.path.join(CAMINHO_REDE, nome_arquivo)

            df_saida.to_excel(caminho_arquivo, index=False)
            df_saida[['nome_cockpit', 'telefone', 'cpf']].to_csv(caminho_arquivo.replace('.xlsx', '.csv'), index=False, sep=';', encoding='utf-8-sig')

    def pasta_destino(self):
        REDE_DADOS_COLETADOS = r'C://Users/luaan.silva/Desktop/Leads_growth_analytics'
        data_hoje = datetime.datetime.today().strftime('%d-%m-%Y')
        pastas = [p for p in os.listdir(REDE_DADOS_COLETADOS) if os.path.isdir(os.path.join(REDE_DADOS_COLETADOS, p))]
        pasta_existente = next((p for p in pastas if p.endswith(data_hoje)), None)
        
        if pasta_existente:
            DATA_HOJE_CAMINHO = pasta_existente
        else:
            numero_alvo = 1
            while True:
                if not any(p.startswith(f"{numero_alvo} -") for p in pastas):
                    DATA_HOJE_CAMINHO = f"{numero_alvo} - {data_hoje}"
                    os.makedirs(os.path.join(REDE_DADOS_COLETADOS, DATA_HOJE_CAMINHO), exist_ok=True)
                    break
                numero_alvo += 1
        return os.path.join(REDE_DADOS_COLETADOS, DATA_HOJE_CAMINHO)

    def gerar_envio(self, df, num_enviado, tipo_envio):
        ids_enviados = [(num_enviado, tipo_envio, nid) for nid in df['id'].tolist()]
        with utils_core.Database('APP_DB_PORTAL') as conn:
            cur = conn.cursor()
            cur.executemany('UPDATE portal.negociacao_cockpit SET enviado = %s, data_hora_enviado = NOW(), tipo_envio = %s WHERE id = %s', ids_enviados)
            conn.commit()

    def gerar_remarketing(self, df):
        ids_enviados = [(nid,) for nid in df['id'].tolist()]
        with utils_core.Database('APP_DB_PORTAL') as conn:
            cur = conn.cursor()
            cur.executemany('UPDATE portal.negociacao_cockpit SET remarketing = NOW(), contagem_remarketing = contagem_remarketing + 1 WHERE id = %s', ids_enviados)
            conn.commit()

    def gerar_dataframes_limpeza_diario(self, df, usuarios_alvo=None):
        return {'CRM_PLANILHA': self.df_consultores(self.df_enriquecer(df), usuarios_alvo)}

    def df_crm_geral(self, df, usuarios_alvo=None):
        qtd_consultor, _, _ = self.qtd_consultores(usuarios_alvo)
        df_crm = df[(df['canal'].isin(self.CANAIS_RECOMENDADOS)) & (df['abriu_regua'] == 'NAO TESTADO') & (df['prioridade'] == 1) & (df['semelhanca_nomes'] < 80)].copy()
        return df_crm.sample(min(100 * qtd_consultor, len(df_crm)), random_state=42)

    def tratar_json_completo(self, df):
        def safe_load(x):
            if pd.isna(x): return {}
            try:
                d = json.loads(x) if isinstance(x, str) else x
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}

        df['ofertas_dict'] = df['ofertas_json'].apply(safe_load)
        df['entrada_recomendada'] = df['ofertas_dict'].apply(lambda x: x.get('entradaRecomendada'))
        df['valor_minimo'] = df['ofertas_dict'].apply(lambda x: x.get('valorMinimo'))

        def expandir_parcelas(row):
            parcelas = row.get('parcelas', [])
            if not isinstance(parcelas, list): return pd.Series(dtype='object')
            d = {}
            for i, p in enumerate(parcelas[:3], 1):
                if isinstance(p, dict):
                    d[f'oferta_{i}_quantidade'] = p.get('quantidade')
                    d[f'oferta_{i}_valor_parcela'] = p.get('valor')
            return pd.Series(d)

        df = pd.concat([df, df['ofertas_dict'].apply(expandir_parcelas)], axis=1).drop(columns=['ofertas_dict'])
        return df

    def df_crm(self, df):
        df_crm = df[(df['canal'].isin(self.CANAIS_RECOMENDADOS)) & (df['abriu_regua'] == 'SIM') & (df['prioridade'] == 1)].copy()
        return df_crm.sample(len(df_crm), random_state=42)

    def gerar_leads_crm_planilha(self, df, usuarios_alvo=None):
        df_enriquecido = self.df_enriquecer(df)
        configuracoes = [
            {'chave': 'CRM_PLANILHA1', 'nome': self.nome_campanha_meta, 'pri': 1, 'tipo': None, 'lim': None, 'q3': True},
            {'chave': 'CRM_PLANILHA2', 'nome': self.nome_campanha_meta2, 'pri': 2, 'tipo': None, 'lim': None, 'q3': True},
        ]
        
        resultados = {}
        for c in configuracoes:
            df_g = self._df_crm_meta_generico(df_enriquecido, c['nome'], c['pri'], c['tipo'], 1000, c['lim'], c['q3'])
            df_g['nome_campanha'] = c['nome']
            resultados[c['chave']] = df_g
            df_enriquecido = df_enriquecido[~df_enriquecido['id'].isin(df_g['id'])]
        return resultados

    def gerar_leads_crm(self, df, usuarios_alvo=None):
        df_enriquecido = self.df_enriquecer(df)
        configuracoes = [
            {'chave': 'CRM_WHATSAPP', 'nome': self.nome_campanha_meta, 'pri': 1, 'tipo': None, 'lim': None},
            {'chave': 'CRM_WHATSAPP2', 'nome': self.nome_campanha_meta2, 'pri': 2, 'tipo': None, 'lim': None},
        ]
        
        resultados = {}
        for c in configuracoes:
            df_g = self._df_crm_meta_generico(df_enriquecido, c['nome'], c['pri'], c['tipo'], 1000, c['lim'], None)
            resultados[c['chave']] = df_g
            df_enriquecido = df_enriquecido[~df_enriquecido['id'].isin(df_g['id'])]
        return resultados

    def _df_crm_meta_generico(self, df, nome_campanha, prioridade, tipo_lead=None, limite_bd=1000, limite_saida=None, qtd_3_meses=None):
        with utils_core.Database('APP_DB') as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM campanha WHERE descricao = %s", (nome_campanha,))
            row = cur.fetchone()
            if row:
                campanha_id = row[0]
            else:
                cur.execute("INSERT INTO campanha (descricao, registro, inicio, demanda, ativo, cor, usuario_criador_id) VALUES (%s, NOW(), CURDATE(), 'sequencial', 1, '#ffffffff', 30209)", (nome_campanha,))
                conn.commit()
                cur.execute("SELECT LAST_INSERT_ID()")
                campanha_id = cur.fetchone()[0]
                
            cur.execute("SELECT COUNT(*) FROM campanha_cliente WHERE campanha_id = %s", (campanha_id,))
            contagem_crm = cur.fetchone()[0]

        if contagem_crm >= limite_bd:
            return df.head(0)

        df_crm = df[(df['canal'].isin(self.CANAIS_RECOMENDADOS)) & (df['prioridade'] == prioridade)].copy()
        if tipo_lead: df_crm = df_crm[df_crm['tipo_lead'] == tipo_lead]
        if qtd_3_meses: df_crm = df_crm[df_crm['qtd_3_meses'] == 1]
        
        espaco_disponivel = limite_bd - contagem_crm
        tamanho_amostra = min(espaco_disponivel, len(df_crm))
        
        if tamanho_amostra > 0:
            df_crm = df_crm.sample(tamanho_amostra, random_state=42)
            if limite_saida is not None: df_crm = df_crm.head(limite_saida)
            return df_crm
        return df.head(0)

    def ultimos_veiculos(self, lista_ids: list):
        builder = utils_core.QueryBuilder()
        builder.add_in_clause('id NOT', lista_ids)
        where_clause, params = builder.build()
        query = f"""
            WITH ultimos AS (
                SELECT telefone, veiculo, ano, valor, data_chegada, data_insercao,
                ROW_NUMBER() OVER (PARTITION BY telefone ORDER BY data_chegada DESC, data_insercao DESC) AS rn
                FROM negociacao_cockpit {where_clause}
            )
            SELECT telefone,
                MAX(CASE WHEN rn = 1 THEN CONCAT(veiculo, ' - ', ano, ' - ', valor) END) AS ultima_simulacao,
                MAX(CASE WHEN rn = 2 THEN CONCAT(veiculo, ' - ', ano, ' - ', valor) END) AS penultima_simulacao,
                MAX(CASE WHEN rn = 3 THEN CONCAT(veiculo, ' - ', ano, ' - ', valor) END) AS antepenultima_simulacao
            FROM ultimos WHERE rn <= 3 GROUP BY telefone ORDER BY telefone;
        """
        with utils_core.Database('APP_DB_PORTAL') as conn:
            return pd.read_sql(query, conn, params=params)

    def df_consultores(self, df, usuarios_alvo=None):
        hoje = pd.Timestamp.today().normalize()
        inicio = hoje - pd.offsets.BDay(2)
        df = df[(~df['canal'].isin(self.CANAIS_PROIBIDOS)) & (~df['canal'].isna()) & (pd.to_datetime(df['data_chegada']).dt.normalize() >= inicio) & (pd.to_datetime(df['data_chegada']).dt.normalize() <= hoje) & (df['prioridade'] == 3)]
        
        qtd_consultores, nomes, ids_consultores = self.qtd_consultores(usuarios_alvo)
        capacidade_total = qtd_consultores * 500
        
        if len(df) <= capacidade_total:
            repeat_count = int(np.ceil(len(df)/max(1, len(nomes))))
            df['consultor'] = np.tile(nomes, repeat_count)[:len(df)]
            df['usuario_id'] = np.tile(ids_consultores, repeat_count)[:len(df)]
            return df

        df_melhores = df.head(capacidade_total)
        df_restante = df[~df['id'].isin(df_melhores['id'])]
        df_extra = df_restante.sample(n=min(max(1, int(capacidade_total * 0.05)), len(df_restante)), random_state=42) if not df_restante.empty else pd.DataFrame(columns=df.columns)
        
        df_final = pd.concat([df_melhores, df_extra], ignore_index=True).sample(frac=1, random_state=42).reset_index(drop=True).head(capacidade_total)
        df_final['consultor'] = np.repeat(nomes, 500)[:len(df_final)]
        df_final['usuario_id'] = np.repeat(ids_consultores, 500)[:len(df_final)]
        return df_final

    def df_enriquecer(self, df):
        df['valor'] = df['valor'].fillna(0)
        df["classificacao_ticket"] = "NÃO SIMULADO"
        df.loc[df["valor"] > 0, "classificacao_ticket"] = pd.cut(df.loc[df["valor"] > 0, "valor"], bins=[0, 40000, 70000, 100000, float('inf')], labels=["Baixo", "Médio", "Alto", "Muito Alto"], right=False)
        
        df['ano_inicio'] = pd.to_numeric(df['ano'].str.split('/').str[0], errors='coerce')
        df['data_chegada'] = pd.to_datetime(df['data_chegada'], errors='coerce')
        df['data_hora_enviado'] = pd.to_datetime(df['data_hora_enviado'], errors='coerce')
        df['dias_para_envio'] = (df['data_hora_enviado'] - df['data_chegada']).dt.days
        
        df = self.tratar_json_completo(df)
        df = df.merge(self.ultimos_veiculos([int(x) for x in df['id'].unique()]), on='telefone', how='left')
        return df

    def qtd_consultores(self, usuarios_alvo=None):
        with utils_core.Database('APP_DB_ANALYTICS') as conn:
            query = "SELECT f.id AS usuario_id, f.nome FROM funcionarios f JOIN cargos c ON c.id = f.cargo_id WHERE f.id IN (30755,30480,29149)"
            if usuarios_alvo:
                query += f" AND f.id IN ({','.join([str(int(u)) for u in usuarios_alvo])})"
            df = pd.read_sql(query, conn)
        return len(df), df['nome'].to_list(), df['usuario_id'].to_list()

class DashGrowth:
    def classificacao_genero(self):
        classificador = utils_core.ClassificadorGenero()
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df = pd.read_sql("SELECT id, nome FROM negociacao_cockpit WHERE data_chegada >= CURDATE() - INTERVAL 30 DAY", conn)
            cursor = conn.cursor()
            for row in df.itertuples(index=False):
                genero = classificador.inferir_genero(row.nome)
                if genero in ('M', 'F'):
                    cursor.execute("UPDATE negociacao_cockpit SET genero = %s WHERE id = %s", (genero, row.id))
            conn.commit()

    def atualizar_estado_por_telefone(self):
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df = pd.read_sql("SELECT id, telefone FROM negociacao_cockpit WHERE telefone IS NOT NULL AND (estado IS NULL OR estado = '')", conn)
            cursor = conn.cursor()
            for row in df.itertuples(index=False):
                estado = utils_core.Geral.inferir_estado_por_telefone(row.telefone)
                if estado:  
                    cursor.execute("UPDATE negociacao_cockpit SET estado = %s WHERE id = %s", (estado, row.id))
            conn.commit()

    def comissao_estimada(self):
        query = """
            SELECT p.id, ila.pcila_txa,
            ROUND((valor_veiculo * p2.cms_sem_ila) - (valor_veiculo * p2.cms_sem_ila * (pcila_txa / 100)), 2) AS comissao_estimada_txa,
            ROUND(CASE WHEN flag_estudo = 'N' THEN (valor_veiculo * (p2.cms_sem_ila * 0.66)) - (valor_veiculo * (p2.cms_sem_ila * 0.66) * (pcila_txa / 100)) ELSE 0 END, 2) AS comissao_estimada_plu,
            ROUND(((valor_veiculo * p2.cms_sem_ila) - (valor_veiculo * p2.cms_sem_ila * (pcila_txa / 100))) +
                  (CASE WHEN flag_estudo = 'N' THEN (valor_veiculo * (p2.cms_sem_ila * 0.66)) - (valor_veiculo * (p2.cms_sem_ila * 0.66) * (pcila_txa / 100)) ELSE 0 END), 2) - p2.repasse_parceiro AS comissao_estimada_total
            FROM producao_fin_banco p
            JOIN pc_ila_financiamento ila ON ila.ano_mes = DATE_FORMAT(p.data_contrato, '%Y-%m')
            JOIN (
                SELECT id, (CAST(REPLACE(regra, 'R', '') AS UNSIGNED) * 1.2) / 100 AS cms_sem_ila,
                       CASE WHEN origem_venda = 'PARCEIRO' THEN valor_veiculo*0.015 ELSE 0 END as repasse_parceiro
                FROM producao_fin_banco
            ) p2 ON p2.id = p.id;
        """
        with utils_core.Database('APP_DB') as conn:
            df = pd.read_sql(query, conn)[['comissao_estimada_txa', 'comissao_estimada_total', 'comissao_estimada_plu', 'id']]
            dados = [tuple(None if pd.isna(x) else x for x in r) for r in df.itertuples(index=False, name=None)]
            cursor = conn.cursor()
            cursor.executemany("UPDATE producao_fin_banco SET comissao_estimada_txa = %s, comissao_estimada_total = %s, comissao_estimada_plu = %s WHERE id = %s", dados)
            conn.commit()

    def classificacao_ticket_db(self):
        with utils_core.Database('APP_DB') as conn:
            df = pd.read_sql('SELECT id, valor_veiculo FROM producao_fin_banco', conn)
            df["classificacao_ticket"] = pd.cut(df["valor_veiculo"], bins=[0, 40000, 70000, 100000, float('inf')], labels=["Baixo", "Médio", "Alto", "Muito Alto"], right=False)
            cursor = conn.cursor()
            for index, row in df.iterrows():
                if pd.notnull(row['classificacao_ticket']):
                    cursor.execute("UPDATE producao_fin_banco SET classificacao_ticket = %s WHERE id = %s", (row['classificacao_ticket'], row['id']))
            conn.commit()

    def app(self):
        self.atualizar_estado_por_telefone()
        self.classificacao_ticket_db()
        self.classificacao_genero()
        self.comissao_estimada()

class Classificacao:
    def gerar_dados(self):
        query = """
            WITH historico_telefones AS (
                SELECT telefone, COUNT(*) AS qtd_total_historico,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 3 MONTH THEN 1 ELSE 0 END) AS qtd_3_meses,
                    SUM(CASE WHEN data_chegada >= NOW() - INTERVAL 1 YEAR THEN 1 ELSE 0 END) AS qtd_1_ano
                FROM portal.negociacao_cockpit GROUP BY telefone
            )
            SELECT nc.id, nc.nome nome_cockpit, nc.veiculo, nc.ano, nc.marca, nc.consultando, nc.locked_at,
                   nc.valor, nc.tipo_lead, nc.enviado, nc.data_chegada, nc.data_insercao, nc.telefone, nc.email,
                   nc.canal, nc.propostas_enviadas_minha_loja, nc.propostas_enviadas_outras_lojas, nc.buscas_portal_wm,
                   ipc.cpf, ipc.nome nome_panorama, nc.genero, nc.estado, ipc.data_nascimento, ipc.semelhanca semelhanca_nomes,
                   nc.abriu_regua, nc.valor_fipe, nc.fipe, NOW() as data_hora_enviado, nc.ofertas_json,
                   COALESCE(ht.qtd_3_meses, 0) AS qtd_3_meses, COALESCE(ht.qtd_1_ano, 0) AS qtd_1_ano,
                   COALESCE(ht.qtd_total_historico, 0) AS qtd_total_historico, nc.classificacao_ticket, nc.tipo_veiculo
            FROM portal.negociacao_cockpit AS nc
            JOIN portal.info_panorama_cockpit AS ipc ON nc.id = ipc.negociacao_id
            LEFT JOIN historico_telefones AS ht ON nc.telefone = ht.telefone
            WHERE nc.data_chegada >= NOW() - INTERVAL 15 DAY
        """
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df = pd.read_sql(query, conn)
        return df.sample(frac=1, random_state=42).reset_index(drop=True) if not df.empty else pd.DataFrame()

    def desclassificar(self, row):
        try:
            if pd.isna(row['telefone']) or row['qtd_3_meses'] > 10: return True
            propostas = row['propostas_enviadas_minha_loja'] if not pd.isna(row['propostas_enviadas_minha_loja']) else 0
            return propostas > 5
        except Exception:
            return True 

    def is_lead_acionavel(self, row):
        try:
            if pd.notna(row.get('enviado')): return False
            return str(row.get('abriu_regua')).strip().upper() in ['SIM', 'NAO TESTADO', 'ERRO MODELO']
        except Exception:
            return False

    def is_prioridade_1(self, row):
        try:
            if any(pd.isna(row[k]) for k in ['telefone', 'cpf', 'data_nascimento', 'ano', 'veiculo', 'marca']): return False
            estado = str(row['estado']).upper()
            if estado in ['ND', 'NAN'] or pd.isna(row['estado']): return False
            if pd.isna(row['semelhanca_nomes']) or row['semelhanca_nomes'] < 100: return False
            canal = str(row['canal']).lower()
            if 'seguro' in canal or 'quitados' in canal: return False
            if pd.isna(row['valor']) or row['valor'] <= 0: return False
            return str(row['tipo_veiculo']).upper() in ['MOTO', 'CARRO']
        except Exception:
            return False

    def calcular_idade(self, data_nascimento):
        try:
            if pd.isna(data_nascimento): return None
            hoje, nascimento = pd.Timestamp.now(), pd.to_datetime(data_nascimento)
            idade = hoje.year - nascimento.year
            if (hoje.month, hoje.day) < (nascimento.month, nascimento.day): idade -= 1
            return idade if 18 <= idade <= 99 else None
        except Exception:
            return None

    def is_lead_valido(self, row):
        if pd.notna(row['enviado']): return False
        return str(row['classificacao_ticket']).upper() in ['BAIXO', 'MÉDIO'] and str(row['abriu_regua']).upper() in ['SIM', 'NAO TESTADO']

    def definir_prioridade(self, row):
        if row['desclassificado']: return 10
        abriu = str(row['abriu_regua']).upper()
        dois_dia_util = self.chegou_menos_2_dia_util(row)
        ticket = str(row['classificacao_ticket']).upper()
        genero = str(row['genero']).strip().upper()
        tipo_veiculo = str(row['tipo_veiculo']).strip().upper()

        if self.is_lead_valido(row) and dois_dia_util and row['qtd_3_meses'] == 2: return 3
        if genero == 'M' and tipo_veiculo == 'MOTO' and dois_dia_util: return 5
        if tipo_veiculo == 'MOTO' and dois_dia_util and self.is_lead_valido(row): return 7
        if self.is_prioridade_1(row) and self.is_lead_valido(row) and dois_dia_util and abriu != 'ERRO MODELO': return 1
        if abriu == 'ERRO MODELO' and dois_dia_util and ticket in ['BAIXO', 'MÉDIO'] and row['semelhanca_nomes'] == 100: return 4
        if self.is_lead_valido(row) and dois_dia_util: return 2
        if dois_dia_util and pd.notna(row['veiculo']) and pd.notna(row['data_insercao']) and (pd.Timestamp.now() - pd.to_datetime(row['data_insercao'])).total_seconds() >= 10800 and abriu != 'NAO': return 6
        return 10

    def definir_tipo_lead_teste(self, row):
        if pd.notna(row.get('enviado')): return row.get('tipo_lead')
        if row['desclassificado']: return 'DESCARTE'
        abriu = str(row['abriu_regua']).strip().upper()
        dois_dia_util = self.chegou_menos_2_dia_util(row)
        
        if row['prioridade'] in [1, 2, 3, 4, 5] and self.is_lead_acionavel(row) and dois_dia_util:
            return 'SQL' if abriu == 'SIM' else 'MQL' if abriu in ['NAO TESTADO', 'ERRO MODELO'] else 'DESCARTE'
        return 'RECUPERACAO' if row['prioridade'] == 6 else 'DESCARTE'

    def definir_tipo_lead(self, row):
        if pd.notna(row.get('enviado')): return row.get('tipo_lead')
        if row['desclassificado']: return 'DESCARTE'
        abriu = str(row['abriu_regua']).upper()
        dois_dia_util = self.chegou_menos_2_dia_util(row)

        if row['prioridade'] == 4 and abriu == 'ERRO MODELO': return 'MQL'
        if row['prioridade'] in [1, 2, 3, 4, 5] and self.is_lead_valido(row) and dois_dia_util:
            return 'SQL' if abriu == 'SIM' else 'MQL' if abriu == 'NAO TESTADO' else 'DESCARTE'
        return 'RECUPERACAO' if row['prioridade'] in [6, 7] else 'DESCARTE'

    def arrived_menos_2_dia_util(self, row):
        return self.chegou_menos_2_dia_util(row)

    def chegou_menos_2_dia_util(self, row):
        if pd.isna(row['data_chegada']): return False
        return np.busday_count(np.datetime64(row['data_chegada']).astype('datetime64[D]'), np.datetime64('now').astype('datetime64[D]')) <= 2

    def definir_prioridade_ticket(self, row):
        if row['desclassificado']: return 10
        dois_dia_util = self.chegou_menos_2_dia_util(row)
        try: valor = float(row['valor']) if pd.notna(row['valor']) else None
        except Exception: valor = None

        if self.is_lead_acionavel(row) and dois_dia_util and valor is not None:
            if 10000 <= valor <= 40000: return 1
            if 40000 < valor <= 80000: return 2

        if dois_dia_util and pd.notna(row['veiculo']) and pd.notna(row['data_insercao']) and (pd.Timestamp.now() - pd.to_datetime(row['data_insercao'])).total_seconds() >= 10800 and str(row['abriu_regua']).strip().upper() != 'NAO':
            return 6
        return 10

    def definir_prioridade_nova(self, row):
        if row['desclassificado']: return 10
        dois_dia_util = self.chegou_menos_2_dia_util(row)
        canal = str(row.get('canal')).upper().strip() if pd.notna(row.get('canal')) else ''
        
        try: valor = float(row['valor'])
        except (ValueError, TypeError): valor = None
        
        try: ano = int(str(row['ano'])[:4])
        except (ValueError, TypeError): ano = None

        ano_atual = pd.Timestamp.today().year
        valido = self.is_lead_valido(row) and valor is not None and 10000 <= valor <= 40000 and ano is not None and (ano_atual - 8) <= ano <= ano_atual
        
        if dois_dia_util and valido and 'APROVADO' in canal: return 1
        if dois_dia_util and valido and 'C2C' in canal: return 2
        return 3 if dois_dia_util else 10

    def definir_prioridade_publico_veiculo(self, row):
        if row['desclassificado']: return 10
        dois_dia_util = self.chegou_menos_2_dia_util(row)
        genero = str(row['genero']).strip().upper()
        tipo_veiculo = str(row['tipo_veiculo']).strip().upper()

        if self.is_lead_acionavel(row) and dois_dia_util:
            if genero == 'M' and tipo_veiculo == 'MOTO': return 1
            if genero == 'F' and tipo_veiculo == 'MOTO': return 2
            if genero == 'M' and tipo_veiculo == 'CARRO': return 3
            if genero == 'F' and tipo_veiculo == 'CARRO': return 4
            if row['qtd_3_meses'] == 2: return 5

        if dois_dia_util and pd.notna(row['veiculo']) and pd.notna(row['data_insercao']) and (pd.Timestamp.now() - pd.to_datetime(row['data_insercao'])).total_seconds() >= 10800 and str(row['abriu_regua']).strip().upper() != 'NAO':
            return 6
        return 10

    def executar_classificacao(self):
        df = self.gerar_dados()
        if df is None or df.empty: return df
        
        df['desclassificado'] = df.apply(self.desclassificar, axis=1)
        df['prioridade'] = df.apply(self.definir_prioridade_nova, axis=1)
        df['tipo_lead'] = df.apply(self.definir_tipo_lead_teste, axis=1)
        df['elegivel'] = df.apply(lambda r: str(r['abriu_regua']).upper() in ['SIM', 'NAO TESTADO', 'ERRO MODELO'] and str(r['classificacao_ticket']).upper() in ['BAIXO', 'MÉDIO'], axis=1)
        
        print(f"Total: {len(df)} | Desclassificados: {df['desclassificado'].sum()} | Elegíveis: {df['elegivel'].sum()}")
        for i in range(1, 8): print(f"Prioridade {i}: {(df['prioridade'] == i).sum()}")
        print(f"Prioridade 10: {(df['prioridade'] == 10).sum()}")
        
        self.atualizar_banco(df)
        return df

    def atualizar_banco(self, df):
        query = "UPDATE portal.negociacao_cockpit SET prioridade = %s, tipo_lead = %s, data_classificacao = NOW(), primeira_prioridade = COALESCE(primeira_prioridade, %s) WHERE id = %s"
        with utils_core.Database('APP_DB_PORTAL') as conn:
            df['primeira_prioridade'] = df['prioridade']
            dados = [tuple(None if pd.isna(x) else x for x in r) for r in df[['prioridade', 'tipo_lead', 'primeira_prioridade', 'id']].itertuples(index=False, name=None)]
            cursor = conn.cursor()
            cursor.executemany(query, dados)
            conn.commit()