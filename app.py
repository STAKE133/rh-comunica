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

# Inicializa o arquivo de mensagens se não existir
if not os.path.exists(FILE_MENSAGENS):
    pd.DataFrame(columns=["data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"]).to_csv(FILE_MENSAGENS, index=False)

# --- FUNÇÕES DE LIMPEZA E LOGÍSTICA ---
def limpar_cpf(cpf):
    """Garante que o CPF tenha 11 dígitos numéricos, tratando zeros à esquerda."""
    s = str(cpf).split('.')[0] # Remove .0 se o Excel ler como float
    s = re.sub(r'\D', '', s)   # Remove qualquer caractere não numérico
    return s.zfill(11)         # Preenche com zeros à esquerda até ter 11 dígitos

@st.cache_data(ttl=60)
def carregar_colaboradores():
    if os.path.exists(FILE_COLABS):
        try:
            df = pd.read_excel(FILE_COLABS)
            # Normaliza os nomes das colunas (tira espaços extras)
            df.columns = [c.strip() for c in df.columns]
            df['CPF_LIMPO'] = df['CPF'].apply(limpar_cpf)
            return df
        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")
            return None
    return None

def carregar_mensagens():
    return pd.read_csv(FILE_MENSAGENS, dtype={"cpf_destino": str})

# --- INTERFACE PRINCIPAL ---
df_base = carregar_colaboradores()

if "logado" not in st.session_state:
    st.session_state.update({"logado": False, "user_cpf": "", "is_admin": False, "user_nome": ""})

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("📲 RH Comunica - Login")
    st.write("Acesse com seu CPF para ver seus comunicados.")
    
    cpf_input = st.text_input("Digite seu CPF (apenas números):", placeholder="Ex: 050...")
    
    if st.button("Entrar no Sistema", use_container_width=True):
        # CPF "000" continua sendo a porta de entrada do Admin
        if cpf_input == "000":
            st.session_state.update({"logado": True, "is_admin": True})
            st.rerun()
            
        cpf_busca = limpar_cpf(cpf_input)
        
        if df_base is not None:
            user = df_base[df_base['CPF_LIMPO'] == cpf_busca]
            if not user.empty:
                nome_completo = user.iloc[0]['Nome']
                st.session_state.update({
                    "logado": True, 
                    "user_cpf": cpf_busca, 
                    "user_nome": nome_completo
                })
                st.rerun()
            else:
                st.error("CPF não encontrado na base ativa do RH.")
        else:
            st.warning("O RH ainda não subiu a base de dados. Tente novamente mais tarde.")

# --- SISTEMA LOGADO ---
else:
    # BOTÃO SAIR (Fica no topo para facilitar no celular)
    if st.sidebar.button("Logoff / Sair"):
        st.session_state.logado = False
        st.rerun()

    if st.session_state.is_admin:
        st.title("🛠️ Painel Administrativo")
        tab1, tab2, tab3 = st.tabs(["🚀 Enviar Mensagens", "📊 Relatório de Leitura", "⚙️ Base de Dados"])
        
        with tab3:
            st.subheader("Atualizar Colaboradores")
            st.info("Sempre que exportar uma nova lista do seu sistema, suba o arquivo .xlsx aqui.")
            new_file = st.file_uploader("Nova Planilha Excel", type="xlsx")
            if st.button("Substituir Base Atual"):
                if new_file:
                    with open(FILE_COLABS, "wb") as f:
                        f.write(new_file.getbuffer())
                    st.cache_data.clear()
                    st.success("Base de dados atualizada com sucesso!")
                    st.rerun()

        with tab1:
            modo = st.radio("Destinatários:", ["Por Obra", "Lista Manual (Colar)"], horizontal=True)
            cpfs_alvo = []
            
            if df_base is not None:
                if modo == "Por Obra":
                    obras = st.multiselect("Selecione as Obras:", options=sorted(df_base['OBRA'].unique()))
                    cpfs_alvo = df_base[df_base['OBRA'].isin(obras)]['CPF_LIMPO'].tolist()
                else:
                    txt_area = st.text_area("Cole os CPFs aqui (separados por vírgula, espaço ou linha):")
                    # Extrai qualquer sequência de números e garante os 11 dígitos
                    raw_cpfs = re.findall(r'\d+', txt_area)
                    cpfs_alvo = [c.zfill(11) for c in raw_cpfs if len(c) <= 11]
                
                st.metric("Total de Alvos", len(cpfs_alvo))
                msg_txt = st.text_area("Escreva o comunicado:", height=200)
                
                if st.button("DISPARAR COMUNICADO", use_container_width=True):
                    if cpfs_alvo and msg_txt:
                        df_m = carregar_mensagens()
                        novas = []
                        for c in cpfs_alvo:
                            # Busca o nome na base para o relatório
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
                        
                        df_m = pd.concat([df_m, pd.DataFrame(novas)], ignore_index=True)
                        df_m.to_csv(FILE_MENSAGENS, index=False)
                        st.success(f"Mensagem enviada para {len(cpfs_alvo)} pessoas!")
                    else:
                        st.error("Preencha os destinatários e a mensagem.")
            else:
                st.error("Suba a planilha de colaboradores primeiro na aba 'Base de Dados'.")

        with tab2:
            st.subheader("Histórico de Envios")
            df_rep = carregar_mensagens()
            if not df_rep.empty:
                st.dataframe(df_rep.sort_values(by="data_envio", ascending=False), use_container_width=True)
            else:
                st.write("Nenhuma mensagem enviada ainda.")

    # --- VISÃO DO COLABORADOR ---
    else:
        primeiro_nome = st.session_state.user_nome.split()[0]
        st.title(f"Olá, {primeiro_nome}!")
        
        df_m = carregar_mensagens()
        minhas = df_m[df_m['cpf_destino'] == st.session_state.user_cpf].copy()
        
        if not minhas.empty:
            st.write("Confira abaixo seus comunicados recentes:")
            # Mostra as mensagens da mais nova para a mais antiga
            for _, r in minhas.iloc[::-1].iterrows():
                with st.chat_message("assistant"):
                    st.write(f"📅 **{r['data_envio']}**")
                    st.markdown(r['mensagem'])
            
            # Marca como lido no CSV
            idx_nao_lidas = df_m[(df_m['cpf_destino'] == st.session_state.user_cpf) & (df_m['lido'] == "Não")].index
            if not idx_nao_lidas.empty:
                df_m.loc[idx_nao_lidas, 'lido'] = "Sim"
                df_m.loc[idx_nao_lidas, 'data_leitura'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                df_m.to_csv(FILE_MENSAGENS, index=False)
        else:
            st.info("Você não tem comunicados pendentes no momento.")
