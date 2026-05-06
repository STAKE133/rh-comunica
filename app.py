import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import streamlit.components.v1 as components

# 1. CONFIGURAÇÃO INICIAL DA PÁGINA
st.set_page_config(page_title="RH Comunica", layout="centered", initial_sidebar_state="collapsed")

# --- ARQUIVOS DE DADOS ---
FILE_MENSAGENS = "MENSAGENS_ENVIADAS.csv"
FILE_COLABS = "DADOS_COLABORADORES.xlsx"
COLUNAS_MSG = ["id", "data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"]

# 2. INICIALIZAÇÃO DE ARQUIVOS (Evita erros de colunas faltando)
def inicializar_arquivos():
    if not os.path.exists(FILE_MENSAGENS):
        pd.DataFrame(columns=COLUNAS_MSG).to_csv(FILE_MENSAGENS, index=False)
    else:
        try:
            df = pd.read_csv(FILE_MENSAGENS, dtype=str)
            mudou = False
            for col in COLUNAS_MSG:
                if col not in df.columns:
                    df[col] = "" if col != "id" else [datetime.now().strftime("%Y%m%d%H%M%S")+str(i) for i in range(len(df))]
                    mudou = True
            if mudou:
                df.to_csv(FILE_MENSAGENS, index=False)
        except:
            pd.DataFrame(columns=COLUNAS_MSG).to_csv(FILE_MENSAGENS, index=False)

inicializar_arquivos()

# 3. FUNÇÕES DE SUPORTE
def limpar_cpf(cpf):
    if pd.isna(cpf): return ""
    s = str(cpf).split('.')[0]
    s = re.sub(r'\D', '', s)
    return s.zfill(11)

@st.cache_data(ttl=30)
def carregar_colaboradores():
    if os.path.exists(FILE_COLABS):
        try:
            df = pd.read_excel(FILE_COLABS)
            df.columns = [c.strip() for c in df.columns]
            df = df.dropna(subset=['CPF'])
            df['CPF_LIMPO'] = df['CPF'].apply(limpar_cpf)
            return df
        except: return None
    return None

def carregar_mensagens():
    df = pd.read_csv(FILE_MENSAGENS, dtype=str).fillna("")
    if not df.empty:
        df['dt_obj'] = pd.to_datetime(df['data_envio'], format="%d/%m/%Y %H:%M", errors='coerce')
    else:
        df['dt_obj'] = pd.Series(dtype='datetime64[ns]')
    return df

# 4. CARREGAMENTO DA BASE (Definindo df_base logo no início para evitar NameError)
df_base = carregar_colaboradores()

# 5. JAVASCRIPT PARA SOM E LOGIN PERSISTENTE
components.html("""
<script>
window.parent.tocarAlerta = function() {
    var audio = new Audio('https://notificationsounds.com/storage/sounds/file-sounds-1150-pristine.mp3');
    audio.play();
}
// Tenta recuperar o CPF salvo
const salvo = localStorage.getItem('rh_cpf');
if (salvo && !window.parent.location.href.includes('sair')) {
    // Apenas uma dica visual, o preenchimento automático depende do navegador
}
</script>
""", height=0)

# --- LÓGICA DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.update({"logado": False, "user_cpf": "", "is_admin": False, "user_nome": ""})

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("📲 RH Comunica - Login")
    cpf_input = st.text_input("Digite seu CPF (apenas números):")
    
    if st.button("Entrar", use_container_width=True):
        if cpf_input == "000": # Acesso Admin
            st.session_state.update({"logado": True, "is_admin": True})
            st.rerun()
            
        cpf_busca = limpar_cpf(cpf_input)
        if df_base is not None:
            user = df_base[df_base['CPF_LIMPO'] == cpf_busca]
            if not user.empty:
                nome_colab = str(user.iloc[0]['Nome'])
                st.session_state.update({"logado": True, "user_cpf": cpf_busca, "user_nome": nome_colab})
                components.html(f"<script>localStorage.setItem('rh_cpf', '{cpf_busca}');</script>", height=0)
                st.rerun()
            else: st.error("CPF não encontrado.")
        else: st.warning("Aguardando o RH subir a base de dados.")

