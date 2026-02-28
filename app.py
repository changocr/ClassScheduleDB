import streamlit as st
import pandas as pd
import matplotlib.colors as mcolors
from pyairtable import Table
import random

# ================= 配置与常量 =================
PERIODS = [
    "08:00~08:45", "08:55~09:40", "10:00~10:45", "10:55~11:40",
    "12:40~13:25", "13:35~14:20", "14:30~15:15", "15:25~16:10",
    "16:20~17:05", "17:15~18:00", "19:00~19:45", "19:55~20:40", "20:50~21:35"
]
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 从 Streamlit Secrets 读取密钥
try:
    AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
except Exception as e:
    st.error(f"请先在 Streamlit 设置中配置 Secrets: {e}")
    st.stop()

# 初始化 Airtable 表
table_colors = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Colors")
table_schedule = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Schedule")

# 颜色池
COLOR_POOL = list(mcolors.TABLEAU_COLORS.values()) + list(mcolors.CSS4_COLORS.values())

# ================= 辅助函数 =================

def get_random_color(existing_hexes):
    random.shuffle(COLOR_POOL)
    for color in COLOR_POOL:
        if color not in existing_hexes:
            return color
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def load_data():
    colors_records = table_colors.all()
    schedule_records = table_schedule.all()
    
    if colors_records:
        df_colors = pd.DataFrame([r["fields"] for r in colors_records])
        df_colors["RecordID"] = [r["id"] for r in colors_records]
    else:
        df_colors = pd.DataFrame(columns=["StudentName", "StartWeek", "EndWeek", "ColorHex", "RecordID"])
    
    if schedule_records:
        df_schedule = pd.DataFrame([r["fields"] for r in schedule_records])
    else:
        df_schedule = pd.DataFrame(columns=["StudentName", "Weekday", "Period", "ColorRecordID"])
    
    return df_colors, df_schedule

# ================= 界面逻辑 =================

st.set_page_config(page_title="智能课表系统", layout="wide")

# 1. 登录界面
if "user_name" not in st.session_state:
    st.title("👋 欢迎使用课表系统")
    input_name = st.text_input("请输入你的名字（管理员请输入 admin）", max_chars=20)
    if st.button("进入系统", type="primary"):
        if input_name:
            st.session_state.user_name = input_name
            st.rerun()
    st.stop()

user_name = st.session_state.user_name

