import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os

# Configuração da página para Mobile First
st.set_page_config(page_title="RH Comunica", layout="centered", initial_sidebar_state="collapsed")

# --- ARQUIVOS DE DADOS ---
FILE_MENSAGENS = "MENSAGENS_ENVIADAS.csv"
FILE_COLABS = "DADOS_COLABORADORES.xlsx"

# Inicializa o arquivo de mensagens com colunas de texto (evita erros de tipo)
if not os.path.exists(FILE_MENSAGENS):
    pd.DataFrame(columns=["data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"]).to_csv(FILE_MENSAGENS, index=False)

# --- FUNÇÕES DE LIMPEZA E LOGÍSTICA ---
def limpar_cpf(cpf):
    """Garante que o CPF tenha 11 dígitos numéricos, tratando zeros à esquerda."""
    s = str(cpf).split('.')[0]
    s = re.sub(r'\D', '', s)
    return s.zfill(11)

@st.cache_data(ttl=60)
def carregar_colaboradores():
    if os.path.exists(FILE_COLABS):
        try:
            df = pd.read_excel(FILE_COLABS)
            df.columns = [c.strip() for c in df.columns]
            df['CPF_LIMPO'] = df['CPF'].apply(limpar_cpf)
            return df
        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")
            return None
    return None

def carregar_mensagens():
    # Forçamos todas as colunas a serem lidas como texto (string) para evitar erros de tipo
    return pd.read_csv(FILE_MENSAGENS, dtype=str).fillna("")

# --- INTERFACE PRINCIPAL ---
df_base = carregar_colaboradores()

if "logado" not in st.session_state:
    st.session_state.update({"logado": False, "user_cpf": "", "is_admin": False, "user_nome": ""})

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("📲 RH Comunica - Login")
    cpf_input = st.text_input("Digite seu CPF (apenas números):", placeholder="Ex: 050...")
    
    if st.button("Entrar no Sistema", use_container_width=True):
        if cpf_input == "000": # Senha Admin
            st.session_state.update({"logado": True, "is_admin": True})
            st.rerun()
            
        cpf_busca = limpar_cpf(cpf_input)
        
        if df_base is not None:
            user = df_base[df_base['CPF_LIMPO'] == cpf_busca]
            if not user.empty:
                st.session_state.update({
                    "logado": True, 
                    "user_cpf": cpf_busca, 
                    "user_nome": user.iloc[0]['Nome']
                })
                st.rerun()
            else:
                st.error("CPF não encontrado na base do RH.")
        else:
            st.warning("O RH ainda não subiu a base de dados.")

else:
    # BOTÃO SAIR
    if st.sidebar.button("Logoff / Sair"):
        st.session_state.logado = False
        st.rerun()

    if st.session_state.is_admin:
        st.title("🛠️ Painel Administrativo")
        tab1, tab2, tab3 = st.tabs(["🚀 Enviar Mensagens", "📊 Relatório de Leitura", "⚙️ Base de Dados"])
        
        with tab3:
            st.subheader("Atualizar Colaboradores")
            new_file = st.file_uploader("Nova Planilha Excel", type="xlsx")
            if st.button("Substituir Base Atual"):
                if new_file:
                    with open(FILE_COLABS, "wb") as f:
                        f.write(new_file.getbuffer())
                    st.cache_data.clear()
                    st.success("Base de dados atualizada!")
                    st.rerun()

        with tab1:
            modo = st.radio("Destinatários:", ["Por Obra", "Lista Manual (Colar)"], horizontal=True)
            cpfs_alvo = []
            
            if df_base is not None:
                if modo == "Por Obra":
                    obras = st.multiselect("Selecione as Obras:", options=sorted(df_base['OBRA'].unique()))
                    cpfs_alvo = df_base[df_base['OBRA'].isin(obras)]['CPF_LIMPO'].tolist()
                else:
                    txt_area = st.text_area("Cole os CPFs aqui:")
                    raw_cpfs = re.findall(r'\d+', txt_area)
                    cpfs_alvo = [c.zfill(11) for c in raw_cpfs if len(c) <= 11]
                
                st.metric("Total de Alvos", len(cpfs_alvo))
                msg_txt = st.text_area("Escreva o comunicado:", height=200)
                
                if st.button("DISPARAR COMUNICADO", use_container_width=True):
                    if cpfs_alvo and msg_txt:
                        df_m = carregar_mensagens()
                        novas = []
                        for c in cpfs_alvo:
                            match = df_base[df_base['CPF_LIMPO'] == c]
                            nome = match.iloc[0]['Nome'] if not match.empty else "NÃO CADASTRADO"
                            novas.append({
                                "data_envio": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "cpf_destino": c,
                                "nome_destino": nome,
                                "mensagem": msg_txt,
                                "lido": "Não",
                                "data_leitura": ""
                            })
                        pd.concat([df_m, pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_MENSAGENS, index=False)
                        st.success(f"Enviado para {len(cpfs_alvo)} pessoas!")
                    else:
                        st.error("Preencha os destinatários e a mensagem.")

        with tab2:
            st.subheader("Histórico de Envios")
            st.dataframe(carregar_mensagens().sort_values(by="data_envio", ascending=False), use_container_width=True)

    # --- VISÃO DO COLABORADOR ---
    else:
        st.title(f"Olá, {st.session_state.user_nome.split()[0]}!")
        df_m = carregar_mensagens()
        minhas = df_m[df_m['cpf_destino'] == st.session_state.user_cpf].copy()
        
        if not minhas.empty:
            for _, r in minhas.iloc[::-1].iterrows():
                with st.chat_message("assistant"):
                    st.write(f"📅 **{r['data_envio']}**")
                    st.markdown(r['mensagem'])
            
            # Lógica corrigida para marcar como lido
            # Buscamos as mensagens do usuário logado que ainda estão como "Não" lidas
            indices_para_atualizar = df_m[(df_m['cpf_destino'] == st.session_state.user_cpf) & (df_m['lido'] == "Não")].index
            
            if len(indices_para_atualizar) > 0:
                df_m.loc[indices_para_atualizar, 'lido'] = "Sim"
                df_m.loc[indices_para_atualizar, 'data_leitura'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                df_m.to_csv(FILE_MENSAGENS, index=False)
                st.toast("Mensagens visualizadas!")
        else:
            st.info("Você não tem comunicados pendentes no momento.")