# --- TELA LOGADO ---
else:
    if st.sidebar.button("Logoff / Sair"):
        components.html("<script>localStorage.removeItem('rh_cpf');</script>", height=0)
        st.session_state.logado = False
        st.rerun()

    # --- VISÃO ADMIN ---
    if st.session_state.is_admin:
        st.title("🛠️ Gestão RH")
        t1, t2, t3 = st.tabs(["🚀 Enviar", "📊 Relatório / Excluir", "⚙️ Base"])
        
        with t1:
            if df_base is not None:
                modo = st.radio("Destinatários:", ["Por Obra", "Lista Manual"], horizontal=True)
                cpfs_alvo = []
                if modo == "Por Obra":
                    opcoes_obra = sorted([str(x) for x in df_base['OBRA'].dropna().unique()])
                    obras = st.multiselect("Selecione as Obras:", options=opcoes_obra)
                    cpfs_alvo = df_base[df_base['OBRA'].astype(str).isin(obras)]['CPF_LIMPO'].tolist()
                else:
                    txt = st.text_area("Cole os CPFs:")
                    cpfs_alvo = [limpar_cpf(c) for c in re.findall(r'\d+', txt)]
                
                st.metric("Total selecionado", len(cpfs_alvo))
                msg_txt = st.text_area("Mensagem:", height=100)
                if st.button("DISPARAR", use_container_width=True):
                    if cpfs_alvo and msg_txt:
                        df_m = pd.read_csv(FILE_MENSAGENS, dtype=str)
                        novas = []
                        for c in cpfs_alvo:
                            match = df_base[df_base['CPF_LIMPO'] == c]
                            nome = str(match.iloc[0]['Nome']) if not match.empty else "Novo"
                            novas.append({
                                "id": datetime.now().strftime("%Y%m%d%H%M%S") + c[-3:],
                                "data_envio": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "cpf_destino": c, "nome_destino": nome, "mensagem": msg_txt, "lido": "Não", "data_leitura": ""
                            })
                        pd.concat([df_m, pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_MENSAGENS, index=False)
                        st.success("Enviado com sucesso!")
            else: st.error("Suba a planilha na aba 'Base'.")

        with t2:
            st.subheader("Histórico e Exclusão")
            df_rep = carregar_mensagens()
            if not df_rep.empty:
                df_rep['Excluir'] = False
                colunas_view = ['Excluir', 'data_envio', 'nome_destino', 'mensagem', 'lido', 'data_leitura', 'id']
                # Garante que as colunas existam antes de mostrar
                colunas_existentes = [c for c in colunas_view if c in df_rep.columns]
                editado = st.data_editor(df_rep[colunas_existentes], hide_index=True, use_container_width=True)
                
                if st.button("Apagar Selecionados", type="primary"):
                    ids_apagar = editado[editado['Excluir'] == True]['id'].tolist()
                    df_final = df_rep[~df_rep['id'].isin(ids_apagar)].drop(columns=['dt_obj', 'Excluir'], errors='ignore')
                    df_final.to_csv(FILE_MENSAGENS, index=False)
                    st.rerun()
            else: st.write("Nenhuma mensagem enviada.")

        with t3:
            up = st.file_uploader("Subir novo Excel", type="xlsx")
            if st.button("Atualizar Base"):
                if up:
                    with open(FILE_COLABS, "wb") as f: f.write(up.getbuffer())
                    st.cache_data.clear()
                    st.rerun()

    # --- VISÃO COLABORADOR ---
    else:
        st.title(f"Olá, {st.session_state.user_nome.split()[0]}!")
        df_m = carregar_mensagens()
        
        # Filtro de 48 horas (Mensagens recentes)
        limite = datetime.now() - timedelta(hours=48)
        minhas = df_m[(df_m['cpf_destino'] == st.session_state.user_cpf) & (df_m['dt_obj'] >= limite)].copy()
        
        if not minhas.empty:
            # Som se houver novas
            if "Não" in minhas['lido'].values:
                st.warning("🔔 Você tem uma nova mensagem!")
                components.html("<script>window.parent.tocarAlerta();</script>", height=0)
            
            for _, r in minhas.iloc[::-1].iterrows():
                with st.chat_message("assistant"):
                    st.write(f"📅 **{r['data_envio']}**")
                    st.markdown(r['mensagem'])
            
            # Marcar como lido
            df_csv = pd.read_csv(FILE_MENSAGENS, dtype=str).fillna("")
            idx = df_csv[(df_csv['cpf_destino'] == st.session_state.user_cpf) & (df_csv['lido'] == "Não")].index
            if len(idx) > 0:
                df_csv.loc[idx, 'lido'] = "Sim"
                df_csv.loc[idx, 'data_leitura'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                df_csv.to_csv(FILE_MENSAGENS, index=False)
        else:
            st.info("Você não tem comunicados novos (avisos expiram em 48h).")
