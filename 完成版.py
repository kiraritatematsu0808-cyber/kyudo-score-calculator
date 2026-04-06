import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pandas as pd
import os
import altair as alt
from PIL import Image

# ==========================================
# 1. 接続設定
# ==========================================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1hXJ7OsVVNpClTpLuTG2SR1-Uk41xqaD6dHkJTKvUOD0/edit?gid=0#gid=0"

if "form_version" not in st.session_state:
    st.session_state.form_version = 0

def connect_gsheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(SPREADSHEET_URL)

# ==========================================
# 2. メンバー管理
# ==========================================
def load_members():
    try:
        doc = connect_gsheet()
        sheet_members = doc.worksheet("部員名簿")
        records = sheet_members.get_all_values()
        
        if len(records) == 0:
            default_headers = ["区分", "学年", "名前"]
            default_data = [
                ["H", "2", "立枩"], ["H", "3", "佐倉谷"], ["H", "3", "千田"], 
                ["H", "2", "新井"], ["H", "2", "佐藤"], ["H", "2", "坂下"], ["H", "2", "安藤"]
            ]
            sheet_members.append_row(default_headers)
            sheet_members.append_rows(default_data)
            records = [default_headers] + default_data

        raw_members = records[1:]
        member_data = []
        for row in raw_members:
            if len(row) >= 3:
                school_type, grade, name = row[0], row[1], row[2]
                type_label = "高" if school_type == "H" else "中"
                member_data.append({
                    "type_val": 1 if school_type == "H" else 2,
                    "grade": int(grade) if grade.isdigit() else 0,
                    "name": name,
                    "full": f"({type_label}{grade}) {name}"
                })

        if member_data:
            df_m = pd.DataFrame(member_data).sort_values(["type_val", "grade", "name"], ascending=[True, False, True])
            sorted_names = ["未選択"] + df_m["full"].tolist()
        else:
            sorted_names = ["未選択"]
        return sorted_names
    except Exception as e:
        st.error(f"部員名簿の読み込みに失敗しました: {e}")
        return ["未選択"]

if "members" not in st.session_state:
    st.session_state.members = load_members()

if "last_name" not in st.session_state:
    st.session_state.last_name = "未選択"

active_members = [m for m in st.session_state.members if m != "未選択"]
all_grades = ["すべて"] + sorted(list(set([m.split(")")[0] + ")" for m in active_members])))

def filter_members(grade_selection):
    if grade_selection == "すべて":
        return st.session_state.members
    return ["未選択"] + [m for m in active_members if m.startswith(grade_selection)]

def get_name_index(filtered_list):
    if st.session_state.last_name in filtered_list:
        return filtered_list.index(st.session_state.last_name)
    return 0

# ==========================================
# 3. UIとメッセージ
# ==========================================
st.set_page_config(page_title="弓道部 ポータル", layout="wide")

if "success_msg" in st.session_state:
    st.success(st.session_state.success_msg)
    del st.session_state.success_msg

st.title("🏹 弓道部 ポータルサイト [Pro]")

with st.sidebar:
    st.header("🏆 メニュー選択")
    # 入力と分析を完全に分離し、UIを直感的に整理
    app_mode = st.radio("機能一覧", [
        "📝 個人練習 (記録)", 
        "👥 団体練習 (記録)", 
        "📊 成績分析・月的表", 
        "🎯 目標・課題メモ", 
        "📅 予定表・欠席連絡",
        "📜 昇段審査対策"
    ])
    st.divider()
    
    st.header("👤 部員管理")
    with st.expander("新規部員を追加"):
        col_s, col_g = st.columns(2)
        with col_s: s_type = st.selectbox("区分", ["高校", "中学"], key="stype")
        with col_g: s_grade = st.selectbox("学年", ["1", "2", "3"], key="sgrade")
        new_name = st.text_input("名前", key=f"minp_{st.session_state.form_version}")
        if st.button("メンバー登録"):
            pure_names = [m.split(") ")[-1] if ") " in m else m for m in st.session_state.members]
            if not new_name: st.warning("名前を入力してください。")
            elif new_name in pure_names: st.error(f"「{new_name}」さんは登録済みです。")
            else:
                type_code = "H" if s_type == "高校" else "M"
                try:
                    doc = connect_gsheet()
                    sheet_members = doc.worksheet("部員名簿")
                    sheet_members.append_row([type_code, s_grade, new_name])
                    st.session_state.success_msg = f"✅ {s_type}{s_grade}年 {new_name} さんを追加しました！"
                    st.session_state.members = load_members() 
                    st.session_state.form_version += 1
                    st.rerun()
                except Exception as e: st.error(f"登録失敗: {e}")

