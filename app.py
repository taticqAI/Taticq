import streamlit as st
import pandas as pd
import google.generativeai as genai
import sqlite3
import os
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fpdf import FPDF
from datetime import datetime
from collections import defaultdict
import csv

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Taticq - Análise Tática Inteligente",
    page_icon="⚽",
    layout="wide"
)

# --- OCULTAR ELEMENTOS NATIVOS E DO GITHUB DA INTERFACE ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÃO DA API DO GEMINI ---
API_KEY_GEMINI = "AQ.Ab8RN6KjOzNnEovrneJGMP_kP6Lasz-yWg1NB5F4W4liJVwPYQ"

if API_KEY_GEMINI:
    genai.configure(api_key=API_KEY_GEMINI)
    modelo = genai.GenerativeModel('gemini-3.5-flash')
else:
    modelo = None

# --- CÓDIGO DE CONVITE MESTRE PARA O BETA FECHADO ---
CODIGO_CONVITE_MESTRE = "TATICQ2026"

# --- FUNÇÃO DE HASH PARA SEGURANÇA DE SENHAS ---
def fazer_hash_senha(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- CONFIGURAÇÃO DA BASE DE DADOS (SQLite) ---
def init_db():
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT,
            email TEXT,
            creditos INTEGER DEFAULT 2,
            plano TEXT DEFAULT 'Gratuito (Trial)'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            clube TEXT,
            escalao TEXT,
            foco TEXT,
            data_criacao TEXT,
            conteudo TEXT
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN email TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN plano TEXT DEFAULT "Gratuito (Trial)"')
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

init_db()

def verificar_utilizador(username, password):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    senha_hash = fazer_hash_senha(password)
    cursor.execute('SELECT creditos, plano FROM usuarios WHERE username = ? AND password = ?', (username, senha_hash))
    res = cursor.fetchone()
    conn.close()
    return res if res else None

def criar_utilizador(username, password, email):
    try:
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        senha_hash = fazer_hash_senha(password)
        cursor.execute('INSERT INTO usuarios (username, password, email, creditos, plano) VALUES (?, ?, ?, 2, ?)', (username, senha_hash, email, 'Gratuito (Trial)'))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def atualizar_dados_utilizador(username, novos_creditos, novo_plano):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET creditos = ?, plano = ? WHERE username = ?', (novos_creditos, novo_plano, username))
    conn.commit()
    conn.close()

def atualizar_senha_utilizador(username, nova_senha):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    senha_hash = fazer_hash_senha(nova_senha)
    cursor.execute('UPDATE usuarios SET password = ? WHERE username = ?', (senha_hash, username))
    conn.commit()
    conn.close()

def obter_dados_utilizador(username):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT creditos, plano FROM usuarios WHERE username = ?', (username,))
    res = cursor.fetchone()
    conn.close()
    return res if res else (0, 'Desconhecido')

def obter_email_por_usuario(username):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM usuarios WHERE username = ?', (username,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def guardar_historico(username, clube, escalao, foco, conteudo):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute('''
        INSERT INTO historico_relatorios (username, clube, escalao, foco, data_criacao, conteudo)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (username, clube, escalao, foco, data_atual, conteudo))
    conn.commit()
    conn.close()

def obter_historico(username):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, clube, escalao, foco, data_criacao, conteudo FROM historico_relatorios WHERE username = ? ORDER BY id DESC', (username,))
    res = cursor.fetchall()
    conn.close()
    return res

def limpar_historico_utilizador(username):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM historico_relatorios WHERE username = ?', (username,))
    conn.commit()
    conn.close()

