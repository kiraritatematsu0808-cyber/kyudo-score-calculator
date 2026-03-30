import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pandas as pd
import os

# ==========================================
# 1. 接続設定
# ==========================================
# ⚠️ 自分のURLに書き換えてください（そのまま使います）
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1hXJ7OsVVNpClTpLuTG2SR1-Uk41xqaD6dHkJTKvUOD0/edit?gid=0#gid=0"

# フォームの強制リセット用
if "form_version" not in st.session_state:
    st.session_state.form_version = 0

def connect_gsheet():
    # スプレッドシート「全体」を返すように変更
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(SPREADSHEET_URL)

# ==========================================
# 2. メンバー管理（クラウド「部員名簿」シートと連動）
# ==========================================
def load_members():
    try:
        doc = connect_gsheet()
        # 「部員名簿」シートを開く
        sheet_members = doc.worksheet("部員名簿")
        records = sheet_members.get_all_values()
        
        # もしシートが完全に空っぽなら、デフォルトのデータを入れる
        if len(records) == 0:
            default_headers = ["区分", "学年", "名前"]
            default_data = [
                ["H", "2", "立枩"], ["H", "3", "佐倉谷"], ["H", "3", "千田"], 
                ["H", "2", "新井"], ["H", "2", "佐藤"], ["H", "2", "坂下"], ["H", "2", "安藤"]
            ]
            sheet_members.append_row(default_headers)
            sheet_members.append_rows(default_data)
            records = [default_headers] + default_data

        # 1行目（見出し）を除いた実際のデータを取り出す
        raw_members = records[1:]
        
        member_data = []
        for row in raw_members:
            if len(row) >= 3:
                school_type, grade, name = row[0], row[1], row[2]
                type_label = "高" if school_type == "H" else "中"
                member_data.append({
                    "type_val": 1 if school_type == "H" else 2, # 高校を先に
                    "grade": int(grade) if grade.isdigit() else 0,
                    "name": name,
                    "full": f"({type_label}{grade}) {name}"
                })

        # 高校→中学、学年(3→1)の順でソート
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

# ==========================================
# 3. UIとメッセージ
# ==========================================
st.set_page_config(page_title="弓道 的中Pro", layout="wide")

if "success_msg" in st.session_state:
    st.success(st.session_state.success_msg)
    del st.session_state.success_msg

st.title("🏹 弓道 的中記録システム [Pro]")

with st.sidebar:
    st.header("🏆 モード選択")
    app_mode = st.radio("入力モード", ["個人練習", "団体（立ち）"])
    st.divider()
    
    st.header("👤 部員管理")
    with st.expander("新規部員を追加"):
        col_s, col_g = st.columns(2)
        with col_s: s_type = st.selectbox("区分", ["高校", "中学"], key="stype")
        with col_g: s_grade = st.selectbox("学年", ["1", "2", "3"], key="sgrade")
        
        new_name = st.text_input("名前", key=f"minp_{st.session_state.form_version}")
        
        if st.button("メンバー登録"):
            pure_names = [m.split(") ")[-1] if ") " in m else m for m in st.session_state.members]
            if not new_name:
                st.warning("名前を入力してください。")
            elif new_name in pure_names:
                st.error(f"「{new_name}」さんは登録済みです。")
            else:
                type_code = "H" if s_type == "高校" else "M"
                try:
                    # クラウドの「部員名簿」に直接書き込む！
                    doc = connect_gsheet()
                    sheet_members = doc.worksheet("部員名簿")
                    sheet_members.append_row([type_code, s_grade, new_name])
                    
                    st.session_state.success_msg = f"✅ {s_type}{s_grade}年 {new_name} さんをクラウド名簿に追加しました！"
                    st.session_state.members = load_members() # リストを再取得
                    st.session_state.form_version += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"登録に失敗しました: {e}")

# ==========================================
# 4. メイン入力エリア
# ==========================================
if app_mode == "個人練習":
    st.subheader("📝 個人練習 記録フォーム")
    col1, col2 = st.columns(2)
    with col1:
        selected_name = st.selectbox("氏名 (学年順)", st.session_state.members, index=0, key=f"pn_{st.session_state.form_version}")
    with col2:
        practice_type = st.selectbox("種別", ["自主練習", "射込み", "立ち"], key=f"pt_{st.session_state.form_version}")
    
    if "personal_rows" not in st.session_state: st.session_state.personal_rows = 1
    c1, c2, _ = st.columns([1,1,4])
    with c1: 
        if st.button("＋ 1立追加"): st.session_state.personal_rows += 1
    with c2:
        if st.button("－ 1立削除") and st.session_state.personal_rows > 1: st.session_state.personal_rows -= 1
            
    all_data = []
    for r in range(st.session_state.personal_rows):
        st.write(f"**{r+1}立目**")
        cols = st.columns(4)
        row_res = []
        for a in range(4):
            with cols[a]:
                res = st.selectbox(f"p_{r}_{a}", ["未", "○", "×"], key=f"p_{r}_{a}_{st.session_state.form_version}", label_visibility="collapsed")
                row_res.append(res)
        all_data.append({"name": selected_name, "type": practice_type, "num": f"{r+1}立目", "data": row_res})