# 2. 区分管理员和学生界面
if user_name.lower() == "admin":
    # ==================================
    # 管理员界面
    # ==================================
    st.title("🔧 管理员总览控制台")
    
    df_colors, df_schedule = load_data()
    
    df_merged = pd.DataFrame()
    if not df_schedule.empty and not df_colors.empty:
        df_merged = pd.merge(df_schedule, df_colors, left_on="ColorRecordID", right_on="RecordID", how="left")
    elif not df_schedule.empty:
        df_merged = df_schedule.copy()

    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=20, value=1)

    all_students = df_merged["StudentName"].unique().tolist() if "StudentName" in df_merged.columns else []
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # ---------------- 视图 1: 当周汇总课表 ----------------
    st.subheader(f"📅 第 {target_week} 周 实际课表")
    
    df_filtered = pd.DataFrame()
    if not df_merged.empty and "StartWeek" in df_merged.columns:
        df_filtered = df_merged[
            (df_merged["StartWeek"] <= target_week) & 
            (df_merged["EndWeek"] >= target_week)
        ]

    header_cols = st.columns([1] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        
        for d, day in enumerate(WEEKDAYS):
            html_content = "<div style='font-size:0.8em; line-height:1.2; min-height:20px;'>"
            if not df_filtered.empty:
                cell_data = df_filtered[
                    (df_filtered["Weekday"] == day) & 
                    (df_filtered["Period"] == period)
                ]
                
                if not cell_data.empty:
                    for _, row in cell_data.iterrows():
                        s_name = row.get('StudentName', '未知')
                        bg_color = student_color_map.get(s_name, "#eee")
                        rgb = mcolors.hex2color(bg_color)
                        text_color = "white" if (rgb[0]*rgb[1]*rgb[2]) < 0.5 else "black"
                        html_content += f"<div style='background-color:{bg_color}; color:{text_color}; padding:2px; margin:1px; border-radius:3px;'>{s_name}</div>"
            
            html_content += "</div>"
            row_cols[d+1].markdown(html_content, unsafe_allow_html=True)

    st.divider()

    # ---------------- 视图 2: 集体空闲时间涂色表 ----------------
    st.subheader(f"🕳️ 第 {target_week} 周 集体空闲表")
    st.caption("🟢 绿色 = 所有人都有空；🔴 红色 = 至少有1人有课")

    free_matrix = {p: {d: True for d in WEEKDAYS} for p in PERIODS}

    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            p = row["Period"]
            d = row["Weekday"]
            if p in free_matrix and d in free_matrix[p]:
                free_matrix[p][d] = False

    header_cols2 = st.columns([1] + [1]*len(WEEKDAYS))
    header_cols2[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols2[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        for d, day in enumerate(WEEKDAYS):
            is_free = free_matrix[period][day]
            color = "#90EE90" if is_free else "#FFB6C1"
            label = "空闲" if is_free else "有课"
            row_cols[d+1].markdown(
                f"<div style='background-color:{color}; padding:10px; border-radius:5px; text-align:center; font-weight:bold;'>{label}</div>",
                unsafe_allow_html=True
            )

else:
    # ==================================
    # 学生界面
    # ==================================
    st.title(f"📝 你好，{user_name}")
    
    with st.expander("📖 使用说明"):
        st.markdown("""
        1. 系统默认已有「黑色 (1-17周)」。
        2. 点击下方 ➕ 号可以新增属于你的颜色和周数范围。
        3. 在课表中点击格子，选择一个颜色即可占位。
        """)

    df_colors, df_schedule = load_data()

    # ---------------- 1. 颜色管理区 ----------------
    st.subheader("🎨 我的颜色与周数")
    
    my_colors = pd.DataFrame()
    if not df_colors.empty and "StudentName" in df_colors.columns:
        my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    
    # 如果没有颜色，创建默认黑色
    if my_colors.empty:
        try:
            table_colors.create({
                "StudentName": user_name,
                "StartWeek": 1,
                "EndWeek": 17,
                "ColorHex": "#000000"
            })
            st.success("已为您创建默认黑色 (1-17周)，页面即将刷新...")
            st.rerun()
        except Exception as e:
            st.error(f"初始化失败，请检查 Airtable 字段名: {e}")
            st.stop()

    # 重新加载
    df_colors, df_schedule = load_data()
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()

    # 显示现有颜色
    if not my_colors.empty:
        cols = st.columns(4)
        for idx, (_, row) in enumerate(my_colors.iterrows()):
            with cols[idx % 4]:
                st.markdown(
                    f"<div style='display:flex; align-items:center; gap:10px;'>"
                    f"<div style='background-color:{row['ColorHex']}; width:20px; height:20px; border:1px solid #ccc;'></div>"
                    f"<span>{int(row['StartWeek'])}-{int(row['EndWeek'])}周</span>"
                    f"</div>", 
                    unsafe_allow_html=True
                )

    # 新增颜色逻辑
    if st.button("➕ 新增颜色周数"):
        st.session_state.show_add_color = True

    if st.session_state.get("show_add_color", False):
        with st.form("add_color_form"):
            st.write("定义新的时间段")
            s_w = st.number_input("开始周", min_value=1, max_value=30, value=1)
            e_w = st.number_input("结束周", min_value=1, max_value=30, value=17)
            submitted = st.form_submit_button("确认创建")
            if submitted:
                existing_hexes = my_colors['ColorHex'].tolist()
                new_hex = get_random_color(existing_hexes)
                table_colors.create({
                    "StudentName": user_name,
                    "StartWeek": int(s_w),
                    "EndWeek": int(e_w),
                    "ColorHex": new_hex
                })
                st.session_state.show_add_color = False
                st.success("创建成功！")
                st.rerun()

    st.divider()

    # ---------------- 2. 课表点击区 (修复版：移除 popover) ----------------
    st.subheader("📅 点击课表占位")
    
    # 构建我的颜色选项字典
    my_color_options = {}
    if not my_colors.empty:
        for _, r in my_colors.iterrows():
            label = f"{int(r['StartWeek'])}-{int(r['EndWeek'])}周"
            my_color_options[r['RecordID']] = (r['ColorHex'], label)

    # 初始化编辑状态
    if "editing_cell" not in st.session_state:
        st.session_state.editing_cell = None

    # 渲染课表网格
    header_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{user_name}_{day}_{period}"
            
            # 查找记录
            current_color_id = None
            current_hex = "#f0f2f6"
            current_label = ""
            
            if not df_schedule.empty and set(["StudentName", "Weekday", "Period"]).issubset(df_schedule.columns):
                my_record = df_schedule[
                    (df_schedule["StudentName"] == user_name) &
                    (df_schedule["Weekday"] == day) &
                    (df_schedule["Period"] == period)
                ]
                if not my_record.empty:
                    current_color_id = my_record.iloc[0]['ColorRecordID']
                    if current_color_id in my_color_options:
                        current_hex = my_color_options[current_color_id][0]
                        current_label = my_color_options[current_color_id][1]

            with row_cols[d+1]:
                # 自定义按钮样式
                btn_style = f"""
                <style>
                div.stButton > button[key="{cell_key}"] {{
                    background-color: {current_hex};
                    color: {'white' if current_hex != '#f0f2f6' else '#333'};
                    height: 50px;
                    white-space: pre-wrap;
                }}
                </style>
                """
                st.markdown(btn_style, unsafe_allow_html=True)

                if st.button(f"{current_label}", key=cell_key):
                    st.session_state.editing_cell = (day, period)

            # 如果是当前正在编辑的格子，在下方显示编辑器
            if st.session_state.editing_cell == (day, period):
                st.info(f"正在编辑: {day} {period}")
                
                select_options = ["删除此时间段"]
                option_map = {"删除此时间段": None}
                
                for rec_id, (hex_val, label) in my_color_options.items():
                    select_options.append(label)
                    option_map[label] = rec_id

                choice = st.radio("选择操作", select_options, key=f"radio_{cell_key}")
                
                if st.button("确认保存", key=f"save_{cell_key}"):
                    # 删除旧记录
                    formula = f"AND({{StudentName}}='{user_name}', {{Weekday}}='{day}', {{Period}}='{period}')"
                    try:
                        old_records = table_schedule.all(formula=formula)
                        for r in old_records:
                            table_schedule.delete(r['id'])
                        
                        # 插入新记录
                        chosen_id = option_map[choice]
                        if chosen_id is not None:
                            table_schedule.create({
                                "StudentName": user_name,
                                "Weekday": day,
                                "Period": period,
                                "ColorRecordID": chosen_id
                            })
                        st.success("保存成功！")
                    except Exception as e:
                        st.error(f"保存出错: {e}")
                    
                    st.session_state.editing_cell = None
                    st.rerun()
                
                if st.button("取消", key=f"cancel_{cell_key}"):
                    st.session_state.editing_cell = None
                    st.rerun()
