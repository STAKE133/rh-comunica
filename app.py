import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import streamlit.components.v1 as components

# Configuração da página
st.set_page_config(page_title="RH Comunica", layout="centered", initial_sidebar_state="collapsed")

# --- ARQUIVOS DE DADOS ---
FILE_MENSAGENS = "MENSAGENS_ENVIADAS.csv"
FILE_COLABS = "DADOS_COLABORADORES.xlsx"

# Inicializa arquivos
if not os.path.exists(FILE_MENSAGENS):
    pd.DataFrame(columns=["id", "data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"]).to_csv(FILE_MENSAGENS, index=False)

# --- FUNÇÕES DE APOIO ---
def limpar_cpf(cpf):
    s = str(cpf).split('.')[0]
    s = re.sub(r'\D', '', s)
    return s.zfill(11)

@st.cache_data(ttl=60)
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
    try:
        df = pd.read_csv(FILE_MENSAGENS, dtype=str).fillna("")
        # Converte data_envio para datetime real para cálculos
        df['dt_obj'] = pd.to_datetime(df['data_envio'], format="%d/%m/%Y %H:%M", errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=["id", "data_envio", "cpf_destino", "nome_destino", "mensagem", "lido", "data_leitura"])

# --- TRUQUE DE LOGIN PERSISTENTE E SOM ---
# Injeta JS para salvar o CPF no navegador e tocar som
def injetar_js_funcionalidades():
    components.html("""
    <script>
    // 1. Manter Login (LocalStorage)
    const cpf_salvo = localStorage.getItem('rh_comunica_cpf');
    if (cpf_salvo && !window.parent.location.href.includes('logout')) {
        // O Streamlit não permite preencher o input direto via JS facilmente, 
        // mas avisa o usuário que ele pode clicar para auto-completar.
    }

    // 2. Função de Som de Notificação
    window.tocarSom = function() {
        var audio = new Audio('https://notificationsounds.com/storage/sounds/file-sounds-1150-pristine.mp3');
        audio.play();
        alert("📢 Nova Mensagem do RH!");
    }
    </script>
    """, height=0)

injetar_js_funcionalidades()

# --- INTERFACE ---
df_base = carregar_colaboradores()

if "logado" not in st.session_state:
    st.session_state.update({"logado": False, "user_cpf": "", "is_admin": False, "user_nome": ""})

# --- LOGIN ---
if not st.session_state.logado:
    st.title("📲 RH Comunica - Login")
    # Tenta sugerir o CPF se o usuário já logou antes (instrução visual)
    st.info("💡 Dica: Seu navegador pode salvar seu CPF para acesso rápido.")
    cpf_input = st.text_input("Digite seu CPF:")
    
    if st.button("Entrar", use_container_width=True):
        if cpf_input == "000":
            st.session_state.update({"logado": True, "is_admin": True})
            st.rerun()
            
        cpf_busca = limpar_cpf(cpf_input)
        if df_base is not None:
            user = df_base[df_base['CPF_LIMPO'] == cpf_busca]
            if not user.empty:
                st.session_state.update({"logado": True, "user_cpf": cpf_busca, "user_nome": str(user.iloc[0]['Nome'])})
                # Salva no navegador via JS
                components.html(f"<script>localStorage.setItem('rh_comunica_cpf', '{cpf_busca}');</script>", height=0)
                st.rerun()
            else: st.error("CPF não encontrado.")