else: # 団体
    st.subheader("👥 団体（立ち） 記録フォーム")
    num_members = st.sidebar.number_input("立ちの人数", min_value=1, max_value=6, value=3)
    practice_type = "立ち"
    positions = {1:["大前"], 2:["大前","落"], 3:["大前","中","落"], 4:["大前","二的","三的","落"], 5:["大前","二的","中","落前","落"], 6:["大前","二的","三的","四的","落前","落"]}
    cur_pos = positions.get(num_members, ["-"]*num_members)
    
    all_data = []
    for i in range(num_members):
        cols = st.columns([1, 2, 1, 1, 1, 1])
        with cols[0]: st.write(f"**{cur_pos[i]}**")
        with cols[1]:
            m_name = st.selectbox(f"g_m_{i}", st.session_state.members, index=0, key=f"gm_{i}_{st.session_state.form_version}", label_visibility="collapsed")
        row_res = []
        for a in range(4):
            with cols[a+2]:
                res = st.selectbox(f"gr_{i}_{a}", ["未", "○", "×"], key=f"gr_{i}_{a}_{st.session_state.form_version}", label_visibility="collapsed")
                row_res.append(res)
        all_data.append({"name": m_name, "type": practice_type, "num": "1立目", "data": row_res})
        st.write("---")

if st.button("🚀 クラウドへ一括送信・保存", type="primary", use_container_width=True):
    if "未選択" in [d["name"] for d in all_data]:
        st.error("名前を選択してください！")
    else:
        try:
            doc = connect_gsheet()
            sheet = doc.worksheet("記録") # 「記録」シートに保存！
            
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 保存時は名前のみ抽出
            rows = [[now, d["name"].split(") ")[-1], d["type"], d["num"]] + d["data"] for d in all_data]
            sheet.append_rows(rows)
            st.session_state.form_version += 1
            st.session_state.personal_rows = 1
            st.session_state.success_msg = "✅ クラウド保存完了！ 全ての入力をリセットしました。"
            st.rerun()
        except Exception as e: st.error(f"保存失敗: {e}")

# ==========================================
# 5. 分析エリア（中高・学年不問、立ち限定的中率）
# ==========================================
st.divider()
st.subheader("📈 クラウド成績分析パネル")
target_user_full = st.selectbox("分析したい人を選択", st.session_state.members, key="stats_user")
target_user = target_user_full.split(") ")[-1]

if st.button("クラウドからデータを取得して分析"):
    try:
        doc = connect_gsheet()
        sheet = doc.worksheet("記録") # 「記録」シートから読み込み！
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            u_df = df[df['氏名'] == target_user]
            if not u_df.empty:
                tachi_df = u_df[u_df['練習種別'] == '立ち']
                
                # 全体統計
                hits = 0; total = 0
                for col in ["一本目", "二本目", "三本目", "四本目"]:
                    hits += (u_df[col] == "○").sum()
                    total += (u_df[col] == "○").sum() + (u_df[col] == "×").sum()
                
                st.write(f"#### {target_user} さんの総合成績")
                m1, m2, m3 = st.columns(3)
                m1.metric("総引数", f"{total}本")
                m2.metric("総的中", f"{hits}本")
                m3.metric("総的中率", f"{(hits/total*100):.1f}%" if total>0 else "0%")
                
                with st.expander("🔍 「立ち」練習の詳細を分析"):
                    if tachi_df.empty:
                        st.info("「立ち」のデータがありません。")
                    else:
                        t_hits = 0; t_total = 0
                        arrow_stats = {"一本目": [0,0], "二本目": [0,0], "三本目": [0,0], "四本目": [0,0]}
                        for _, row in tachi_df.iterrows():
                            for col in ["一本目", "二本目", "三本目", "四本目"]:
                                if row[col] == "○": t_hits += 1; t_total += 1; arrow_stats[col][0] += 1; arrow_stats[col][1] += 1
                                elif row[col] == "×": t_total += 1; arrow_stats[col][1] += 1
                        
                        st.write("#### 「立ち」のみの総的中率")
                        st.subheader(f"🎯 立ち的中率: {(t_hits/t_total*100):.1f}% ({t_hits}中/{t_total}本)")
                        
                        st.write("#### 本数別の的中率")
                        d_cols = st.columns(4)
                        for i, col in enumerate(["一本目", "二本目", "三本目", "四本目"]):
                            h, t = arrow_stats[col]
                            r = (h / t * 100) if t > 0 else 0
                            with d_cols[i]: st.metric(col, f"{r:.1f}%", help=f"{h}/{t}")
            else: st.warning("データがありません")
        else: st.info("クラウドにデータがありません")
    except Exception as e: st.error(f"分析エラー: {e}")