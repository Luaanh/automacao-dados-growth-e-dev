import os
import re
import time
import shutil
import random
import hashlib
import sqlite3
import datetime
import functools
import collections
import unicodedata
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
from thefuzz import fuzz
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import undetected_chromedriver as uc

DDD_ESTADO = {
    11: "SP", 12: "SP", 13: "SP", 14: "SP", 15: "SP", 16: "SP", 17: "SP", 18: "SP", 19: "SP",
    21: "RJ", 22: "RJ", 24: "RJ", 27: "ES", 28: "ES",
    31: "MG", 32: "MG", 33: "MG", 34: "MG", 35: "MG", 37: "MG", 38: "MG",
    41: "PR", 42: "PR", 43: "PR", 44: "PR", 45: "PR", 46: "PR",
    47: "SC", 48: "SC", 49: "SC", 51: "RS", 53: "RS", 54: "RS", 55: "RS",
    61: "DF", 62: "GO", 64: "GO", 63: "TO", 65: "MT", 66: "MT", 67: "MS",
    68: "AC", 69: "RO", 71: "BA", 73: "BA", 74: "BA", 75: "BA", 77: "BA", 79: "SE",
    81: "PE", 87: "PE", 82: "AL", 83: "PB", 84: "RN", 85: "CE", 88: "CE",
    86: "PI", 89: "PI", 91: "PA", 93: "PA", 94: "PA", 92: "AM", 97: "AM",
    95: "RR", 96: "AP", 98: "MA", 99: "MA"
}

def _extrair_digitos(valor: str) -> str:
    if pd.isna(valor) or valor is None:
        return ""
    return re.sub(r'\D', '', str(valor))

