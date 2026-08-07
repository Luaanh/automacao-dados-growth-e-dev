import os
import json
from pathlib import Path
import pandas as pd
import utils_core

PASTA_DOWNLOADS = Path(os.environ.get('USERPROFILE', '')) / 'Downloads'
ENV_VAR = 'APP_DB'

class Consignado:
    def banco_brasil(self):
        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["producaomensalbd"],
            pasta=str(PASTA_DOWNLOADS),
            tabela="contratos_bb",
            env_var=ENV_VAR,
            apagar_arquivos=True
        ).load_db()
        
        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["_todos_"],
            pasta=str(PASTA_DOWNLOADS),
            tabela="comissao_bb",
            env_var=ENV_VAR,
            apagar_arquivos=True
        ).load_db(sheet_name="A Vista")

    def contratos_nova(self):
        with utils_core.Database(ENV_VAR) as conn:
            utils_core.LoadArquivoDB(
                extensoes=(".csv",),
                partes_nome=["contratos_digitados_de_"],
                pasta=str(PASTA_DOWNLOADS),
                tabela="contratos_nova",
                env_var=ENV_VAR,
                apagar_arquivos=True,
                conn=conn
            ).load_db()

    def uy_tres(self):
        def preprocess_fgts(df):
            df.columns = [c.strip().lower() for c in df.columns]
            colunas_esperadas = [
                "corban", "cliente", "produto", "produto detalhado", "operação",
                "vop", "juros da op", "iof", "líquido", "custo de emissão", "r$ comissão"
            ]
            
            if any(c not in df.columns for c in colunas_esperadas):
                return pd.DataFrame()
            return df

        pasta_base = Path(r'C:\mock_network_share\comissoes\Geral\FATURAS - SANTANDER')
        
        for ano in range(2025, 2026):
            pasta_ano = pasta_base / str(ano)
            if not pasta_ano.exists():
                continue
            
            for pasta_fgts in pasta_ano.rglob("*fgts*"):
                if pasta_fgts.is_dir():
                    utils_core.LoadArquivoDB(
                        extensoes=(".csv", ".xlsx"),
                        partes_nome=["uy3"],
                        pasta=str(pasta_fgts),
                        tabela="comissao_uy3",
                        env_var=ENV_VAR,
                        preprocess_func=preprocess_fgts
                    ).load_db()

        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["uy3-prod"],
            pasta=str(PASTA_DOWNLOADS),
            tabela="contratos_uy3",
            env_var=ENV_VAR,
            apagar_arquivos=True
        ).load_db()

    def rodar_processos(self):
        self.banco_brasil()
        self.contratos_nova()
        self.uy_tres()

