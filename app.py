import streamlit as st
import pandas as pd
from datetime import datetime
from passlib.hash import bcrypt
from database import SessionLocal, init_db
from models import User, Service, Expense, Client, Appointment, FinancialTransaction

# Inicializar Banco de Dados
init_db()

st.set_page_config(page_title="Fio&Caixa — Gestão para Barbearias", layout="wide", page_icon="✂️")

def get_db():
    return SessionLocal()

# Criar usuário admin padrão se não existir
db = get_db()
if not db.query(User).filter_by(username="admin").first():
    hashed_pw = bcrypt.hash("admin123")
    admin_user = User(username="admin", password_hash=hashed_pw, role="admin")
    db.add(admin_user)
    db.commit()
db.close()

# Autenticação Simples na Sessão
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user"] = None

def login_screen():
    st.markdown("# ✂️ Fio&Caixa — Gestão Inteligente")
    st.subheader("Faça login para acessar o painel administrativo")
    
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        db = get_db()
        user = db.query(User).filter_by(username=username).first()
        db.close()
        if user and bcrypt.verify(password, user.password_hash):
            st.session_state["authenticated"] = True
            st.session_state["user"] = user.username
            st.success("Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

if not st.session_state["authenticated"]:
    # Opção para Página Pública de Agendamento ou Login
    tab_login, tab_public = st.tabs(["Painel Administrativo", "Agendamento Online (Cliente)"])
    
    with tab_login:
        login_screen()
        
    with tab_public:
        st.markdown("## 📅 Agende seu Horário na Barbearia")
        db = get_db()
        services = db.query(Service).filter_by(is_active=True).all()
        
        if not services:
            st.warning("Nenhum serviço disponível no momento.")
        else:
            service_options = {s.name: s for s in services}
            selected_service_name = st.selectbox("Escolha o Serviço", list(service_options.keys()))
            selected_service = service_options[selected_service_name]
            
            st.write(f"**Preço:** R$ {selected_service.price:.2f} | **Duração:** {selected_service.duration_minutes} min")
            
            app_date = st.date_input("Data do Atendimento", min_value=datetime.today().date())
            app_time = st.time_input("Horário")
            
            client_name = st.text_input("Seu Nome Completo")
            client_phone = st.text_input("Seu Telefone / WhatsApp")
            
            if st.button("Confirmar Agendamento"):
                if not client_name or not client_phone:
                    st.error("Preencha seu nome e telefone.")
                else:
                    full_datetime = datetime.combine(app_date, app_time)
                    # Verificar conflito
                    conflict = db.query(Appointment).filter_by(date_time=full_datetime, status="confirmado").first()
                    if conflict:
                        st.error("Horário indisponível. Escolha outro horário.")
                    else:
                        # Cadastrar ou recuperar cliente
                        client = db.query(Client).filter_by(phone=client_phone).first()
                        if not client:
                            client = Client(name=client_name, phone=client_phone)
                            db.add(client)
                            db.commit()
                            db.refresh(client)
                        
                        import random
                        code = f"FIO-{random.randint(1000, 9999)}"
                        
                        new_app = Appointment(
                            code=code,
                            client_id=client.id,
                            service_id=selected_service.id,
                            date_time=full_datetime,
                            status="aguardando confirmação"
                        )
                        db.add(new_app)
                        db.commit()
                        st.success(f"Agendamento realizado com sucesso! Código de identificação: **{code}**")
        db.close()
        st.stop()

# --- PAINEL ADMINISTRATIVO ---
st.sidebar.title(f"Bem-vindo, {st.session_state['user']}")
menu = st.sidebar.radio("Navegação", [
    "Dashboard", 
    "Serviços", 
    "Despesas", 
    "Fluxo de Caixa", 
    "Agendamentos", 
    "Clientes", 
    "Lucros", 
    "Relatórios"
])

if st.sidebar.button("Sair"):
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()

db = get_db()

if menu == "Dashboard":
    st.title("📊 Dashboard Executivo")
    
    # Indicadores
    transactions = db.query(FinancialTransaction).all()
    total_entradas = sum(t.amount for t in transactions if t.operation_type == "entrada")
    total_saidas = sum(t.amount for t in transactions if t.operation_type == "saida")
    saldo_caixa = total_entradas - total_saidas
    
    appointments = db.query(Appointment).all()
    concluidos = sum(1 for a in appointments if a.status == "concluído")
    pendentes = sum(1 for a in appointments if a.status == "aguardando confirmação")
    cancelados = sum(1 for a in appointments if a.status == "cancelado")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Saldo Atual em Caixa", f"R$ {saldo_caixa:.2f}")
    col2.metric("Total Entradas", f"R$ {total_entradas:.2f}", delta="Receitas")
    col3.metric("Total Saídas", f"R$ {total_saidas:.2f}", delta="-Despesas", delta_color="inverse")
    col4.metric("Atendimentos Concluídos", concluidos)
    
    st.divider()
    st.subheader("Movimentações Recentes")
    if transactions:
        df_trans = pd.DataFrame([{
            "Descrição": t.description,
            "Valor": f"R$ {t.amount:.2f}",
            "Data": t.date.strftime("%d/%m/%Y %H:%M"),
            "Tipo": t.operation_type.upper(),
            "Categoria": t.category
        } for t in transactions[-10:]])
        st.dataframe(df_trans, use_container_width=True)
    else:
        st.info("Nenhuma movimentação financeira registrada.")

elif menu == "Serviços":
    st.title("✂️ Gestão de Serviços")
    
    with st.form("form_service"):
        st.subheader("Cadastrar Novo Serviço")
        name = st.text_input("Nome do Serviço")
        description = st.text_area("Descrição")
        price = st.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
        cost = st.number_input("Custo Estimado (R$)", min_value=0.0, format="%.2f")
        duration = st.number_input("Duração (minutos)", min_value=5, value=30, step=5)
        category = st.selectbox("Categoria", ["Cabelo", "Barba", "Combo", "Outros"])
        
        submitted = st.form_submit_button("Salvar Serviço")
        if submitted:
            if name and price > 0:
                srv = Service(name=name, description=description, price=price, cost=cost, duration_minutes=duration, category=category)
                db.add(srv)
                db.commit()
                st.success("Serviço cadastrado com sucesso!")
                st.rerun()
            else:
                st.error("Preencha o nome e um preço válido.")
                
    st.divider()
    st.subheader("Serviços Cadastrados")
    services = db.query(Service).all()
    if services:
        df_srv = pd.DataFrame([{
            "ID": s.id,
            "Nome": s.name,
            "Preço": f"R$ {s.price:.2f}",
            "Custo": f"R$ {s.cost:.2f}",
            "Duração": f"{s.duration_minutes} min",
            "Ativo": "Sim" if s.is_active else "Não"
        } for s in services])
        st.dataframe(df_srv, use_container_width=True)

elif menu == "Despesas":
    st.title("💸 Controle de Despesas")
    with st.form("form_expense"):
        st.subheader("Registrar Despesa")
        exp_name = st.text_input("Descrição da Despesa")
        exp_cat = st.selectbox("Categoria", ["Aluguel", "Água e Energia", "Internet", "Produtos", "Salários", "Impostos", "Outros"])
        exp_amount = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        due_date = st.date_input("Data de Vencimento")
        status = st.selectbox("Status", ["pendente", "pago", "atrasado"])
        payment_method = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Transferência", "Outros"])
        
        if st.form_submit_button("Salvar Despesa"):
            new_exp = Expense(
                name=exp_name,
                category=exp_cat,
                amount=exp_amount,
                due_date=datetime.combine(due_date, datetime.min.time()),
                status=status,
                payment_method=payment_method,
                payment_date=datetime.now() if status == "pago" else None
            )
            db.add(new_exp)
            if status == "pago":
                # Lançar automaticamente no fluxo de saída
                trans = FinancialTransaction(
                    description=f"Despesa: {exp_name}",
                    amount=exp_amount,
                    category=exp_cat,
                    payment_method=payment_method,
                    operation_type="saida"
                )
                db.add(trans)
            db.commit()
            st.success("Despesa registrada com sucesso!")
            st.rerun()

elif menu == "Fluxo de Caixa":
    st.title("💰 Fluxo de Caixa")
    st.subheader("Movimentações Financeiras")
    transactions = db.query(FinancialTransaction).all()
    if transactions:
        df_cf = pd.DataFrame([{
            "Descrição": t.description,
            "Valor": f"R$ {t.amount:.2f}",
            "Tipo": t.operation_type.upper(),
            "Categoria": t.category,
            "Forma Pagto": t.payment_method,
            "Data": t.date.strftime("%d/%m/%Y")
        } for t in transactions])
        st.dataframe(df_cf, use_container_width=True)
    else:
        st.info("Nenhuma movimentação registrada.")

elif menu == "Agendamentos":
    st.title("📅 Gestão de Agendamentos")
    appointments = db.query(Appointment).all()
    if appointments:
        for app in appointments:
            with st.expander(f"[{app.code}] {app.client.name} - {app.service.name} ({app.date_time.strftime('%d/%m/%Y %H:%M')}) - Status: {app.status}"):
                new_status = st.selectbox("Alterar Status", ["aguardando confirmação", "confirmado", "em atendimento", "concluído", "cancelado"], index=["aguardando confirmação", "confirmado", "em atendimento", "concluído", "cancelado"].index(app.status), key=f"status_{app.id}")
                payment_method = st.selectbox("Forma de Pagamento (se concluído)", ["Dinheiro", "Pix", "Cartão de Débito", "Cartão de Crédito"], key=f"pay_{app.id}")
                
                if st.button("Atualizar Agendamento", key=f"btn_{app.id}"):
                    if new_status == "concluído" and app.status != "concluído":
                        # Gerar entrada financeira automática sem duplicidade
                        trans = FinancialTransaction(
                            description=f"Serviço: {app.service.name} - Cliente: {app.client.name}",
                            amount=app.service.price,
                            category="Serviços",
                            payment_method=payment_method,
                            operation_type="entrada"
                        )
                        db.add(trans)
                    app.status = new_status
                    app.payment_method = payment_method
                    db.commit()
                    st.success("Agendamento atualizado com sucesso!")
                    st.rerun()
    else:
        st.info("Nenhum agendamento encontrado.")

elif menu == "Clientes":
    st.title("👥 Cadastro de Clientes")
    clients = db.query(Client).all()
    if clients:
        df_clients = pd.DataFrame([{
            "Nome": c.name,
            "Telefone": c.phone,
            "Primeiro Atendimento": c.first_service_date.strftime("%d/%m/%Y")
        } for c in clients])
        st.dataframe(df_clients, use_container_width=True)
    else:
        st.info("Nenhum cliente cadastrado.")

elif menu == "Lucros":
    st.title("📈 Apuração de Lucros")
    transactions = db.query(FinancialTransaction).all()
    receita_bruta = sum(t.amount for t in transactions if t.operation_type == "entrada")
    despesas_pagas = sum(t.amount for t in transactions if t.operation_type == "saida")
    lucro_liquido = receita_bruta - despesas_pagas
    margem = (lucro_liquido / receita_bruta * 100) if receita_bruta > 0 else 0.0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Receita Bruta", f"R$ {receita_bruta:.2f}")
    col2.metric("Despesas Pagas", f"R$ {despesas_pagas:.2f}")
    col3.metric("Lucro Líquido Estimado", f"R$ {lucro_liquido:.2f}", delta=f"{margem:.1f}% Margem")

elif menu == "Relatórios":
    st.title("📊 Relatórios Financeiros")
    st.write("Exporte os dados consolidados do sistema.")
    transactions = db.query(FinancialTransaction).all()
    if transactions:
        df_rep = pd.DataFrame([{
            "Descrição": t.description,
            "Valor": t.amount,
            "Tipo": t.operation_type,
            "Categoria": t.category,
            "Data": t.date.strftime("%d/%m/%Y")
        } for t in transactions])
        st.download_button("Baixar Relatório em CSV", df_rep.to_csv(index=False).encode('utf-8'), "relatorio_financeiro.csv", "text/csv")
    else:
        st.info("Sem dados para exportar.")

db.close()
