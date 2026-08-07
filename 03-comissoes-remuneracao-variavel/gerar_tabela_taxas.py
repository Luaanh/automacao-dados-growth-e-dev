import datetime
import pandas as pd
import customtkinter as ctk

import utils_core
import Application

COLUNAS_COMPARACAO = [
    "codigo_regra",
    "descricao_regra",
    "faixa_parcela",
    "taxa_juros_sem_seguro",
    "taxa_juros_com_seguro",
    "percentual_comissao_a_vista"
]

def carregar_banco_teste(conn):
    sql = """
        SELECT 
            id,
            codigo AS codigo_regra,
            descricao_banco AS descricao_regra,
            prazo,
            taxa_total AS taxa_juros_sem_seguro,
            taxa_vista AS taxa_juros_com_seguro,
            comissao_total AS percentual_comissao_a_vista
        FROM tabela_taxas
        WHERE data_fim IS NULL
        AND banco = 'banco_teste'
    """
    df = pd.read_sql(sql, conn)
    
    if not df.empty:
        df["prazo"] = df["prazo"].astype(str).str.replace(r'^0+', '', regex=True)
        df["faixa_parcela"] = df["prazo"]
    else:
        df["faixa_parcela"] = []

    return df

def criar_comparacao(df):
    if df.empty:
        df["comparacao"] = ""
        df["chave"] = ""
        return df

    df["comparacao"] = (
        df["codigo_regra"].astype(str)
        + df["descricao_regra"].astype(str)
        + df["faixa_parcela"].astype(str)
        + df["taxa_juros_sem_seguro"].astype(str)
        + df["taxa_juros_com_seguro"].astype(str)
        + df["percentual_comissao_a_vista"].astype(str)
    )

    df["chave"] = (
        df["codigo_regra"].astype(str)
        + df["faixa_parcela"].astype(str)
    )

    return df

def compor_codigo_unico(row):
    partes = [
        str(row.get("codigo_regra", "")).strip(),
        str(row.get("range_faixa", "")).strip(),
        str(row.get("faixa_parcela", "")).strip()
    ]
    partes_validas = [p for p in partes if p and p.lower() != 'nan']
    return "-".join(partes_validas)

def processar_tabela(df_novo):
    renames_iniciais = {}
    if "inicio_regra" in df_novo.columns:
        renames_iniciais["inicio_regra"] = "codigo_regra"
    elif "regra" in df_novo.columns and "codigo_regra" not in df_novo.columns:
        renames_iniciais["regra"] = "codigo_regra"
        
    if "percentual_comissao_a_vista_atual" in df_novo.columns:
        renames_iniciais["percentual_comissao_a_vista_atual"] = "percentual_comissao_a_vista"
        
    if renames_iniciais:
        df_novo = df_novo.rename(columns=renames_iniciais)
        
    df_novo["codigo_regra"] = df_novo.apply(compor_codigo_unico, axis=1)
    
    with utils_core.Database("APP_DB") as conn:
        df_antigo = carregar_banco_teste(conn)
        
        df_novo = criar_comparacao(df_novo)
        df_antigo = criar_comparacao(df_antigo)
        
        if not df_antigo.empty:
            novas = df_novo[~df_novo["chave"].isin(df_antigo["chave"])]
            
            merge = df_novo.merge(
                df_antigo,
                on="chave",
                how="inner",
                suffixes=("_novo", "_antigo")
            )

            alteradas = merge[merge["comparacao_novo"] != merge["comparacao_antigo"]]
            ids_desativar = alteradas["id"].tolist()
            
            removidas = df_antigo[~df_antigo["chave"].isin(df_novo["chave"])]
            ids_desativar.extend(removidas["id"].tolist())
            
            if ids_desativar:
                sql_update = f"""
                    UPDATE tabela_taxas
                    SET data_fim = %s
                    WHERE id IN ({",".join(["%s"] * len(ids_desativar))})
                """
                cur = conn.cursor()
                cur.execute(sql_update, [datetime.date.today() - datetime.timedelta(days=1), *ids_desativar])
                conn.commit()
                cur.close()
                
            if not alteradas.empty:
                alteradas_limpo = alteradas.filter(regex="_novo").rename(columns=lambda x: x.replace("_novo", ""))
                inserir = pd.concat([novas, alteradas_limpo])
            else:
                inserir = novas.copy()
                
        else:
            inserir = df_novo.copy()

        if not inserir.empty:
            inserir["data_inicio"] = datetime.date.today()
            inserir["banco"] = "SANTANDER"
            inserir["perc_parceiro"] = 0.8000
            inserir["comissao_total"] = inserir["percentual_comissao_a_vista"]
            inserir["comissao_vista"] = inserir["percentual_comissao_a_vista"]

            cond = inserir["percentual_comissao_a_vista"] < 0.5
            inserir.loc[~cond, "comissao_total"] = inserir["percentual_comissao_a_vista"] * 0.80
            inserir.loc[~cond, "comissao_vista"] = inserir["percentual_comissao_a_vista"] * 0.80
            
            colunas_map = {
                "codigo_regra": "codigo",
                "descricao_regra": "descricao_banco",
                "nome_convenio": "convenio", 
                "forma_contrato": "forma_contrato", 
                "produto_regra": "forma_contrato",
                "faixa_parcela": "prazo",
                "taxa_juros_sem_seguro": "taxa_total",
                "taxa_juros_com_seguro": "taxa_vista"
            }
            
            inserir = inserir.rename(columns=colunas_map)
            
            if "convenio" in inserir.columns and "descricao_banco" in inserir.columns:
                inserir['convenio'] = (
                    inserir['convenio'].astype(str) + ' - ' +
                    inserir['descricao_banco'].astype(str)
                )
                
            for col in ["descricao_banco", "convenio", "forma_contrato"]:
                if col not in inserir.columns: 
                    inserir[col] = None
                    
            colunas_db = [
                "codigo", "descricao_banco", "convenio", "forma_contrato",
                "taxa_total", "taxa_vista", "prazo",
                "comissao_total", "comissao_vista", 
                "banco", "data_inicio"
            ]
            
            inserir_final = inserir[colunas_db].where(pd.notnull(inserir), None)

            cursor = conn.cursor()
            sql_insert = """
                INSERT INTO tabela_taxas (
                    codigo, descricao_banco, convenio, forma_contrato,
                    taxa_total, taxa_vista, prazo, 
                    comissao_total, comissao_vista,
                    banco, data_inicio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(sql_insert, inserir_final.values.tolist())
            conn.commit()
            cursor.close()

def main():
    filename = ctk.filedialog.askopenfilename(title="Abra um arquivo excel/csv", filetype=(("CSV/XLSX", "*.*"),))
    if not filename:
        return
        
    try:
        df, ext = Application.FileHandler.load_file(filename, "Condições_comerciais")
    except Exception as e:
        print(f"Erro ao carregar o arquivo: {e}")
        return
        
    df["faixa_parcela"] = df["faixa_parcela"].astype(str)
    processar_tabela(df)

if __name__ == "__main__":
    main()