# --- FUNÇÃO PARA GERAR PDF PROFISSIONAL E LIMPO ---
def gerar_pdf_relatorio(texto_relatorio, clube, analista, categoria):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 15)
    pdf.set_text_color(20, 40, 80)
    pdf.cell(0, 10, "TATICQ - RELATORIO DE INTELIGENCIA TATICA", 0, 1, 'C')
    
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Clube: {clube} | Escalao: {categoria} | Analista: {analista}", 0, 1, 'C')
    pdf.ln(4)
    
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)
    
    texto_limpo = (
        texto_relatorio
        .replace("$$", "")
        .replace("$", "")
        .replace("**", "")
        .replace("###", "")
        .replace("##", "")
        .replace("#", "")
        .replace("---", "")
        .replace("? ", "- ")
    )
    
    paragrafos = texto_limpo.split("\n")
    
    for linha in paragrafos:
        linha_tratada = linha.encode('latin-1', 'replace').decode('latin-1')
        if any(sec in linha_tratada.upper() for sec in ["IDENTIFICACAO", "SUMARIO", "DIAGNOSTICO", "MATRIZ", "PLANO", "OBJETIVO", "ANALISE", "AVALIACAO", "GRAU", "AJUSTES"]):
            pdf.ln(4)
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(20, 40, 80)
            pdf.multi_cell(0, 6, linha_tratada)
            pdf.set_font("Arial", '', 10)
            pdf.set_text_color(60, 60, 60)
        else:
            pdf.set_font("Arial", '', 10)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5, linha_tratada)
            
    output = pdf.output(dest='S')
    if isinstance(output, str):
        return output.encode('latin1')
    return bytes(output)

# --- ESTADO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.username = ""

if 'ultimo_pdf' not in st.session_state:
    st.session_state.ultimo_pdf = None

# --- TELA DE LOGIN / REGISTO / RECUPERAÇÃO ---
if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=140)
            
        st.title("⚽ Taticq - Acesso Restrito")
        st.markdown("Plataforma de alta performance para inteligência e análise de desempenho no futebol.")
        
        aba_login, aba_registo, aba_recuperar = st.tabs(["🔑 Iniciar Sessão", "📝 Solicitar Acesso (Beta)", "🔄 Recuperar Senha"])
        
        with aba_login:
            user_input = st.text_input("Usuário", key="login_user")
            pass_input = st.text_input("Senha", type="password", key="login_pass")
            if st.button("Entrar", key="btn_login_submit"):
                user_limpo = user_input.strip()
                dados = verificar_utilizador(user_limpo, pass_input)
                if dados is not None:
                    st.session_state.logado = True
                    st.session_state.username = user_limpo
                    st.success("Login efetuado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
                    
        with aba_registo:
            st.info("🔒 **Beta Fechado:** O registo requer um código de convite corporativo.")
            new_user = st.text_input("Nome de Usuário (Sem espaços)", key="reg_user")
            new_email = st.text_input("E-mail Corporativo", key="reg_email")
            new_pass = st.text_input("Palavra-passe", type="password", key="reg_pass")
            convite_input = st.text_input("Código de Convite", type="password", key="reg_convite")
            
            if st.button("Registar Conta", key="btn_reg_submit"):
                user_limpo = new_user.strip()
                if " " in user_limpo:
                    st.warning("⚠️ O nome de utilizador não pode conter espaços em branco.")
                elif not user_limpo or not new_pass or not new_email:
                    st.warning("Preencha todos os campos obrigatórios.")
                elif convite_input != CODIGO_CONVITE_MESTRE:
                    st.error("❌ Código de convite inválido ou restrito. Contacte o administrador.")
                elif len(new_pass) < 6:
                    st.warning("A palavra-passe deve ter pelo menos 6 caracteres.")
                elif criar_utilizador(user_limpo, new_pass, new_email.strip()):
                    st.success("Conta criada com sucesso! Faça login na primeira aba.")
                else:
                    st.error("Nome de usuário já existe. Escolha outro.")

        with aba_recuperar:
            st.markdown("Esqueceu-se da palavra-passe? Insira o seu utilizador para gerar uma nova chave temporária.")
            user_rec = st.text_input("Nome de Usuário", key="rec_user_input")
            if st.button("Gerar Nova Senha Temporária", key="btn_rec_submit"):
                user_limpo_rec = user_rec.strip()
                if not user_limpo_rec:
                    st.warning("Insira o nome de utilizador.")
                else:
                    email_cadastrado = obter_email_por_usuario(user_limpo_rec)
                    if not email_cadastrado and user_limpo_rec.lower() != "admin":
                        st.error("Utilizador não encontrado na base de dados.")
                    else:
                        nova_temp = f"Taticq{random.randint(1000, 9999)}"
                        atualizar_senha_utilizador(user_limpo_rec, nova_temp)
                        st.success(f"✅ Nova palavra-passe temporária gerada com sucesso para o utilizador `{user_limpo_rec}`:")
                        st.code(nova_temp, language="text")
                        st.info("Guarde esta senha temporária e faça login na primeira aba para depois a alterar nas definições.")
    st.stop()

# --- APLICAÇÃO PRINCIPAL ---
creditos_atuais, plano_atual = obter_dados_utilizador(st.session_state.username)
historico_usuario = obter_historico(st.session_state.username)

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=100)

