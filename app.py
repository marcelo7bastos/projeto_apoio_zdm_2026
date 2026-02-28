import json
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_FILE = Path(__file__).resolve().parent / "data" / "df_merged.csv"
MG_GEOJSON_URL = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-31-mun.json"

CREDIT_COL = "Cr\u00e9dito Pronaf em 2025 (R$)"
IMMEDIATE_REGION_COL = "Regi\u00e3o Geogr\u00e1fica Imediata (2022)"
MUNICIPALITY_COL = "Munic\u00edpio"
IBGE_COL = "C\u00f3digo IBGE"
AF_COL = "Quantidade de Agricultores Familiares"
WOMEN_COL = "QUANTIDADE DE MULHERES EM CAF ATIVO"
MEN_COL = "QUANTIDADE DE HOMENS EM CAF ATIVO"
CAF_PF_COL = "CAFs PF ATIVO"
OPERATIONS_COL = "Opera\u00e7\u00f5es em 2025"

NUMERIC_COLUMNS = [
    CAF_PF_COL,
    "CAFs PJ ATIVO",
    WOMEN_COL,
    MEN_COL,
    AF_COL,
    OPERATIONS_COL,
    CREDIT_COL,
]

INTEGER_COLUMNS = [
    CAF_PF_COL,
    "CAFs PJ ATIVO",
    WOMEN_COL,
    MEN_COL,
    AF_COL,
]


def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def configure_page() -> None:
    st.set_page_config(
        page_title="Central de Monitoramento - Zona da Mata/MG",
        page_icon=":bar_chart:",
        layout="wide",
    )

    st.title("Monitoramento de Impacto - Agricultura Familiar (Zona da Mata/MG)")
    st.caption(
        "Central estrat\u00e9gica para monitorar exposi\u00e7\u00e3o econ\u00f4mica, priorizar munic\u00edpios e "
        "apoiar decis\u00f5es emergenciais de aloca\u00e7\u00e3o de recursos p\u00fablicos."
    )


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    treated_df = df.copy()

    for col in NUMERIC_COLUMNS:
        if col in treated_df.columns:
            treated_df[col] = pd.to_numeric(treated_df[col], errors="coerce")

    if CREDIT_COL in treated_df.columns:
        treated_df[CREDIT_COL] = treated_df[CREDIT_COL].fillna(0.0).astype(float)

    for col in INTEGER_COLUMNS:
        if col in treated_df.columns:
            treated_df[col] = treated_df[col].fillna(0).round().astype(int)

    if IBGE_COL in treated_df.columns:
        treated_df[IBGE_COL] = pd.to_numeric(treated_df[IBGE_COL], errors="coerce").astype("Int64")

    return treated_df