else:
    # --- PAINEL RH (ADMIN) ---
    if st.session_state.is_admin:
        st.title("🛠️ Gestão RH")
        tab1, tab2, tab3 = st.tabs(["🚀 Enviar", "📊 Relatório / Excluir", "⚙️ Base"])
        
        with tab1:
            if df_base is not None:
                modo = st.radio("Destinatários:", ["Por Obra", "Lista Manual"], horizontal=True)
                cpfs_alvo = []
                if modo == "Por Obra":
                    opcoes_obra = sorted([str(x) for x in df_base['OBRA'].dropna().unique()])
                    obras = st.multiselect("Selecione as Obras:", options=opcoes_obra)
                    cpfs_alvo = df_base[df_base['OBRA'].astype(str).isin(obras)]['CPF_LIMPO'].tolist()
                else:
                    txt_area = st.text_area("Cole os CPFs:")
                    cpfs_alvo = [limpar_cpf(c) for c in re.findall(r'\d+', txt_area)]
                
                st.metric("Selecionados", len(cpfs_alvo))
                msg_txt = st.text_area("Mensagem:", height=100)
                if st.button("DISPARAR", use_container_width=True):
                    df_m = carregar_mensagens().drop(columns=['dt_obj'])
                    novas = []
                    for c in cpfs_alvo:
                        match = df_base[df_base['CPF_LIMPO'] == c]
                        nome = str(match.iloc[0]['Nome']) if not match.empty else "Novo"
                        novas.append({
                            "id": datetime.now().strftime("%Y%m%d%H%M%S") + c[-3:], # ID único
                            "data_envio": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "cpf_destino": c,
                            "nome_destino": nome,
                            "mensagem": msg_txt,
                            "lido": "Não",
                            "data_leitura": ""
                        })
                    pd.concat([df_m, pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_MENSAGENS, index=False)
                    st.success("Mensagens enviadas!")

        with tab2:
            st.subheader("Controle de Mensagens")
            df_report = carregar_mensagens()
            
            # Interface para EXCLUIR mensagens
            st.write("Selecione mensagens para apagar:")
            # Tabela editável para permitir exclusão
            df_report['Excluir'] = False
            editado = st.data_editor(
                df_report[['Excluir', 'data_envio', 'nome_destino', 'mensagem', 'lido', 'data_leitura', 'id']],
                column_config={"id": None}, # Esconde o ID
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("Confirmar Exclusão de Selecionados", type="primary"):
                ids_para_excluir = editado[editado['Excluir'] == True]['id'].tolist()
                df_final = df_report[~df_report['id'].isin(ids_para_excluir)].drop(columns=['dt_obj', 'Excluir'])
                df_final.to_csv(FILE_MENSAGENS, index=False)
                st.success("Mensagens removidas!")
                st.rerun()

        with tab3:
            new_file = st.file_uploader("Atualizar Excel", type="xlsx")
            if st.button("Substituir Base"):
                if new_file:
                    with open(FILE_COLABS, "wb") as f: f.write(new_file.getbuffer())
                    st.cache_data.clear()
                    st.rerun()

    # --- VISÃO COLABORADOR ---
    else:
        st.title(f"Olá, {str(st.session_state.user_nome).split()[0]}!")
        df_m = carregar_mensagens()
        
        # 1. Filtro de Expiração (48 horas)
        limite = datetime.now() - timedelta(hours=48)
        minhas = df_m[(df_m['cpf_destino'] == st.session_state.user_cpf) & (df_m['dt_obj'] >= limite)].copy()
        
        if not minhas.empty:
            # Verifica se há mensagens novas para tocar o som
            if "Não" in minhas['lido'].values:
                components.html("<script>tocarSom();</script>", height=0)
            
            for _, r in minhas.iloc[::-1].iterrows():
                with st.chat_message("assistant"):
                    st.write(f"📅 **{r['data_envio']}**")
                    st.markdown(r['mensagem'])
            
            # Marcar como lido
            df_total = pd.read_csv(FILE_MENSAGENS, dtype=str).fillna("")
            indices = df_total[(df_total['cpf_destino'] == st.session_state.user_cpf) & (df_total['lido'] == "Não")].index
            if len(indices) > 0:
                df_total.loc[indices, 'lido'] = "Sim"
                df_total.loc[indices, 'data_leitura'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                df_total.to_csv(FILE_MENSAGENS, index=False)
        else:
            st.info("Você não tem avisos pendentes (mensagens expiram após 48h).")

    if st.sidebar.button("Logoff / Sair"):
        st.session_state.logado = False
        st.rerun()