st.sidebar.markdown(f"👤 **Utilizador:** `{st.session_state.username}`")
st.sidebar.markdown(f"📦 **Plano Ativo:** `{plano_atual}`")
st.sidebar.markdown(f"💳 **Créditos Disponíveis:** `{creditos_atuais}` 📋")
st.sidebar.markdown(f"📊 **Relatórios Gerados:** `{len(historico_usuario)}`")

if creditos_atuais <= 1:
    st.sidebar.warning("⚠️ **Créditos baixos!** Recarregue na Loja para continuar.")

if st.sidebar.button("🚪 Terminar Sessão"):
    st.session_state.logado = False
    st.session_state.username = ""
    st.session_state.ultimo_pdf = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Painel do Analista & Desempenho")

tipo_analise_contexto = st.sidebar.selectbox(
    "Contexto da Análise",
    ["🎬 Partida Oficial / Adversário", "📋 Sessão de Treino / Exercício"]
)

clube = st.sidebar.text_input("Nome do Clube", "Operário", key="input_clube")
analista = st.sidebar.text_input("Nome do Analista", "Pedro", key="input_analista")

categoria = st.sidebar.selectbox(
    "Categoria / Escalão",
    ["Profissional", "Sub-20", "Sub-17", "Sub-15", "Sub-13"],
    key="select_cat"
)

if "Partida" in tipo_analise_contexto:
    foco_tatico = st.sidebar.selectbox(
        "Foco da Análise de Jogo",
        [
            "Ação Ofensiva (Organização, Construção e Finalização)",
            "Ação Defensiva (Bloco, Pressão e Recuperação)",
            "Transição Ofensiva (Contra-ataque e Aceleração)",
            "Transição Defensiva (Reorganização e Retirada de Espaço)",
            "Bolas Paradas (Pontapés de canto, livres e laterais)",
            "Análise Geral Completa"
        ],
        key="select_foco_jogo"
    )
else:
    foco_tatico = st.sidebar.selectbox(
        "Foco da Sessão de Treino",
        [
            "Intensidade e Ritmo de Execução do Exercício",
            "Comportamento Defensivo em Transição e Bloco",
            "Dinâmica de Circulação e Construção Ofensiva",
            "Ajustes de Posicionamento e Linhas de Passe",
            "Competitividade e Duelos em Espaço Reduzido"
        ],
        key="select_foco_treino"
    )

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 Configuração de Uniformes")
uniforme_equipa = st.sidebar.text_input("Uniforme da Equipa", "Listas verticais pretas e brancas", key="input_kit_equipa")
uniforme_adversario = st.sidebar.text_input("Uniforme Adversário", "Azul-celeste liso", key="input_kit_adv")

st.sidebar.markdown("---")

opcoes_navegacao = [
    "🎬 Carregar Jogo & Dados", 
    "📂 Histórico de Relatórios", 
    "💎 Planos & Assinaturas (SaaS)", 
    "🛒 Comprar Relatórios Avulsos",
    "⚙️ Definições & Perfil"
]