# ==========================================
# 電卓方式（シーケンシャル入力）のロジック構築
# ==========================================
# 個人用
if "personal_data" not in st.session_state: st.session_state.personal_data = [["未"]*4]
def add_p_row(): st.session_state.personal_data.append(["未"]*4)
def sub_p_row(): 
    if len(st.session_state.personal_data) > 1: st.session_state.personal_data.pop()

def mark_p(mark):
    for r in range(len(st.session_state.personal_data)):
        for a in range(4):
            if st.session_state.personal_data[r][a] == "未":
                st.session_state.personal_data[r][a] = mark; return
def undo_p():
    for r in range(len(st.session_state.personal_data)-1, -1, -1):
        for a in range(3, -1, -1):
            if st.session_state.personal_data[r][a] != "未":
                st.session_state.personal_data[r][a] = "未"; return
def is_active_p(r, a):
    for rr in range(len(st.session_state.personal_data)):
        for aa in range(4):
            if st.session_state.personal_data[rr][aa] == "未":
                return r == rr and a == aa
    return False

# 団体用
if "g_num" not in st.session_state: st.session_state.g_num = 3
if "g_rows" not in st.session_state: st.session_state.g_rows = 1
if "group_data" not in st.session_state:
    st.session_state.group_data = [[ ["未"]*4 for _ in range(st.session_state.g_num) ] for _ in range(st.session_state.g_rows)]

def reset_group_data(num_members, num_rows):
    st.session_state.group_data = [[ ["未"]*4 for _ in range(num_members) ] for _ in range(num_rows)]
    st.session_state.g_num = num_members
    st.session_state.g_rows = num_rows

def mark_g(mark):
    # 道場での「立ち順」に合わせて、1本目を全員分→2本目を全員分...と探す
    for r in range(st.session_state.g_rows):
        for a in range(4):
            for i in range(st.session_state.g_num):
                if st.session_state.group_data[r][i][a] == "未":
                    st.session_state.group_data[r][i][a] = mark; return
def undo_g():
    for r in range(st.session_state.g_rows-1, -1, -1):
        for a in range(3, -1, -1):
            for i in range(st.session_state.g_num-1, -1, -1):
                if st.session_state.group_data[r][i][a] != "未":
                    st.session_state.group_data[r][i][a] = "未"; return
def is_active_g(r, i, a):
    for rr in range(st.session_state.g_rows):
        for aa in range(4):
            for ii in range(st.session_state.g_num):
                if st.session_state.group_data[rr][ii][aa] == "未":
                    return r == rr and i == ii and a == aa
    return False

# ==========================================
# 4. メインエリア
# ==========================================