def _configurar_opcoes_chrome(diretorio_user, window_size, diretorio_download, is_uc=False):
    options = uc.ChromeOptions() if is_uc else webdriver.ChromeOptions()
    options.add_argument("--enable-javascript")
    options.add_argument("--force-device-scale-factor=0.5")
    options.add_argument(f"--window-size={window_size}")
    options.add_argument("--disable-popup-blocking")
    
    if diretorio_download:
        prefs = {
            "download.default_directory": os.path.abspath(diretorio_download),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
    os.makedirs(diretorio_user, exist_ok=True)
    options.add_argument(f"--user-data-dir={os.path.abspath(diretorio_user)}")
    return options


class Automacoes:
    @staticmethod
    def abrir_driver(diretorio_user: str, diretorio_download=False, window_size='1280,800', navegador_brave=True):
        options = _configurar_opcoes_chrome(diretorio_user, window_size, diretorio_download)
        options.add_argument("--profile-directory=Default")
        
        if navegador_brave:
            options.binary_location = os.path.join(
                os.environ['USERPROFILE'], 
                'AppData', 'Local', 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'
            )
        return webdriver.Chrome(options=options)

    @staticmethod
    def abrir_driver_cockpit(diretorio_user: str, diretorio_download=False, window_size='1280,800'):
        user_data_root = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
        source_profile_path = os.path.join(user_data_root, 'Profile 1')
        if not os.path.exists(source_profile_path):
            source_profile_path = os.path.join(user_data_root, 'Default')
            
        automation_dir = os.path.abspath(diretorio_user)
        destination_profile_path = os.path.join(automation_dir, 'Default')
        
        if not os.path.exists(destination_profile_path):
            shutil.copytree(source_profile_path, destination_profile_path)

        options = _configurar_opcoes_chrome(automation_dir, window_size, diretorio_download)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return webdriver.Chrome(options=options)

    @staticmethod
    def abrir_driver_uc(diretorio_user: str, chrome_driver_path=False, diretorio_download=False, window_size='1280,800'):
        options = _configurar_opcoes_chrome(diretorio_user, window_size, diretorio_download, is_uc=True)
        options.add_argument("--profile-directory=Default")
        
        if chrome_driver_path:
            return uc.Chrome(options=options, driver_executable_path=chrome_driver_path)
        return uc.Chrome(options=options)

    @staticmethod
    def salvar_screenshot(driver: webdriver.Chrome, nome_arquivo: str, automacao: str, pasta=r'C:\mock_network_share\InteligenciaComercial\Margem - Evidências'):
        data_hoje = datetime.datetime.today().strftime('%d-%m-%Y')
        pasta_automacao = os.path.join(pasta, automacao)
        os.makedirs(pasta_automacao, exist_ok=True)
        
        caminho_pasta = next((os.path.join(pasta_automacao, p) for p in os.listdir(pasta_automacao) 
                              if os.path.isdir(os.path.join(pasta_automacao, p)) and data_hoje in p), None)
        
        if not caminho_pasta:
            numero_alvo = sum(1 for p in os.listdir(pasta_automacao) if os.path.isdir(os.path.join(pasta_automacao, p))) + 1
            caminho_pasta = os.path.join(pasta_automacao, f"{numero_alvo} - {data_hoje}")
            os.makedirs(caminho_pasta)

        tempo_screenshot = datetime.datetime.now().strftime('%d_%m_%Y - %H_%M_%S')
        driver.save_screenshot(os.path.join(caminho_pasta, f"{nome_arquivo}_{tempo_screenshot}.png"))

    @staticmethod
    def executar_com_limite(hora_inicio, hora_fim):
        class TempoUtil:
            def __init__(self, start, end):
                self.hora_inicio = start
                self.hora_fim = end

            def pode_continuar(self):
                now = datetime.datetime.now()
                return self.hora_inicio <= now.hour < self.hora_fim and now.weekday() < 5

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(TempoUtil(hora_inicio, hora_fim), *args, **kwargs)
            return wrapper
        return decorator


class Whatsapp:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def gerar_limite(self, telefone_envio: str) -> int:
        db_limite = "limites.db"
        with sqlite3.connect(db_limite) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS limites (telefone TEXT PRIMARY KEY, historico TEXT)")
            cursor.execute("SELECT historico FROM limites WHERE telefone = ?", (telefone_envio,))
            row = cursor.fetchone()

            if row:
                historico = list(map(int, row[0].split(",")))
                novo_limite = max(10, historico[-1] + random.randint(-5, 10))
                historico.append(novo_limite)
                novo_historico = ",".join(map(str, historico[-10:]))
                cursor.execute("UPDATE limites SET historico = ? WHERE telefone = ?", (novo_historico, telefone_envio))
            else:
                novo_limite = random.randint(5, 15)
                cursor.execute("INSERT INTO limites (telefone, historico) VALUES (?, ?)", (telefone_envio, str(novo_limite)))
            conn.commit()
        return novo_limite


class Database:
    def __init__(self, variavel_env: str):
        load_dotenv()
        creds = os.getenv(variavel_env).split(',')
        self.connection = mysql.connector.connect(
            host=creds[0], user=creds[1], password=creds[2], database=creds[3]
        )

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection.is_connected():
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
            self.connection.close()

    def cursor(self):
        return self.connection.cursor()

    def close(self):
        if self.connection.is_connected():
            self.connection.close()

    def execute_calls(self, calls):
        try:
            cursor = self.cursor()
            for call in calls:
                cursor.execute(call)
            self.connection.commit()
            cursor.close()
        except mysql.connector.Error as err:
            print(err)


class Geral:
    @staticmethod
    def retornar_valor_env(env_var):
        load_dotenv()
        return os.getenv(env_var)

    @staticmethod
    def gerador_pausa_curta():
        return random.randint(50, 100) if datetime.datetime.now().minute % 10 == 0 else random.randint(3, 9)

    @staticmethod
    def check_if_exists(driver: webdriver.Chrome, xpath: str):
        try:
            driver.find_element(By.XPATH, xpath)
            return True
        except NoSuchElementException:
            return False

    @staticmethod
    def padronizar_telefone(telefone):
        numeros = _extrair_digitos(telefone)
        if not numeros: return None
        if numeros.startswith('55'):
            return numeros if len(numeros) in [12, 13] else None
        return '55' + numeros if len(numeros) in [10, 11] else None

    @staticmethod
    def criar_faixas(coluna, step=None, bins_manual=None, labels_manual=None):
        if bins_manual is not None:
            return pd.cut(coluna, bins=bins_manual, labels=labels_manual)
        if step:
            max_val = int(coluna.max())
            bins = range(0, max_val + step + 1, step)
            labels = [f"{i}-{i+step}" for i in range(0, max_val + 1, step)]
            return pd.cut(coluna, bins=bins, labels=labels, right=False)
        return coluna

    @staticmethod
    def inferir_estado_por_telefone(telefone):
        numeros = _extrair_digitos(telefone)
        if numeros.startswith('55') and len(numeros) > 11:
            numeros = numeros[2:]
        if len(numeros) < 10: return None
        try:
            return DDD_ESTADO.get(int(numeros[:2]))
        except ValueError:
            return None

    @staticmethod
    def formatar_cpf(cpf: int | str) -> str | None:
        if cpf is None or pd.isna(cpf) or cpf == 'None': return None
        cpf_str = _extrair_digitos(cpf).zfill(11)
        if len(cpf_str) > 11: cpf_str = cpf_str[:11]
        return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"

    @staticmethod
    def desformatar_cpf(cpf: int | str) -> str | None:
        numeros = _extrair_digitos(cpf)
        return numeros if len(numeros) == 11 else None

    @staticmethod
    def normalizar_numero(numero):
        digitos = _extrair_digitos(numero)
        return digitos[-11:] if len(digitos) >= 11 else None

    @staticmethod
    def merge_em_lote(df_base: pd.DataFrame, dfs: list[pd.DataFrame], how_pos: str, left_on: str, right_on: str):
        for i, df in enumerate(dfs):
            right_temp_col = f"{right_on}_tmp_{i}"
            df_temp = df.rename(columns={right_on: right_temp_col})
            df_base = df_base.merge(df_temp, left_on=left_on, right_on=right_temp_col, how=how_pos)
            if right_temp_col in df_base.columns:
                df_base = df_base.drop(columns=[right_temp_col])
        return df_base

    @staticmethod
    def tempo_parado(tempo: int, automacao: str):
        for segundos_restantes in range(tempo, 0, -1):
            horas, rem = divmod(segundos_restantes, 3600)
            minutos, segundos = divmod(rem, 60)
            print(f"{automacao}: Faltam {horas:02}:{minutos:02}:{segundos:02}", end='\r')
            time.sleep(1)

    @staticmethod
    def normalize_table_name(table_name):
        normalized = ''.join(c for c in unicodedata.normalize('NFKD', table_name.lower()) if not unicodedata.combining(c))
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        normalized = re.sub(r'[\s-]+', '_', normalized)
        return re.sub(r'_+', '_', normalized).strip('_')

    @staticmethod
    def handle_duplicate_column_names(df):
        normalized_cols = [Geral.normalize_table_name(col) for col in df.columns]
        counts = collections.Counter(normalized_cols)
        seen = collections.defaultdict(int)
        new_cols = []
        
        for col in normalized_cols:
            if counts[col] > 1:
                if seen[col] == 0:
                    new_cols.append(col)
                else:
                    new_cols.append(f"{col}_{seen[col]}")
                seen[col] += 1
            else:
                new_cols.append(col)
        df.columns = new_cols
        return df

    @staticmethod
    def _garantir_coluna(cur, tabela, coluna, definicao):
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s LIMIT 1
        """, (tabela, coluna))
        if not cur.fetchone():
            cur.execute(f"ALTER TABLE `{tabela}` ADD COLUMN `{coluna}` {definicao}")

    @staticmethod
    def create_table_and_add_columns(df, table_name, env_var):
        with Database(env_var) as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')")
            if not cur.fetchone()[0]:
                cols_def = [
                    'ID INT PRIMARY KEY AUTO_INCREMENT',
                    'data_insercao DATETIME DEFAULT CURRENT_TIMESTAMP',
                    'row_hash CHAR(64) NOT NULL UNIQUE',
                    'execution_date DATE',
                    'verificacao_hash DATETIME'
                ]
                cols_def += [f"{Geral.normalize_table_name(c)} VARCHAR(255)" for c in df.columns]
                cur.execute(f"CREATE TABLE {table_name} (\n" + ",\n".join(cols_def) + "\n);")
            else:
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
                existing_cols = {col[0] for col in cur.fetchall()}
                for col in df.columns:
                    norm_col = Geral.normalize_table_name(col)
                    if norm_col not in existing_cols:
                        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {norm_col} VARCHAR(255);")
            conn.commit()

    @staticmethod
    def inserir_db(df: pd.DataFrame, tabela: str, env_var: str, conn=None):
        df = df[[c for c in df.columns if c and str(c).strip().lower() not in ['nan', 'none', '']]].copy()
        df = Geral.handle_duplicate_column_names(df)
        Geral.create_table_and_add_columns(df, tabela, env_var)
        
        df.columns = [Geral.normalize_table_name(c) for c in df.columns]
        df = df.where(pd.notnull(df), None).astype(str).replace({'nan': None, 'NaT': None, 'None': None})
        
        df["row_hash"] = df.apply(Geral.calculate_row_hash, axis=1)
        df["execution_date"] = datetime.date.today()
        
        tuplas = list(df.itertuples(index=False, name=None))
        col_names = ','.join(f'`{c}`' for c in df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        query = f"INSERT INTO {tabela} ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE verificacao_hash = NOW()"

        def _executar(db_conn):
            c = db_conn.cursor()
            Geral._garantir_coluna(c, tabela, 'execution_date', 'DATE')
            Geral._garantir_coluna(c, tabela, 'verificacao_hash', 'DATETIME')
            c.executemany(query, tuplas)
            db_conn.commit()
            c.close()

        if conn:
            _executar(conn)
        else:
            with Database(env_var) as db_conn:
                _executar(db_conn)

    @staticmethod
    def transforma_em_decimal(numero):
        if not numero: return Decimal('0.0')
        try:
            return Decimal(str(numero).replace('.', '').replace(',', '.').replace("R$", "").replace('RS', '').strip())
        except (InvalidOperation, ValueError):
            return Decimal('0.0')

    @staticmethod
    def calculate_row_hash(row: pd.Series) -> str:
        parts = []
        for col in sorted(row.index):
            val = row[col]
            if pd.notna(val) and val is not None:
                parts.append(f"{Decimal(val):.4f}" if isinstance(val, (int, float, Decimal)) else str(val))
            else:
                parts.append('')
        return hashlib.sha256(''.join(parts).encode('utf-8')).hexdigest()

    @staticmethod
    def normalizar_texto(texto: str) -> str:
        t = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8').lower()
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()

    @staticmethod
    def converter_texto_data(data_str):
        try:
            return datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def limpar_nome_brasileiro(nome):
        if pd.isna(nome) or not str(nome).strip(): return ""
        n = ''.join(c for c in unicodedata.normalize('NFD', str(nome).lower().strip()) if unicodedata.category(c) != 'Mn')
        n = re.sub(r'[^a-z0-9\s]', '', n)
        n = re.sub(r'\b(de|da|do|das|dos|e)\b', '', n)
        return re.sub(r'\s+', ' ', n).strip()

    @staticmethod
    def calcular_semelhanca_nomes(df: pd.DataFrame, coluna_nome1='nome', coluna_nome2='nome_cliente_panorama') -> pd.DataFrame:
        df_res = df.copy()
        n1_list = df_res[coluna_nome1].apply(Geral.limpar_nome_brasileiro)
        n2_list = df_res[coluna_nome2].apply(Geral.limpar_nome_brasileiro)
        df_res['semelhanca'] = [fuzz.token_set_ratio(n1, n2) if n1 and n2 else 0 for n1, n2 in zip(n1_list, n2_list)]
        return df_res


class QueryBuilder:
    def __init__(self):
        self.conditions = []
        self.params = []

    def add_literal_condition(self, literal_condition: str):
        if literal_condition:
            self.conditions.append(literal_condition)

    def add_condition(self, condition: str, value):
        if value is not None:
            self.conditions.append(condition)
            self.params.append(value)

    def add_in_clause(self, column: str, values: list):
        if values:
            self.conditions.append(f"{column} IN ({', '.join(['%s'] * len(values))})")
            self.params.extend(values)
            
    def build(self) -> tuple[str, list]:
        if not self.conditions: return "", []
        return "WHERE " + " AND ".join(self.conditions), self.params


class GerarRelatorios:
    def __init__(self, dict_df: dict[str, pd.DataFrame], pasta: str, nome_arquivo: str | bool = False):
        self.pasta = pasta
        self.dict_df = dict_df
        self.nome_arquivo = nome_arquivo or ''

    def gerar_relatorios(self):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_final = f"{self.nome_arquivo}_relatorio_COMPLETO_{timestamp}.xlsx" if self.nome_arquivo == '' else f"{self.nome_arquivo}.xlsx"
        path = os.path.join(self.pasta, nome_final)
            
        with pd.ExcelWriter(path, engine='xlsxwriter', datetime_format='dd/mm/yyyy') as writer:
            for nome, df in self.dict_df.items():
                for c in df.columns:
                    if 'data' in str(c).lower():
                        df[c] = pd.to_datetime(df[c], errors='coerce')
                
                df.to_excel(writer, index=False, sheet_name=nome)
                worksheet = writer.sheets[nome]
                header_format = writer.book.add_format({
                    'bold': True, 'valign': 'center', 'align': 'center', 'fg_color': '#FF0000', 'font_color': '#FFFFFF'
                })

                for col_num, value in enumerate(df.columns):
                    worksheet.write(0, col_num, value, header_format)
                    max_len = max(df[value].astype(str).map(len).max() if not df.empty else 0, len(str(value))) + 2
                    worksheet.set_column(col_num, col_num, max_len)
                
                worksheet.autofilter(0, 0, df.shape[0], df.shape[1] - 1)


class LoadArquivoDB:
    def __init__(self, extensoes: tuple[str], partes_nome: list[str], pasta: str, tabela: str, env_var: str, preprocess_func=None, apagar_arquivos=False, conn=False):
        self.extensoes = extensoes
        self.partes_nome = [p.lower() for p in partes_nome]
        self.pasta = pasta
        self.tabela = tabela
        self.env_var = env_var
        self.preprocess_func = preprocess_func
        self.apagar_arquivos = apagar_arquivos
        self.conn = conn
        self.arquivos_encontrados = []

    def procurar_arquivos(self):
        self.arquivos_encontrados = [
            os.path.join(self.pasta, a) for a in os.listdir(self.pasta)
            if a.lower().endswith(self.extensoes) and (not self.partes_nome or any(p in a.lower() for p in self.partes_nome))
        ]

    def load_db(self, sheet_name: str = None):
        import Application
        self.procurar_arquivos()

        for caminho in self.arquivos_encontrados:
            df, _ = Application.FileHandler().load_file(caminho, sheet_name)
            if self.preprocess_func and not df.empty:
                df = self.preprocess_func(df)

            if not df.empty:
                Geral.inserir_db(df, self.tabela, self.env_var, conn=self.conn)
            time.sleep(0.5)

        if self.apagar_arquivos:
            self.delete_arquivo()

    def delete_arquivo(self):
        for c in self.arquivos_encontrados:
            os.remove(c)


class ClassificadorGenero:
    def __init__(self):
        self.mapa_genero = {}
        self._carregar_base('data_set_genero.csv')

    def _remover_acentos(self, texto):
        if pd.isna(texto) or not isinstance(texto, str): return ""
        return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').strip().upper()

    def _carregar_base(self, caminho_csv):
        df = pd.read_csv(caminho_csv, sep=',')
        for row in df.itertuples(index=False):
            classificacao = str(row.classification).strip().upper()
            if classificacao not in ['M', 'F']: continue

            nome_principal = self._remover_acentos(row.group_name)
            if nome_principal:
                self.mapa_genero[nome_principal] = classificacao
            
            if pd.notna(row.alternative_names) and isinstance(row.alternative_names, str):
                for variacao in row.alternative_names.split('|'):
                    v_limpa = self._remover_acentos(variacao)
                    if v_limpa: self.mapa_genero[v_limpa] = classificacao

    def inferir_genero(self, nome_completo):
        if pd.isna(nome_completo) or not str(nome_completo).strip(): return None
        return self.mapa_genero.get(self._remover_acentos(str(nome_completo).strip().split()[0]), None)