from flask import Flask, jsonify, request
import pandas as pd
import utils_core
import datetime
import pandas as pd
import re
from flask_cors import CORS
import json
import utils_core 
app = Flask(__name__)
CORS(app, origins=["https://partner-platform.example.com"])
ano_atual = datetime.date.today().year
mapeamento_estados = {
    'AC': 'ACRE', 'AL': 'ALAGOAS', 'AP': 'AMAPA', 'AM': 'AMAZONAS',
    'BA': 'BAHIA', 'CE': 'CEARA', 'DF': 'DISTRITO FEDERAL', 'ES': 'ESPIRITO SANTO',
    'GO': 'GOIAS', 'MA': 'MARANHAO', 'MT': 'MATO GROSSO', 'MS': 'MATO GROSSO DO SUL',
    'MG': 'MINAS GERAIS', 'PA': 'PARA', 'PB': 'PARAIBA', 'PR': 'PARANA',
    'PE': 'PERNAMBUCO', 'PI': 'PIAUI', 'RJ': 'RIO DE JANEIRO', 'RN': 'RIO GRANDE DO NORTE',
    'RS': 'RIO GRANDE DO SUL', 'RO': 'RONDONIA', 'RR': 'RORAIMA', 'SC': 'SANTA CATARINA',
    'SP': 'SAO PAULO', 'SE': 'SERGIPE', 'TO': 'TOCANTINS'
}
def carregar_simulacoes():
    with utils_core.Database('APP_DB_PORTAL') as conn:
        cur = conn.cursor()
        df = pd.read_sql(r"""
            SELECT
                nc.id,
                ipc.cpf,
                ipc.data_nascimento AS nascimento,
                nc.marca,
                nc.ano,
                nc.veiculo AS modelo,
                nc.valor,
                nc.estado,
                CONCAT(
                    UPPER(LEFT(nc.tipo_veiculo, 1)),
                    LOWER(SUBSTRING(nc.tipo_veiculo, 2))
                ) AS tipoVeiculo
            FROM
                portal.negociacao_cockpit AS nc
            JOIN
                portal.info_panorama_cockpit AS ipc ON nc.id = ipc.negociacao_id
            WHERE
                prioridade = 1
                AND (nc.consultando = 0  OR nc.locked_at < NOW() - INTERVAL 5 MINUTE)
                AND nc.enviado IS NULL
                AND nc.telefone IS NOT NULL
                AND ipc.cpf IS NOT NULL
                AND nc.estado IS NOT NULL
                AND nc.estado <> 'ND'
                AND ipc.semelhanca >= 100
                AND ipc.data_nascimento is not null
                AND nc.abriu_regua = 'NAO TESTADO'
                AND nc.canal not like '%seguro%'
                AND LOWER(nc.canal) not like '%quitados%'
                AND nc.ano is not null
                and nc.veiculo is not null
                and nc.marca is not null      
                AND nc.valor is not null
                AND nc.valor > 0
                AND nc.tipo_veiculo IN ('MOTO', 'CARRO')
            ORDER BY nc.data_chegada DESC, RAND()
            LIMIT 1;
""", conn)
        lista_ids = df['id'].to_list()

        params = [(i,) for i in lista_ids]

        cur.executemany(
            'UPDATE negociacao_cockpit SET consultando = 1, locked_at = NOW() WHERE id = %s',
            params
        )
        conn.commit()
        cur.close()
    df['ano'] = df['ano'].str.split('/').str[-1].str.strip().astype(int)
    df['usadoNovo'] = df['ano'].apply(lambda x: '0km/Novo' if x >= (ano_atual - 1) else 'Usado')
    df['estado'] = df['estado'].str.upper().map(mapeamento_estados).fillna(df['estado'])
    df['cpf'] = df['cpf'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(11)
    df['valor'] = df['valor'].fillna(0).astype(int)
    df['modelo'] = df['modelo'].str.replace(r'\s*\d\.\d.*', '', regex=True).str.strip()
    df['nascimento'] = pd.to_datetime(df['nascimento']).dt.strftime('%d/%m/%Y')
    
    colunas_ordenadas = [
        'id', 'cpf', 'nascimento', 'marca', 'ano', 
        'modelo', 'valor', 'estado', 'tipoVeiculo', 'usadoNovo'
    ]
    df = df[colunas_ordenadas]
    
    return df
def carregar_placas():
    with utils_core.Database('APP_DB') as conn:
        cur = conn.cursor()
        df = pd.read_sql(r"""
            SELECT
                cpf, placa
            FROM
                consulta_seguro
            WHERE
                data_placa is null
            LIMIT 1;
""", conn)
        lista_ids = df['placa'].to_list()

        params = [(i,) for i in lista_ids]

        cur.executemany(
            'UPDATE consulta_seguro SET consultando_placa = 1 WHERE placa = %s',
            params
        )
        conn.commit()
        cur.close()
    df['cpf'] = df['cpf'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(11)
    
    return df
def carregar_cotacao():
    with utils_core.Database('APP_DB') as conn:
        cur = conn.cursor()
        df = pd.read_sql(r"""
                SELECT
                contato_id id,
                placa,
                cpf,
                uf_licenciamento estado,
                estado_veiculo usadoNovo,
                marca,
                modelo,
                 CONCAT(
                    UPPER(LEFT(tipo_veiculo, 1)),
                    LOWER(SUBSTRING(tipo_veiculo, 2))
                ) AS tipoVeiculo,
                ano_combustivel,
                preco_medio_veiculo valor,
                CASE 
                    WHEN uso_veiculo = 'PARTICULAR' THEN 'Comum' 
                    WHEN uso_veiculo = 'APLICATIVO' THEN 'Motorista de Aplicativo'
                    WHEN uso_veiculo = 'PCD' THEN 'PCD'
                    WHEN uso_veiculo = 'TAXISTA' THEN 'Taxista'
                END AS uso_veiculo,
                data_nascimento
            FROM
                consulta_seguro
            WHERE
                data_consulta is null
                AND DATE(data_placa) >= CURDATE() - INTERVAL 1 DAY
                AND modelo is not null
                AND placa NOT LIKE 'CPF%'
            ORDER BY data_placa DESC
         ;
""", conn)
        lista_ids = df['placa'].to_list()

        params = [(i,) for i in lista_ids]

        cur.executemany(
            'UPDATE consulta_seguro SET consultando_cotacao = 1 WHERE placa = %s',
            params
        )
        conn.commit()
        cur.close()
    df['cpf'] = df['cpf'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(11)
    df['estado'] = df['estado'].str.upper().map(mapeamento_estados).fillna(df['estado'])
    df['valor'] = df['valor'].fillna(0).astype(int)
    df['data_nascimento'] = pd.to_datetime(
        df['data_nascimento'],
        errors='coerce'
    )

    df['data_nascimento'] = df['data_nascimento'].dt.strftime('%d/%m/%Y')

    df['data_nascimento'] = df['data_nascimento'].where(
        df['data_nascimento'].notna(), None
    )

    colunas_ordenadas = [
        'id', 'cpf', 'marca', 'ano_combustivel', 
        'modelo', 'valor', 'estado', 'tipoVeiculo', 'usadoNovo',
        'uso_veiculo','data_nascimento'
    ]
    return df[colunas_ordenadas]

@app.route("/simulacoes", methods=["GET"])
def get_simulacoes():
    df = carregar_simulacoes()
    lista = df.to_dict(orient="records")
    return jsonify(lista)
@app.route("/placas", methods=["GET"])
def get_placas():
    df = carregar_placas()
    lista = df.to_dict(orient="records")
    return jsonify(lista)
@app.route("/cotacao", methods=["GET"])
def get_cotacao():
    df = carregar_cotacao()
    lista = df.to_dict(orient="records")
    return jsonify(lista)
if __name__ == "__main__":
    app.run(debug=True, port=5000)