# --- A. 目標・課題メモ モード ---
if app_mode == "🎯 目標・課題メモ":
    st.subheader("🎯 今月の目標・課題・指導メモ")
    col_g, col_n, col_m = st.columns([1, 1.5, 2])
    with col_g: s_grade = st.selectbox("学年", all_grades, key=f"memo_g")
    with col_n:
        f_members = filter_members(s_grade)
        selected_name = st.selectbox("氏名", f_members, index=get_name_index(f_members), key="memo_name")
    
    JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
    current_month = datetime.datetime.now(JST).strftime("%Y年%m月")
    with col_m: st.info(f"📅 対象月: {current_month}")

    if selected_name == "未選択": st.warning("名前を選択してください。")
    else:
        st.write("---")
        goal = st.text_area("🚀 今月の目標", placeholder="例: 的中率4割、皆中を1回以上出す")
        focus = st.text_area("🔍 今月の課題・意識すること", placeholder="例: 大三で右肘を高く、離れで緩まない")
        advice = st.text_area("🗣️ 監督コーチに指導されたこと", placeholder="例: 引き分けで肩が上がっている")
        
        if st.button("💾 クラウドに保存・更新", type="primary", use_container_width=True):
            try:
                doc = connect_gsheet()
                try: sheet_memo = doc.worksheet("目標メモ")
                except:
                    sheet_memo = doc.add_worksheet(title="目標メモ", rows="1000", cols="10")
                    sheet_memo.append_row(["年月", "氏名", "今月の目標", "課題・意識すること", "監督コーチからの指導"])
                
                records = sheet_memo.get_all_records()
                pure_target_name = selected_name.split(") ")[-1]
                found_row = -1
                for i, rec in enumerate(records):
                    if rec["年月"] == current_month and rec["氏名"] == pure_target_name:
                        found_row = i + 2; break
                
                if found_row != -1:
                    sheet_memo.update_cell(found_row, 3, goal)
                    sheet_memo.update_cell(found_row, 4, focus)
                    sheet_memo.update_cell(found_row, 5, advice)
                else: sheet_memo.append_row([current_month, pure_target_name, goal, focus, advice])
                st.session_state.last_name = selected_name
                st.success(f"✅ {current_month} の記録を保存しました！")
            except Exception as e: st.error(f"保存失敗: {e}")

        st.write("---")
        st.subheader("📚 過去の目標・指導履歴")
        try:
            doc = connect_gsheet()
            all_memos = pd.DataFrame(doc.worksheet("目標メモ").get_all_records())
            if not all_memos.empty:
                user_memos = all_memos[all_memos['氏名'] == selected_name.split(") ")[-1]].sort_values("年月", ascending=False)
                if not user_memos.empty:
                    for _, row in user_memos.iterrows():
                        with st.expander(f"📌 {row['年月']} の記録"):
                            st.write(f"**【今月の目標】**\n{row.get('今月の目標', '-')}")
                            st.write(f"**【課題・意識すること】**\n{row.get('課題・意識すること', '-')}")
                            st.write(f"**【監督コーチからの指導】**\n{row.get('監督コーチからの指導', '-')}")
                else: st.info("過去の履歴はありません。")
        except: st.info("履歴データがまだありません。")