@st.cache_data(show_spinner=False)
def load_data(file_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        raise

    return preprocess_data(df)


@st.cache_data(show_spinner=False)
def load_mg_geojson() -> dict:
    with urlopen(MG_GEOJSON_URL, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros Estrat\u00e9gicos")

    immediate_regions = ["Todas"] + sorted(df[IMMEDIATE_REGION_COL].dropna().unique().tolist())
    selected_region = st.sidebar.selectbox(
        "Regi\u00e3o Geogr\u00e1fica Imediata (2022)",
        options=immediate_regions,
        index=0,
    )

    region_df = df if selected_region == "Todas" else df[df[IMMEDIATE_REGION_COL] == selected_region]

    municipality_options = ["Todos"] + sorted(region_df[MUNICIPALITY_COL].dropna().unique().tolist())
    selected_municipalities = st.sidebar.multiselect(
        "Munic\u00edpio",
        options=municipality_options,
        default=["Todos"],
    )

    if not selected_municipalities or "Todos" in selected_municipalities:
        return region_df

    return region_df[region_df[MUNICIPALITY_COL].isin(selected_municipalities)]


def render_kpis(df: pd.DataFrame) -> None:
    total_agricultores = int(df[AF_COL].sum())
    total_credito = float(df[CREDIT_COL].sum())
    total_mulheres = int(df[WOMEN_COL].sum())
    total_municipios = int(df[MUNICIPALITY_COL].nunique())

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total de Agricultores Familiares Atingidos", format_int(total_agricultores))
    kpi2.metric("Volume Financeiro Total do Pronaf em Risco", format_brl(total_credito))
    kpi3.metric("Total de Mulheres com CAF Ativo", format_int(total_mulheres))
    kpi4.metric("N\u00famero de Munic\u00edpios Selecionados", format_int(total_municipios))


def build_impacted_farmers_map(df: pd.DataFrame):
    map_df = df[[IBGE_COL, MUNICIPALITY_COL, AF_COL]].dropna(subset=[IBGE_COL]).copy()
    map_df[IBGE_COL] = map_df[IBGE_COL].astype(int).astype(str).str.zfill(7)
    geojson = load_mg_geojson()

    fig = px.choropleth_mapbox(
        map_df,
        geojson=geojson,
        locations=IBGE_COL,
        featureidkey="properties.id",
        color=AF_COL,
        hover_name=MUNICIPALITY_COL,
        color_continuous_scale="YlOrRd",
        mapbox_style="carto-positron",
        center={"lat": -20.75, "lon": -42.85},
        zoom=6.2,
        opacity=0.7,
        labels={AF_COL: "Agricultores Atingidos"},
        title="Mapa da Regi\u00e3o - Total de Agricultores Familiares Atingidos",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    return fig


def build_credit_concentration_chart(df: pd.DataFrame):
    top_10 = df.nlargest(10, CREDIT_COL).sort_values(CREDIT_COL, ascending=True)

    fig = px.bar(
        top_10,
        x=CREDIT_COL,
        y=MUNICIPALITY_COL,
        orientation="h",
        color=CREDIT_COL,
        color_continuous_scale="YlOrRd",
        title="Concentra\u00e7\u00e3o do Cr\u00e9dito Pronaf em Risco",
        labels={
            CREDIT_COL: "Cr\u00e9dito Pronaf em 2025 (R$)",
            MUNICIPALITY_COL: "Munic\u00edpio",
        },
        hover_data={CREDIT_COL: ":,.2f"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0), coloraxis_showscale=False)
    fig.update_xaxes(tickprefix="R$ ")
    return fig


def build_vulnerability_scatter(df: pd.DataFrame):
    fig = px.scatter(
        df,
        x=AF_COL,
        y=CREDIT_COL,
        size=CAF_PF_COL,
        color=IMMEDIATE_REGION_COL,
        hover_name=MUNICIPALITY_COL,
        size_max=45,
        title="Matriz de Vulnerabilidade Econ\u00f4mica Municipal",
        labels={
            AF_COL: "Quantidade de Agricultores Familiares",
            CREDIT_COL: "Cr\u00e9dito Pronaf em 2025 (R$)",
            CAF_PF_COL: "CAFs PF ATIVO",
            IMMEDIATE_REGION_COL: "Regi\u00e3o Imediata",
        },
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    fig.update_yaxes(tickprefix="R$ ")
    return fig


def build_gender_donut(df: pd.DataFrame):
    gender_df = pd.DataFrame(
        {
            "G\u00eanero": ["Mulheres", "Homens"],
            "Quantidade": [int(df[WOMEN_COL].sum()), int(df[MEN_COL].sum())],
        }
    )

    fig = px.pie(
        gender_df,
        names="G\u00eanero",
        values="Quantidade",
        hole=0.6,
        color="G\u00eanero",
        color_discrete_map={"Mulheres": "#d1495b", "Homens": "#00798c"},
        title="Distribui\u00e7\u00e3o de G\u00eanero - CAF Ativo",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


@st.cache_data(show_spinner=False)
def dataframe_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def render_dashboard(df: pd.DataFrame) -> None:
    st.subheader("Indicadores Estrat\u00e9gicos (Vis\u00e3o Macro)")
    render_kpis(df)
    st.markdown("---")

    st.subheader("Vulnerabilidade Econ\u00f4mica Municipal")
    map_col, scatter_col = st.columns(2)
    with map_col:
        try:
            st.plotly_chart(build_impacted_farmers_map(df), use_container_width=True)
        except Exception:
            st.warning(
                "N\u00e3o foi poss\u00edvel carregar o mapa geogr\u00e1fico no momento. "
                "Exibindo o ranking de concentra\u00e7\u00e3o de cr\u00e9dito."
            )
            st.plotly_chart(build_credit_concentration_chart(df), use_container_width=True)

    with scatter_col:
        st.plotly_chart(build_vulnerability_scatter(df), use_container_width=True)

    st.plotly_chart(build_credit_concentration_chart(df), use_container_width=True)

    st.markdown("---")
    st.subheader("Perfil Demogr\u00e1fico e Detalhamento")
    donut_col, table_col = st.columns([1, 2])
    with donut_col:
        st.plotly_chart(build_gender_donut(df), use_container_width=True)

    with table_col:
        st.subheader("Base Filtrada de Munic\u00edpios")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            label="Exportar dados filtrados em CSV",
            data=dataframe_to_csv(df),
            file_name="monitoramento_impacto_zona_mata.csv",
            mime="text/csv",
            use_container_width=True,
        )


def main() -> None:
    configure_page()

    try:
        base_df = load_data(DATA_FILE)
    except FileNotFoundError:
        st.error(f"Arquivo n\u00e3o encontrado: {DATA_FILE}")
        st.stop()

    filtered_df = filter_data(base_df)
    if filtered_df.empty:
        st.warning("Nenhum registro encontrado para os filtros selecionados.")
        st.stop()

    render_dashboard(filtered_df)


if __name__ == "__main__":
    main()
