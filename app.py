import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os

st.set_page_config(page_title="RH Comunica", layout="centered")

# --- ARQUIVOS DE DADOS ---
FILE_MENSAGENS = "MENSAGENS_ENVIADAS.csv"
FILE_COLABS = "DADOS_COLABORADORES.xlsx"

# Inicializa arquivos se não existirem
if not os.path.exists(FILE_MENSAGENS):
    pd.DataFrame(columns=["data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"]).to_csv(FILE_MENSAGENS, index=False)

# --- FUNÇÕES ---
def limpar_cpf(cpf):
    return re.sub(r'\D', '', str(cpf))

def carregar_colaboradores():
    if os.path.exists(FILE_COLABS):
        try:
            df = pd.read_excel(FILE_COLABS)
            df['CPF_LIMPO'] = df['CPF'].apply(limpar_cpf)
            return df
        except:
            return None
    return None

def carregar_mensagens():
    return pd.read_csv(FILE_MENSAGENS, dtype={"cpf_destino": str})

# --- INTERFACE ---
df_base = carregar_colaboradores()

if "logado" not in st.session_state:
    st.session_state.update({"logado": False, "user_cpf": "", "is_admin": False})

if not st.session_state.logado:
    st.title("📲 RH Comunica - Login")
    cpf_input = st.text_input("CPF (apenas números):")
    
    if st.button("Entrar"):
        if cpf_input == "000": # Senha Admin provisória
            st.session_state.update({"logado": True, "is_admin": True})
            st.rerun()
            
        cpf_busca = limpar_cpf(cpf_input)
        if df_base is not None:
            user = df_base[df_base['CPF_LIMPO'] == cpf_busca]
            if not user.empty:
                st.session_state.update({"logado": True, "user_cpf": cpf_busca, "user_nome": user.iloc[0]['Nome']})
                st.rerun()
            else:
                st.error("CPF não cadastrado.")
        else:
            st.error("Base de dados não encontrada. Contate o Administrador.")

else:
    if st.session_state.is_admin:
        st.title("🛠️ Painel Admin")
        tab1, tab2, tab3 = st.tabs(["🚀 Enviar", "📊 Relatório", "⚙️ Configurar Base"])
        
        with tab3:
            st.subheader("Atualizar Lista de Colaboradores")
            st.write("Tirou uma planilha nova do sistema? Suba ela aqui:")
            new_file = st.file_uploader("Arraste o novo Excel aqui", type="xlsx")
            if st.button("Substituir Base Atual"):
                if new_file:
                    with open(FILE_COLABS, "wb") as f:
                        f.write(new_file.getbuffer())
                    st.success("Planilha atualizada! O sistema já reconhece os novos nomes e CPFs.")
                    st.cache_data.clear()
                    st.rerun()

        with tab1:
            modo = st.radio("Destinatários:", ["Por Obra", "Colar CPFs"])
            cpfs_alvo = []
            if df_base is not None:
                if modo == "Por Obra":
                    obras = st.multiselect("Obras:", df_base['OBRA'].unique())
                    cpfs_alvo = df_base[df_base['OBRA'].isin(obras)]['CPF_LIMPO'].tolist()
                else:
                    txt_cpfs = st.text_area("Cole os CPFs:")
                    cpfs_alvo = re.findall(r'\d+', txt_cpfs)
                
                st.info(f"Destinatários: {len(cpfs_alvo)}")
                msg = st.text_area("Mensagem:")
                if st.button("ENVIAR"):
                    df_m = carregar_mensagens()
                    novos = []
                    for c in cpfs_alvo:
                        nome = df_base[df_base['CPF_LIMPO'] == c]['Nome'].values[0] if c in df_base['CPF_LIMPO'].values else "Novo"
                        novos.append({"data_envio": datetime.now().strftime("%d/%m/%Y %H:%M"), "cpf_destino": c, "nome_destino": nome, "mensagem": msg, "lido": "Não"})
                    pd.concat([df_m, pd.DataFrame(novos)]).to_csv(FILE_MENSAGENS, index=False)
                    st.success("Enviado!")
            else:
                st.warning("Suba a planilha na aba 'Configurar Base' primeiro.")

        with tab2:
            st.dataframe(carregar_mensagens())

    else:
        st.title(f"Olá, {st.session_state.user_nome}!")
        df_m = carregar_mensagens()
        minhas = df_m[df_m['cpf_destino'] == st.session_state.user_cpf]
        for _, r in minhas.iloc[::-1].iterrows():
            with st.chat_message("assistant"):
                st.write(f"📅 {r['data_envio']}\n\n{r['mensagem']}")
        
        # Marcar como lido
        df_m.loc[(df_m['cpf_destino'] == st.session_state.user_cpf) & (df_m['lido'] == "Não"), 'lido'] = "Sim"
        df_m.to_csv(FILE_MENSAGENS, index=False)

    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()