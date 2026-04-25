
# PriceDetection: Dashboard Streamlit

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

#Configuração da página
st.set_page_config(
    page_title="PriceDetection: um novíssimo Detector de Preços",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

#Estilo customizado
st.markdown("""
<style>
    .main-title {
        background: linear-gradient(135deg, #0a0a2e, #3d1278, #7F77DD);
        padding: 20px 30px; border-radius: 12px;
        color: white; margin-bottom: 20px;
    }
    .metric-card {
        background: #f8f9ff; border: 1px solid #e0d8ff;
        border-radius: 10px; padding: 15px; text-align: center;
    }
    .promo-badge {
        background: #e1f5ee; color: #0f6e56;
        padding: 2px 8px; border-radius: 20px;
        font-size: 12px; font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


#Conexão com o banco
@st.cache_resource
def get_connection():
    conn = sqlite3.connect("priceradar.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_connection()


#Funções de consulta (com cache)
@st.cache_data(ttl=300)  #cache por 5 minutos
def listar_produtos():
    return pd.read_sql(
        "SELECT id, nome, marca, unidade FROM produtos ORDER BY nome, marca", conn
    )

@st.cache_data(ttl=300)
def precos_hoje(produto_id):
    return pd.read_sql(
        """
        SELECT s.nome AS supermercado, s.bairro,
               ROUND(pr.preco, 2) AS preco, pr.em_promocao
        FROM precos pr
        JOIN supermercados s ON s.id = pr.supermercado_id
        WHERE pr.produto_id = ? AND pr.data_coleta = DATE('now')
        ORDER BY pr.preco ASC
        """, conn, params=(produto_id,)
    )

@st.cache_data(ttl=300)
def historico(produto_id, dias=30):
    return pd.read_sql(
        """
        SELECT pr.data_coleta, s.nome AS supermercado,
               ROUND(pr.preco, 2) AS preco, pr.em_promocao,
               ROUND(AVG(pr.preco) OVER (
                   PARTITION BY pr.supermercado_id
                   ORDER BY pr.data_coleta
                   ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
               ), 2) AS media_movel_7d
        FROM precos pr
        JOIN supermercados s ON s.id = pr.supermercado_id
        WHERE pr.produto_id  = ?
          AND pr.data_coleta >= DATE('now', ?)
        ORDER BY pr.data_coleta
        """, conn, params=(produto_id, f"-{dias} days")
    )

@st.cache_data(ttl=300)
def comparar_lista(produtos_selecionados):
    placeholders = ",".join(["?"]*len(produtos_selecionados))
    return pd.read_sql(
        f"""
        SELECT s.nome AS supermercado,
               COUNT(DISTINCT p.id)     AS itens_encontrados,
               ROUND(SUM(pr.preco), 2)  AS total_lista,
               ROUND(AVG(pr.preco), 2)  AS preco_medio_item
        FROM precos pr
        JOIN supermercados s ON s.id = pr.supermercado_id
        JOIN produtos       p ON p.id = pr.produto_id
        WHERE pr.data_coleta = DATE('now')
          AND pr.em_promocao = 0
          AND p.id IN ({placeholders})
        GROUP BY s.id
        ORDER BY total_lista ASC
        """, conn, params=produtos_selecionados
    )

@st.cache_data(ttl=300)
def promocoes_hoje():
    return pd.read_sql(
        """
        WITH hist AS (
            SELECT produto_id, supermercado_id, preco, data_coleta,
                   LAG(preco) OVER (
                       PARTITION BY produto_id, supermercado_id
                       ORDER BY data_coleta
                   ) AS preco_anterior
            FROM precos
        )
        SELECT p.nome AS produto, p.unidade, s.nome AS supermercado,
               ROUND(h.preco_anterior, 2) AS preco_antes,
               ROUND(h.preco, 2)          AS preco_agora,
               ROUND((h.preco-h.preco_anterior)*100.0/h.preco_anterior, 1) AS queda_pct
        FROM hist h
        JOIN produtos p ON p.id = h.produto_id
        JOIN supermercados s ON s.id = h.supermercado_id
        WHERE h.preco_anterior IS NOT NULL
          AND h.preco < h.preco_anterior * 0.95
          AND h.data_coleta = DATE('now')
        ORDER BY queda_pct ASC
        """, conn
    )


# SIDEBAR
with st.sidebar:
    st.markdown("### 🛒 PriceDetection")
    st.markdown("*um novíssimo Detector de Preçoso*")
    st.divider()

    pagina = st.radio(
        "Navegação",
        ["Buscar Produto", "Histórico de Preços", "Comparar Lista", "Promoções de Hoje"],
        label_visibility="collapsed"
    )

    st.divider()
    st.caption(f"Dados atualizados em: {date.today().strftime('%d/%m/%Y')}")
    total = pd.read_sql("SELECT COUNT(*) AS n FROM precos", conn).iloc[0,0]
    st.caption(f"Total de registros: {total:,}")



# PÁGINA 1: BUSCAR PRODUTO
if pagina == "Buscar Produto":

    st.markdown("""
    <div class='main-title'>
    <h2 style='margin:0'>Buscar Produto</h2>
    <p style='margin:4px 0 0; color:#c8b8f8'>Compare preços de hoje entre todos os supermercados</p>
    </div>
    """, unsafe_allow_html=True)

    df_produtos = listar_produtos()
    df_produtos["label"] = df_produtos["nome"] + " — " + df_produtos["marca"] + " (" + df_produtos["unidade"] + ")"

    col1, col2 = st.columns([3, 1])
    with col1:
        produto_label = st.selectbox(
            "Selecione o produto:",
            df_produtos["label"].tolist()
        )
    with col2:
        st.write("")
        st.write("")
        buscar = st.button("Buscar", use_container_width=True)

    produto_id = int(df_produtos.loc[df_produtos["label"] == produto_label, "id"].values[0])

    df_precos = precos_hoje(produto_id)

    if len(df_precos) > 0:
        mais_barato  = df_precos.iloc[0]
        mais_caro    = df_precos.iloc[-1]
        economia     = mais_caro["preco"] - mais_barato["preco"]

        # Métricas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Menor preço",    f"R$ {mais_barato['preco']:.2f}",  mais_barato['supermercado'])
        c2.metric("Maior preço",    f"R$ {mais_caro['preco']:.2f}",    mais_caro['supermercado'])
        c3.metric("Economia", f"R$ {economia:.2f}",              f"{economia/mais_barato['preco']*100:.1f}%")
        c4.metric("Mercados",        len(df_precos),                   "monitorados")

        st.divider()

        col_a, col_b = st.columns([1, 1])

        with col_a:
            st.subheader("Preços por supermercado")
            df_precos["cor"] = df_precos["supermercado"].apply(
                lambda x: "#55A868" if x == mais_barato["supermercado"] else "#7F77DD"
            )
            fig = px.bar(
                df_precos, x="supermercado", y="preco",
                text="preco", color="supermercado",
                color_discrete_map={mais_barato["supermercado"]: "#55A868"},
            )
            fig.update_traces(texttemplate="R$ %{text:.2f}", textposition="outside")
            fig.update_layout(
                showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Preço (R$)", xaxis_title=""
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.subheader("Tabela de preços")
            df_display = df_precos[["supermercado", "bairro", "preco", "em_promocao"]].copy()
            df_display["em_promocao"] = df_display["em_promocao"].apply(
                lambda x: "Sim" if x == 1 else "—"
            )
            df_display.columns = ["Supermercado", "Bairro", "Preço (R$)", "Promoção"]
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            if economia > 0:
                st.success(f"Comprando no **{mais_barato['supermercado']}** você economiza **R$ {economia:.2f}** em relação ao {mais_caro['supermercado']}")
    else:
        st.warning("Nenhum preço encontrado para hoje. Execute o coletor primeiro.")


#PÁGINA 2: HISTÓRICO

elif pagina == "Histórico de Preços":

    st.markdown("""
    <div class='main-title'>
    <h2 style='margin:0'>Histórico de Preços</h2>
    <p style='margin:4px 0 0; color:#c8b8f8'>Evolução e tendência ao longo do tempo</p>
    </div>
    """, unsafe_allow_html=True)

    df_produtos = listar_produtos()
    df_produtos["label"] = df_produtos["nome"] + " — " + df_produtos["marca"] + " (" + df_produtos["unidade"] + ")"

    col1, col2 = st.columns([3, 1])
    with col1:
        produto_label = st.selectbox("Produto:", df_produtos["label"].tolist(), key="hist_prod")
    with col2:
        dias = st.select_slider("Período:", options=[7, 14, 21, 30], value=30)

    produto_id = int(df_produtos.loc[df_produtos["label"] == produto_label, "id"].values[0])
    df_hist    = historico(produto_id, dias)

    if len(df_hist) > 0:
        # Tabs para diferentes visualizações
        tab1, tab2, tab3 = st.tabs(["Linha", "Área", "Tabela"])

        with tab1:
            col_toggle = st.checkbox("Mostrar média móvel 7 dias", value=True)
            fig = px.line(
                df_hist[df_hist["em_promocao"]==0],
                x="data_coleta", y="preco", color="supermercado",
                markers=True,
                title=f"Histórico de preços — {produto_label}",
            )
            if col_toggle:
                for mercado in df_hist["supermercado"].unique():
                    df_m = df_hist[df_hist["supermercado"]==mercado]
                    fig.add_scatter(
                        x=df_m["data_coleta"], y=df_m["media_movel_7d"],
                        mode="lines", line=dict(dash="dash", width=1),
                        name=f"MM7d {mercado}", opacity=0.5
                    )
            fig.update_layout(xaxis_title="Data", yaxis_title="Preço (R$)")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            media_dia = df_hist.groupby("data_coleta")["preco"].mean().reset_index()
            fig2 = px.area(
                media_dia, x="data_coleta", y="preco",
                title="Preço médio diário (todos os mercados)",
                color_discrete_sequence=["#7F77DD"]
            )
            fig2.update_layout(xaxis_title="Data", yaxis_title="Preço médio (R$)")
            st.plotly_chart(fig2, use_container_width=True)

        with tab3:
            st.dataframe(
                df_hist[["data_coleta","supermercado","preco","media_movel_7d","em_promocao"]],
                use_container_width=True, hide_index=True
            )


#PÁGINA 3: COMPARAR LISTA

elif pagina == "Comparar Lista":

    st.markdown("""
    <div class='main-title'>
    <h2 style='margin:0'>Comparar Lista de Compras</h2>
    <p style='margin:4px 0 0; color:#c8b8f8'>Descubra onde comprar sua lista completa pelo menor preço</p>
    </div>
    """, unsafe_allow_html=True)

    df_produtos = listar_produtos()
    df_produtos["label"] = df_produtos["nome"] + " — " + df_produtos["marca"] + " (" + df_produtos["unidade"] + ")"

    selecionados_labels = st.multiselect(
        "Selecione os produtos da sua lista:",
        df_produtos["label"].tolist(),
        default=df_produtos["label"].tolist()[:4]
    )

    if len(selecionados_labels) > 0:
        ids = df_produtos.loc[df_produtos["label"].isin(selecionados_labels), "id"].tolist()
        df_comp = comparar_lista(ids)

        mais_barato = df_comp.iloc[0]
        mais_caro   = df_comp.iloc[-1]
        economia    = mais_caro["total_lista"] - mais_barato["total_lista"]

        col1, col2 = st.columns([1,1])

        with col1:
            st.subheader("🏆 Ranking de supermercados")
            fig = px.bar(
                df_comp, x="supermercado", y="total_lista",
                text="total_lista", color="total_lista",
                color_continuous_scale="RdYlGn_r"
            )
            fig.update_traces(texttemplate="R$ %{text:.2f}", textposition="outside")
            fig.update_layout(
                showlegend=False, coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="Total (R$)"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Resumo")
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
            st.success(f"Comprando no **{mais_barato['supermercado']}** você economiza **R$ {economia:.2f}** vs. o {mais_caro['supermercado']}")
            pct_economia = economia / mais_caro["total_lista"] * 100
            st.info(f"Isso representa **{pct_economia:.1f}%** de desconto na lista completa")
    else:
        st.info("Selecione ao menos um produto para comparar.")


#PÁGINA 4: PROMOÇÕES

elif pagina == "Promoções de Hoje":

    st.markdown("""
    <div class='main-title'>
    <h2 style='margin:0'>Promoções de Hoje</h2>
    <p style='margin:4px 0 0; color:#c8b8f8'>Produtos com queda de preço acima de 5% vs. ontem</p>
    </div>
    """, unsafe_allow_html=True)

    df_promo = promocoes_hoje()

    if len(df_promo) > 0:
        st.success(f"{len(df_promo)} promoções encontradas hoje!")

        fig = px.bar(
            df_promo, x="produto", y="queda_pct",
            color="supermercado", barmode="group",
            title="Queda de preço por produto e supermercado (%)",
            text="queda_pct"
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="", yaxis_title="Queda (%)"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalhes das promoções")
        df_promo["queda_pct"] = df_promo["queda_pct"].apply(lambda x: f"{x:.1f}%")
        df_promo.columns = ["Produto","Unidade","Supermercado","Preço Antes","Preço Agora","Queda"]
        st.dataframe(df_promo, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma promoção detectada hoje (queda < 5%).")