# --- B. 個人練習 (記録) ---
elif app_mode == "📝 個人練習 (記録)":
    st.subheader("📝 個人練習 記録フォーム")
    col_g, col_n, col_t = st.columns([1, 1.5, 2])
    with col_g: s_grade = st.selectbox("学年", all_grades, key="p_g")
    with col_n:
        f_members = filter_members(s_grade)
        selected_name = st.selectbox("氏名", f_members, index=get_name_index(f_members), key="p_name")
    with col_t: practice_type = st.segmented_control("種別", ["自主練習", "射込み"], default="自主練習", key="p_type")
    
    st.divider()
    st.write("### 👇 結果を入力（下のボタンをポンポン押すだけ！）")
    # 究極のワンタップ入力パネル
    bc1, bc2, bc3 = st.columns(3)
    with bc1: st.button("🟢 ◯ (アタリ)", on_click=mark_p, args=("○",), use_container_width=True, type="primary")
    with bc2: st.button("🔴 ✕ (ハズレ)", on_click=mark_p, args=("×",), use_container_width=True, type="primary")
    with bc3: st.button("🔙 1つ戻る", on_click=undo_p, use_container_width=True)

    st.write("---")
    c1, c2, _ = st.columns([1,1,4])
    with c1: st.button("＋ 1立追加", on_click=add_p_row)
    with c2: st.button("－ 1立削除", on_click=sub_p_row)

    # 状態の可視化
    for r, row_data in enumerate(st.session_state.personal_data):
        cols = st.columns([1, 1, 1, 1, 1, 2])
        with cols[0]: st.write(f"**{r+1}立目**")
        for a in range(4):
            val = row_data[a]
            icon = "🟢" if val=="○" else ("🔴" if val=="×" else "⚪")
            with cols[a+1]:
                if is_active_p(r, a): st.markdown(f"<div style='text-align:center; background-color:#555; border-radius:5px;'><b>👉 {icon}</b></div>", unsafe_allow_html=True)
                else: st.markdown(f"<div style='text-align:center;'>{icon}</div>", unsafe_allow_html=True)
        # AI連携のダミー導線
        with cols[5]: 
            if st.button("🎥 3D解析", key=f"3d_p_{r}", help="Mocopiデータを分析"): st.toast("⚠️ この機能はmocopi連携後に有効になります", icon="🤖")

    st.write("---")
    if st.button("🚀 クラウドへ一括送信・保存", type="primary", use_container_width=True):
        if selected_name == "未選択": st.error("名前を選択してください！")
        else:
            try:
                doc = connect_gsheet()
                JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
                now = datetime.datetime.now(JST)
                sheet_title = now.strftime("%Y年%m月")
                try: sheet = doc.worksheet(sheet_title)
                except:
                    sheet = doc.add_worksheet(title=sheet_title, rows="1000", cols="20")
                    sheet.append_row(["日時", "氏名", "練習種別", "立数", "一本目", "二本目", "三本目", "四本目"])
                
                rows = []
                for r, row_data in enumerate(st.session_state.personal_data):
                    rows.append([now.strftime("%Y-%m-%d %H:%M:%S"), selected_name.split(") ")[-1], practice_type, f"{r+1}立目"] + row_data)
                
                sheet.append_rows(rows)
                st.session_state.last_name = selected_name
                st.session_state.personal_data = [["未"]*4] # リセット
                st.success(f"✅ クラウド保存完了！ ({sheet_title} シートに記録しました)")
                st.rerun()
            except Exception as e: st.error(f"保存失敗: {e}")

# --- C. 団体練習 (記録) ---
elif app_mode == "👥 団体練習 (記録)": 
    st.subheader("👥 団体練習（立ち） 記録フォーム")
    
    col_n, col_r, _ = st.columns([1,1,3])
    with col_n: num_members = st.number_input("立ちの人数", min_value=2, max_value=6, value=st.session_state.g_num)
    with col_r: group_rows = st.number_input("引く立数", min_value=1, max_value=10, value=st.session_state.g_rows)
    
    # 人数や立数が変わったらデータをリセット
    if num_members != st.session_state.g_num or group_rows != st.session_state.g_rows:
        reset_group_data(num_members, group_rows)
        st.rerun()

    st.divider()
    st.write("### 👇 結果を入力（下のボタンをポンポン押すだけ！）")
    st.caption("※大前の1本目→二的の1本目…の順に、自動でフォーカス（👉）が移動します。")
    bc1, bc2, bc3 = st.columns(3)
    with bc1: st.button("🟢 ◯ (アタリ)", on_click=mark_g, args=("○",), use_container_width=True, type="primary")
    with bc2: st.button("🔴 ✕ (ハズレ)", on_click=mark_g, args=("×",), use_container_width=True, type="primary")
    with bc3: st.button("🔙 1つ戻る", on_click=undo_g, use_container_width=True)
    st.write("---")

    positions = {2:["大前","落"], 3:["大前","中","落"], 4:["大前","二的","三的","落"], 5:["大前","二的","中","落前","落"], 6:["大前","二的","三的","四的","落前","落"]}
    cur_pos = positions.get(num_members, ["-"]*num_members)
    
    for r in range(st.session_state.g_rows):
        st.write(f"**{r+1}立目**")
        for i in range(st.session_state.g_num):
            cols = st.columns([1, 1.5, 2, 1, 1, 1, 1, 1.5])
            with cols[0]: st.write(f"**{cur_pos[i]}**")
            with cols[1]: g_grade = st.selectbox("学年", all_grades, key=f"gg_{r}_{i}", label_visibility="collapsed")
            with cols[2]:
                f_members = filter_members(g_grade)
                st.selectbox("氏名", f_members, index=0, key=f"gm_{r}_{i}", label_visibility="collapsed")
            
            for a in range(4):
                val = st.session_state.group_data[r][i][a]
                icon = "🟢" if val=="○" else ("🔴" if val=="×" else "⚪")
                with cols[a+3]:
                    if is_active_g(r, i, a): st.markdown(f"<div style='text-align:center; background-color:#555; border-radius:5px;'><b>👉 {icon}</b></div>", unsafe_allow_html=True)
                    else: st.markdown(f"<div style='text-align:center;'>{icon}</div>", unsafe_allow_html=True)
            with cols[7]:
                if st.button("🎥 解析", key=f"3d_g_{r}_{i}"): st.toast("⚠️ mocopi連携後に有効になります", icon="🤖")
        st.write("---")

    if st.button("🚀 クラウドへ一括送信・保存", type="primary", use_container_width=True):
        names = [st.session_state[f"gm_0_{i}"] for i in range(st.session_state.g_num)]
        if "未選択" in names: st.error("名前を選択していない枠があります！")
        else:
            try:
                doc = connect_gsheet()
                JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
                now = datetime.datetime.now(JST)
                sheet_title = now.strftime("%Y年%m月")
                try: sheet = doc.worksheet(sheet_title)
                except:
                    sheet = doc.add_worksheet(title=sheet_title, rows="1000", cols="20")
                    sheet.append_row(["日時", "氏名", "練習種別", "立数", "一本目", "二本目", "三本目", "四本目"])
                
                rows = []
                for r in range(st.session_state.g_rows):
                    for i in range(st.session_state.g_num):
                        name = st.session_state[f"gm_{r}_{i}"].split(") ")[-1]
                        rows.append([now.strftime("%Y-%m-%d %H:%M:%S"), name, "立ち", f"{r+1}立目"] + st.session_state.group_data[r][i])
                
                sheet.append_rows(rows)
                reset_group_data(st.session_state.g_num, st.session_state.g_rows)
                st.success(f"✅ 団体記録をクラウドに保存しました！")
                st.rerun()
            except Exception as e: st.error(f"保存失敗: {e}")