class Veiculos:
    def santander(self):
        colunas_financeiro = {'tipo_de_veiculo', 'condicao', 'valor_liberado', 'status'}
        
        for arquivo in PASTA_DOWNLOADS.glob('*extrato_*.csv'):
            df = pd.read_csv(arquivo, sep=';', on_bad_lines='skip')
            df.columns = [utils_core.Geral.normalize_table_name(c) for c in df.columns]
            
            if 'data_do_extrato' in df.columns:
                df = df.drop(columns='data_do_extrato')
                
            tipo = 'financeiro' if colunas_financeiro.issubset(df.columns) else 'comissao'
            novo_nome = f'extrato_{tipo}_plataforma_{arquivo.stem}.xlsx'
            
            df.to_excel(PASTA_DOWNLOADS / novo_nome, index=False)
            arquivo.unlink()

        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["extrato_comissao_plataforma_"],
            pasta=str(PASTA_DOWNLOADS),
            tabela="extrato_comissao_plataforma",
            env_var=ENV_VAR,
            apagar_arquivos=False
        ).load_db()

        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["extrato_financeiro_plataforma_"],
            pasta=str(PASTA_DOWNLOADS),
            tabela="extrato_financeiro_plataforma",
            env_var=ENV_VAR,
            apagar_arquivos=False
        ).load_db()

        pasta_json = Path(r"C:\mock_downloads")
        registros = []

        for arquivo in pasta_json.glob("extrato_comissao_finveiculo_vivero*.json"):
            with open(arquivo, "r", encoding="utf-8") as f:
                data = json.load(f)

            detalhe = data.get("extratoComissaoDetalheContrato", {})
            contrato = detalhe.get("contrato", {})
            cliente = detalhe.get("dadosCliente", {})
            acordo = detalhe.get("acordo", {})
            resumo = data.get("resumoExtratoComissaoContratoDetalhe", {})

            registros.append({
                "idContrato": contrato.get("idContrato"),
                "nrCpfCnpj": cliente.get("nrCpfCnpj"),
                "nrChassi": str(cliente.get("nrChassi", "")).strip(),
                "vlLiquido": float(contrato.get("vlLiquido", 0)),
                "dtEmissao": contrato.get("dtEmissao"),
                "dtLiberacao": contrato.get("dtLiberacao"),
                "dtPagamento": contrato.get("dtPagamento"),
                "nrAcordo": acordo.get("nrAcordo"),
                "tipoComissao": acordo.get("dsTipoComissao"),
                "vlBruto": float(acordo.get("vlBruto", 0)),
                "vlIR": float(acordo.get("vlIR", 0)),
                "vlISS": float(acordo.get("vlISS", 0)),
                "pcIla": float(acordo.get("pcIla", 0)),
                "vlIla": float(acordo.get("vlIla", 0)),
                "dtInicial": resumo.get("dtInicial"),
                "dtFinal": resumo.get("dtFinal"),
                "vlLiquidoTotal": float(resumo.get("vlLiquidoTotal", 0))
            })

        if registros:
            pd.DataFrame(registros).to_excel(pasta_json / "extrato_comissao_finitau_vivero_consolidado.xlsx", index=False)

            utils_core.LoadArquivoDB(
                extensoes=(".xlsx",),
                partes_nome=["extrato_comissao_finitau_vivero_consolidado"],
                pasta=str(pasta_json),
                tabela="extrato_financeiro_vivero",
                env_var=ENV_VAR,
                apagar_arquivos=False
            ).load_db()

class Consorcio:
    def ancora(self):
        def normalizar_colunas(cols):
            return (
                cols
                .str.normalize('NFKD')
                .str.encode('ascii', errors='ignore')
                .str.decode('utf-8')
                .str.lower()
                .str.strip()
                .str.replace(' ', '_')
                .str.replace('%', 'perc', regex=False)
                .str.replace(r'[^\w_]', '', regex=True)
            )

        def preprocess_ancora(df):
            df.columns = normalizar_colunas(df.columns.str.lower())
            
            mapa_colunas = {
                'no_doc': 'n_doc', 'repres': 'repres', 'data': 'data',
                'descricao': 'descricao', 'tipo': 'tipo', 'contrato': 'contrato',
                'venda': 'venda', 'grupo': 'grupo', 'cota': 'cota',
                'parcela': 'parcela', 'valor_base_carta_de_credito': 'valor_base', 'valor': 'valor'
            }
            
            df = df.rename(columns=mapa_colunas)[list(mapa_colunas.values())]
            df["data"] = pd.to_datetime(df["data"], dayfirst=True)
            df["venda"] = pd.to_datetime(df["venda"], dayfirst=True)
            df['usuario_insercao'] = 30209
            
            return df

        pasta_comissao_ancora = r'C:\mock_network_share\conta_integrada\CONTA INTEGRADA\02 - JOANA - GESTÃO DE DESEMPENHO E RELATÓRIOS GERENCIAIS\FECHAMENTO\2025\CONSÓRCIO'
        
        utils_core.LoadArquivoDB(
            extensoes=(".xlsx",),
            partes_nome=["comissãoplanilhamãe"],
            pasta=pasta_comissao_ancora,
            tabela="relatorio_comissao_ancora",
            env_var=ENV_VAR,
            apagar_arquivos=False,
            preprocess_func=preprocess_ancora
        ).load_db('TABELA DE VENDAS')
class Seguros:
    def seguros(self):
        utils_core.LoadArquivoDB(
            extensoes=(".csv",),
            partes_nome=["extrato de comissao de seguro auto"],
            pasta=r'C:\mock_downloads',
            tabela="comissao_seguro_auto",
            env_var=ENV_VAR,
            apagar_arquivos=False
        ).load_db()

if __name__ == "__main__":
    Consignado().rodar_processos()
    Veiculos().santander()
    Seguros().seguros()