nav_sistema = st.sidebar.radio("Navegação do Sistema:", opcoes_navegacao, key="radio_navegacao")

# --- MENU 1: CARREGAR E ANALISAR JOGO ---
if nav_sistema == "🎬 Carregar Jogo & Dados":
    if "Partida" in tipo_analise_contexto:
        st.title("⚽ Taticq - Análise de Partida / Adversário")
        st.markdown("Carregue o vídeo da partida e opcionalmente os dados de telemetria/GPS estruturados.")
        label_video = "1. Carregar vídeo da partida (`.mp4`, `.mov`)"
        nome_botao = "Gerar Relatório Tático Avançado"
    else:
        st.title("📋 Taticq - Análise de Sessão de Treino")
        st.markdown("Carregue o vídeo do exercício ou sessão de treino para auditoria tática e comportamental.")
        label_video = "1. Carregar vídeo do treino/exercício (`.mp4`, `.mov`)"
        nome_botao = "Gerar Auditoria da Sessão de Treino"

    st.markdown(f"**Analista:** {analista} | **Clube:** {clube} ({categoria})")

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        uploaded_video = st.file_uploader(label_video, type=["mp4", "mov"])
    with col_up2:
        uploaded_csv = st.file_uploader("2. Carregar base de dados de tracking / GPS estruturado (`.csv`)", type="csv")

    if uploaded_video is not None:
        st.success("✅ Vídeo carregado com sucesso!")
        st.video(uploaded_video)

    df_texto = ""
    try:
        if uploaded_csv is not None:
            df_temp = pd.read_csv(uploaded_csv)
        else:
            df_temp = pd.read_csv("dados_jogada.csv")
            
        total_linhas = len(df_temp)
        colunas_disponiveis = ", ".join(df_temp.columns.tolist())
        
        erros_registados = ""
        if "Erro_Cometido" in df_temp.columns:
            erros_df = df_temp[df_temp["Erro_Cometido"] != "Nenhum"]
            erros_registados = f"- Total de erros e desvios táticos catalogados: {len(erros_df)}\n- Amostra de motivos de erro: {erros_df['Motivo_Erro'].head(5).tolist() if not erros_df.empty else 'Nenhum erro crítico'}"

        df_texto = f"""
        DADOS ESTRUTURADOS DE TRACKING E TELEMETRIA DA PARTIDA:
        - Dimensão da base de dados: {total_linhas} registos táticos analisados.
        - Colunas de rastreio disponíveis: {colunas_disponiveis}
        {erros_registados}
        - Amostra completa dos dados estruturados por quadro/minuto:
        {df_temp.to_string()}
        """
        if uploaded_csv is not None:
            st.success(f"✅ Base de dados de tracking integrada com sucesso ({total_linhas} registos detetados)!")
        else:
            st.info(f"ℹ️ A usar base de dados padrão (`dados_jogada.csv`) com {total_linhas} registos.")
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro de dados: {e}")
        df_texto = "Erro na leitura dos dados. O sistema focar-se-á na leitura posicional."

    st.markdown("---")

    if st.button(nome_botao):
        if creditos_atuais <= 0:
            st.error("❌ Créditos esgotados! Redirecionando para a loja de relatórios...")
            st.rerun()
        elif not modelo:
            st.error("❌ Chave API Gemini não configurada.")
        else:
            spinner_texto = "🤖 A processar motor avançado de IA tática..." if "Partida" in tipo_analise_contexto else "🤖 A auditar a sessão de treino com matriz metodológica..."
            with st.spinner(spinner_texto):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais - 1, plano_atual)
                
                if "Partida" in tipo_analise_contexto:
                    prompt_analista = f"""
                    [SISTEMA: ENGENHARIA DE DESEMPENHO E SCOUTING PROFISSIONAL]
                    Atua como um Coordenador de Análise de Desempenho e Treinador UEFA Pro com experiência em grandes clubes internacionais.
                    O teu objetivo é gerar um relatório tático cirúrgico, analítico e de alto rendimento para a equipa '{clube}', escalão '{categoria}', solicitado pelo analista '{analista}'.

                    CONTEXTO E FOCO DA ANÁLISE: '{foco_tatico}'
                    IDENTIFICAÇÃO VISUAL:
                    - Nossa Equipa: {uniforme_equipa}
                    - Adversário: {uniforme_adversario}

                    DADOS ESTRUTURADOS DE TRACKING / TELEMETRIA / VÍDEO:
                    {df_texto}

                    DIRETRIZES TÉCNICAS OBRIGATÓRIAS:
                    1. **Raciocínio Baseado em Posições e Funções:** Analisa o comportamento coletivo e individual cruzando rigorosamente os dados de coordenadas, velocidades e desvios táticos fornecidos na tabela CSV.
                    2. **Causa-Raiz Profunda:** Explica o vetor do erro tático com precisão científica e de campo.
                    3. **Terminologia de Campo Avançada:** Utiliza rigor técnico (ex: pressão pós-perda, compactação vertical, espaço entrelinhas).

                    ESTRUTURA O RELATÓRIO EXATAMENTE EM 5 SECÇÕES PROFISSIONAIS:
                    1. IDENTIFICAÇÃO VISUAL DE EQUIPAMENTOS E REFERÊNCIAS
                    2. SUMÁRIO EXECUTIVO E DINÂMICA COLETIVA
                    3. DIAGNÓSTICO COMPORTAMENTAL E CAUSA-RAIZ POR SETOR/ATLETA
                    4. MATRIZ DE RISCOS ESTRUTURAIS E PONTOS FORTES
                    5. PLANO METODOLÓGICO E EXERCÍCIOS PRÁTICOS PARA O TREINO
                    """
                else:
                    prompt_analista = f"""
                    [SISTEMA: AUDITORIA METODOLÓGICA DE TREINO]
                    Atua como um Treinador Principal e Diretor Metodológico de Alto Rendimento.
                    Preparas uma auditoria tática e física detalhada de uma **Sessão de Treino** para a equipa '{clube}', escalão '{categoria}', elaborada por '{analista}'.

                    FOCO DA SESSÃO: '{foco_tatico}'
                    EQUIPAMENTO / CORES: {uniforme_equipa}
                    DADOS DA SESSÃO / GPS / TELEMETRIA: {df_texto}

                    DIRETRIZES TÉCNICAS OBRIGATÓRIAS:
                    1. **Auditoria de Carga e Intensidade:** Avalia se o ritmo e a densidade competitiva do exercício atingiram o objetivo pretendido cruzando com as velocidades e dados de telemetria.
                    2. **Transferência para o Jogo:** Analisa de que forma os comportamentos praticados no treino resolvem as debilidades da equipa.

                    ESTRUTURA A AUDITORIA EXATAMENTE EM 5 SECÇÕES:
                    1. OBJETIVO TÁTICO E ALINHAMENTO DA SESSÃO
                    2. ANÁLISE DE INTENSIDADE, RITMO E DENSIDADE DO EXERCÍCIO
                    3. AVALIAÇÃO COMPORTAMENTAL (EXECUÇÃO TÉCNICO-TÁTICA)
                    4. GRAU DE ABSORÇÃO DO MODELO DE JOGO
                    5. AJUSTES METODOLÓGICOS E PROGRESSÃO PARA O PRÓXIMO MICROCICLO
                    """
                
                try:
                    resposta = modelo.generate_content(prompt_analista)
                    texto_completo = resposta.text
                    
                    st.markdown("### 📋 Relatório de Inteligência Gerado")
                    st.success(f"Relatório gerado com sucesso! Restam {creditos_atuais - 1} créditos.")
                    
                    guardar_historico(st.session_state.username, clube, categoria, f"[{tipo_analise_contexto[:7]}] {foco_tatico}", texto_completo)
                    st.session_state.ultimo_pdf = gerar_pdf_relatorio(texto_completo, clube, analista, categoria)
                    
                    if plano_atual in ['Clube Profissional', 'Clube de Elite']:
                        st.success(f"👑 **{plano_atual} Ativo:** Acesso total a 100% do relatório detalhado e PDF!")
                        st.markdown(texto_completo)
                    elif plano_atual == 'Analista Solo':
                        st.info("⭐ **Analista Solo Ativo:** Visualizando até à 3ª parte.")
                        partes = texto_completo.split("3.")
                        st.markdown(partes[0])
                    else:
                        st.warning("🔒 **Amostra Limitada (Plano Gratuito / Trial):** Faça upgrade para desbloquear o relatório completo! 🚀")
                        partes = texto_completo.split("2.")
                        st.markdown(partes[0])
                        
                except Exception as e:
                    st.error(f"Erro ao comunicar com a IA: {e}")

    if st.session_state.ultimo_pdf is not None:
        st.markdown("---")
        st.download_button(
            label="📄 Descarregar Relatório Oficial em PDF",
            data=st.session_state.ultimo_pdf,
            file_name=f"Relatorio_Tatico_{clube.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

# --- MENU 2: HISTÓRICO COM FILTROS ---
elif nav_sistema == "📂 Histórico de Relatórios":
    st.title("📂 Histórico de Relatórios")
    
    col_hist1, col_hist2 = st.columns([3, 1])
    with col_hist2:
        if st.button("🗑️ Limpar Histórico"):
            limpar_historico_utilizador(st.session_state.username)
            st.success("Histórico limpo com sucesso!")
            st.rerun()

    pesquisa_termo = st.text_input("🔍 Pesquisar no histórico por clube ou foco tático:")

    historico = obter_historico(st.session_state.username)
    if not historico:
        st.info("Ainda não gerou nenhum relatório.")
    else:
        if pesquisa_termo:
            historico = [h for h in historico if pesquisa_termo.lower() in h[1].lower() or pesquisa_termo.lower() in h[3].lower()]
            
        if not historico:
            st.warning("Nenhum relatório encontrado com esse termo de pesquisa.")
        else:
            for item in historico:
                id_rel, clube_hist, escalao_hist, foco_hist, data_hist, conteudo_hist = item
                with st.expander(f"⚽ {clube_hist} ({escalao_hist}) — {foco_hist} [{data_hist}]"):
                    st.markdown(conteudo_hist)

# --- MENU 3: PLANOS E ASSINATURAS (SaaS) ---
elif nav_sistema == "💎 Planos & Assinaturas (SaaS)":
    st.title("💎 Planos & Assinaturas - Taticq")
    st.markdown("Escolha o plano ideal para escalar a análise de desempenho com máxima rentabilidade e proteção de custos.")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container():
            st.markdown("### Analista Solo")
            st.markdown("### R$ 197,00 `/mês`")
            st.markdown("Ideal para analistas independentes e formação.")
            st.markdown("---")
            st.markdown("✅ **8 Créditos mensais**")
            st.markdown("🔒 Amostra Parcial / Intermédia")
            st.markdown("✅ Suporte por e-mail")
            if st.button("Assinar Analista Solo", key="btn_solo_plan"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 8, "Analista Solo")
                st.balloons()
                st.success("🎉 Plano Analista Solo ativado com sucesso! +8 créditos adicionados.")
                st.rerun()
            
    with col2:
        with st.container():
            st.markdown("### Clube Profissional ⭐")
            st.markdown("### R$ 497,00 `/mês`")
            st.markdown("O motor de lucro para equipas profissionais.")
            st.markdown("---")
            st.markdown("✅ **25 Créditos mensais**")
            st.markdown("🔓 **Acesso Total 100% + PDF**")
            st.markdown("✅ Suporte Prioritário")
            if st.button("Assinar Profissional", key="btn_profissional_plan"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 25, "Clube Profissional")
                st.balloons()
                st.success("🎉 Plano Clube Profissional ativado com sucesso! +25 créditos adicionados.")
                st.rerun()
            
    with col3:
        with st.container():
            st.markdown("### Clube de Elite 👑")
            st.markdown("### R$ 997,00 `/mês`")
            st.markdown("Para clubes da elite e scouting avançado.")
            st.markdown("---")
            st.markdown("✅ **70 Créditos mensais**")
            st.markdown("🔓 **Acesso Total Ilimitado + PDF**")
            st.markdown("✅ Suporte Dedicado 24h")
            if st.button("Assinar Clube de Elite", key="btn_elite_plan"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 70, "Clube de Elite")
                st.balloons()
                st.success("🎉 Plano Clube de Elite ativado com sucesso! +70 créditos adicionados.")
                st.rerun()

# --- MENU 4: LOJA DE RELATÓRIOS (PAY-PER-USE) ---
elif nav_sistema == "🛒 Comprar Relatórios Avulsos":
    st.title("🛒 Loja de Relatórios Avulsos (Pay-Per-Use)")
    st.markdown("Precisa de créditos extra ou análises pontuais sem compromisso mensal? Compre pacotes com entrega imediata via Pix.")
    st.markdown("---")
    
    col_loja1, col_loja2, col_loja3 = st.columns(3)
    
    with col_loja1:
        with st.container():
            st.markdown("### Pacote Básico")
            st.markdown("**5 Relatórios**")
            st.markdown("### R$ 79,90")
            st.markdown("---")
            if st.button("Comprar 5 Relatórios", key="comprar_pacote_basico"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 5, plano_atual)
                st.success("🎉 Pagamento Pix aprovado! +5 créditos adicionados à sua conta.")
                st.rerun()
            
    with col_loja2:
        with st.container():
            st.markdown("### Pacote Standard")
            st.markdown("**15 Relatórios**")
            st.markdown("### R$ 197,00")
            st.markdown("---")
            if st.button("Comprar 15 Relatórios", key="comprar_pacote_standard"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 15, plano_atual)
                st.success("🎉 Pagamento Pix aprovado! +15 créditos adicionados à sua conta.")
                st.rerun()
            
    with col_loja3:
        with st.container():
            st.markdown("### Pacote Master")
            st.markdown("**40 Relatórios**")
            st.markdown("### R$ 447,00")
            st.markdown("---")
            if st.button("Comprar 40 Relatórios", key="comprar_pacote_master"):
                atualizar_dados_utilizador(st.session_state.username, creditos_atuais + 40, plano_atual)
                st.success("🎉 Pagamento Pix aprovado! +40 créditos adicionados à sua conta.")
                st.rerun()

# --- MENU 5: DEFINIÇÕES & PERFIL ---
elif nav_sistema == "⚙️ Definições & Perfil":
    st.title("⚙️ Definições de Conta & Perfil")
    st.markdown("Gerencie as credenciais de acesso da sua conta corporativa no Taticq.")
    st.markdown("---")
    
    st.markdown(f"**Utilizador Atual:** `{st.session_state.username}`")
    st.markdown(f"**Plano Contratado:** `{plano_atual}`")
    st.markdown(f"**Créditos em Conta:** `{creditos_atuais}`")
    
    st.markdown("---")
    st.subheader("🔑 Alterar Palavra-passe")
    
    nova_senha1 = st.text_input("Nova Palavra-passe", type="password", key="nova_pass_1")
    nova_senha2 = st.text_input("Confirmar Nova Palavra-passe", type="password", key="nova_pass_2")
    
    if st.button("Atualizar Palavra-passe"):
        if not nova_senha1 or not nova_senha2:
            st.warning("Preencha ambos os campos.")
        elif len(nova_senha1) < 4:
            st.warning("A palavra-passe deve ter pelo menos 4 caracteres.")
        elif nova_senha1 != nova_senha2:
            st.error("As palavras-passe não coincidem.")
        else:
            atualizar_senha_utilizador(st.session_state.username, nova_senha1)
            st.success("Palavra-passe atualizada com sucesso!")