# --- D. 成績分析・月的表 モード (分離・統合) ---
elif app_mode == "📊 成績分析・月的表":
    st.subheader("📊 成績分析 ＆ 月的表ポータル")
    
    col_ag, col_au = st.columns([1, 2])
    with col_ag: s_grade_analysis = st.selectbox("学年", all_grades, key="stats_g")
    with col_au:
        f_members_analysis = filter_members(s_grade_analysis)
        target_user_full = st.selectbox("分析したい人を選択", f_members_analysis, key="stats_user")
        target_user = target_user_full.split(") ")[-1]

    if st.button("🔍 クラウドからデータを取得して分析", type="primary"):
        if target_user_full == "未選択": st.error("名前を選択してください！")
        else:
            try:
                doc = connect_gsheet()
                all_records = []
                for ws in doc.worksheets():
                    if ws.title not in ["部員名簿", "目標メモ", "欠席連絡"]: 
                        try: all_records.extend(ws.get_all_records())
                        except: pass
                            
                df = pd.DataFrame(all_records)
                if not df.empty:
                    u_df = df[df['氏名'] == target_user].copy()
                    if not u_df.empty:
                        date_col = u_df.columns[0]
                        u_df[date_col] = pd.to_datetime(u_df[date_col], errors='coerce')
                        u_df = u_df.dropna(subset=[date_col])
                        u_df['年月'] = u_df[date_col].dt.strftime('%Y年%m月')
                        
                        # 分析画面をタブでスッキリ整理
                        tab1, tab2 = st.tabs(["📅 月的表 (成績まとめ)", "📈 的中率推移グラフ"])
                        
                        with tab1:
                            st.write(f"### 📅 {target_user} さんの月的表")
                            available_months = sorted(u_df['年月'].unique(), reverse=True)
                            for month in available_months:
                                m_df = u_df[u_df['年月'] == month]
                                m_hits = sum((m_df[col] == "○").sum() for col in ["一本目", "二本目", "三本目", "四本目"])
                                m_total = sum((m_df[col] == "○").sum() + (m_df[col] == "×").sum() for col in ["一本目", "二本目", "三本目", "四本目"])
                                m_rate = (m_hits / m_total * 100) if m_total > 0 else 0
                                
                                with st.expander(f"📌 {month} の成績: {m_hits}中 / {m_total}本 (的中率: {m_rate:.1f}%)", expanded=(month == available_months[0])):
                                    c1, c2, c3 = st.columns(3)
                                    c1.metric("総引数", f"{m_total}本")
                                    c2.metric("総的中", f"{m_hits}本")
                                    c3.metric("総合 的中率", f"{m_rate:.1f}%")
                                    
                                    # ⚠️ ここにAI分析のダミー警告を設置して未来を匂わせる
                                    if m_rate < 40:
                                        st.warning("🤖 AI分析レポート：今月は「離れの瞬間の緩み」が多発しています。目標メモのゴースト映像を確認してください。")

                            st.divider()
                            st.write("#### 🕒 直近の記録（最新5件）")
                            recent_df = u_df.sort_values(by=date_col, ascending=False).head(5).copy()
                            recent_df[date_col] = recent_df[date_col].dt.strftime('%Y-%m-%d %H:%M')
                            st.dataframe(recent_df, use_container_width=True, hide_index=True)

                        with tab2:
                            st.write(f"### 📈 的中率推移グラフ")
                            time_unit = st.radio("集計単位", ["月ごと", "週ごと", "日ごと"], horizontal=True)
                            
                            if time_unit == "月ごと": u_df['期間'] = u_df[date_col].dt.strftime('%Y-%m')
                            elif time_unit == "週ごと": u_df['期間'] = u_df[date_col].dt.strftime('%Y-W%W')
                            else: u_df['期間'] = u_df[date_col].dt.strftime('%Y-%m-%d')

                            graph_data = []
                            for period in sorted(u_df['期間'].unique()):
                                p_df = u_df[u_df['期間'] == period]
                                hits = sum((p_df[col] == "○").sum() for col in ["一本目", "二本目", "三本目", "四本目"])
                                total = sum((p_df[col] == "○").sum() + (p_df[col] == "×").sum() for col in ["一本目", "二本目", "三本目", "四本目"])
                                rate = (hits / total * 100) if total > 0 else 0
                                graph_data.append({"期間": period, "的中率(%)": round(rate, 1), "総引数": total, "的中数": hits})
                            
                            res_df = pd.DataFrame(graph_data)
                            if not res_df.empty:
                                chart = alt.Chart(res_df).mark_bar(color='#FF4B4B', cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                                    x=alt.X('期間:N', title=time_unit),
                                    y=alt.Y('的中率(%):Q', title='的中率 (%)', scale=alt.Scale(domain=[0, 100])),
                                    tooltip=['期間', '的中率(%)', '的中数', '総引数']
                                ).properties(height=350)
                                st.altair_chart(chart, use_container_width=True)
                    else: st.warning(f"「{target_user}」さんのデータがありません。")
                else: st.info("クラウドに記録データがありません。")
            except Exception as e: st.error(f"分析エラー: {e}")

# --- E. 予定表・欠席連絡 モード ---
elif app_mode == "📅 予定表・欠席連絡":
    st.subheader("📅 予定表・欠席連絡")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("#### 📆 今月の予定表")
        try: st.image(Image.open("schedule.jpg"), use_container_width=True)
        except: st.warning("⚠️ 予定表の画像（schedule.jpg）が見つかりません。")
    with col2:
        st.write("#### 📝 欠席・遅刻連絡")
        st.link_button("👉 欠席連絡フォームを開く", "https://forms.gle/8MmQydxeJvD2Tpm97", type="primary", use_container_width=True)

# --- F. 昇段審査対策 モード ---
elif app_mode == "📜 昇段審査対策":
    st.subheader("📜 昇段審査対策")
    st.markdown("### 🚧 Coming Soon...")
    st.info("審査が近くなったら公開予定です。お楽しみに！")