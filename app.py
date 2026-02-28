
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
CLEAR_PASSWORD = "1956"

try:
    AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
except Exception as e:
    st.error(f"部署失败：请先在 Streamlit 后台配置 Secrets 密钥 | 错误信息：{e}")
    st.stop()

@st.cache_resource
def init_airtable():
    return (
        Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Colors"),
        Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Schedule")
    )
table_colors, table_schedule = init_airtable()

COLOR_POOL = list(mcolors.TABLEAU_COLORS.values()) + list(mcolors.CSS4_COLORS.values())

# ================= 辅助函数 =================
def get_random_color(existing_hexes):
    random.shuffle(COLOR_POOL)
    for color in COLOR_POOL:
        if color not in existing_hexes:
            return color
    return f"#{random.randint(0, 0xFFFFFF):06x}"

@st.cache_data(ttl=30)
def load_full_data():
    colors_records = table_colors.all()
    if colors_records:
        df_colors = pd.DataFrame([r["fields"] for r in colors_records])
        df_colors["RecordID"] = [r["id"] for r in colors_records]
    else:
        df_colors = pd.DataFrame(columns=["StudentName", "StartWeek", "EndWeek", "ColorHex", "RecordID"])
    
    schedule_records = table_schedule.all()
    if schedule_records:
        df_schedule = pd.DataFrame([r["fields"] for r in schedule_records])
    else:
        df_schedule = pd.DataFrame(columns=["StudentName", "Weekday", "Period", "ColorRecordID"])
    
    return df_colors, df_schedule

def load_user_init_data(user_name, df_colors, df_schedule):
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    user_schedule = {}
    color_id_map = {row["RecordID"]: (row["ColorHex"], f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周") for _, row in my_colors.iterrows()}
    
    if not df_schedule.empty and "StudentName" in df_schedule.columns:
        user_records = df_schedule[df_schedule["StudentName"] == user_name]
        for _, row in user_records.iterrows():
            key = f"{row['Weekday']}-{row['Period']}"
            c_id = row["ColorRecordID"]
            if c_id in color_id_map:
                user_schedule[key] = (c_id, color_id_map[c_id][0], color_id_map[c_id][1])
    return my_colors, user_schedule, color_id_map

# ================= 页面基础配置 =================
st.set_page_config(page_title="课表系统", layout="wide", initial_sidebar_state="collapsed")

# 1. 登录界面
if "user_name" not in st.session_state:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("👋 欢迎使用课表系统")
        st.markdown("<p style='color:#666; margin-bottom:2rem;'>请输入您的身份标识以继续访问系统核心组件。</p>", unsafe_allow_html=True)
        input_name = st.text_input("用户身份标识 (User ID)", max_chars=20)
        if st.button("进入系统", type="primary", use_container_width=True):
            if input_name.strip():
                st.session_state.user_name = input_name.strip()
                for key in list(st.session_state.keys()):
                    if key not in ["user_name"]:
                        del st.session_state[key]
                st.rerun()
    st.stop()

user_name = st.session_state.user_name

# 2. 区分管理员/学生界面
if user_name.lower() == "admin":
    # ==================================
    # 管理员界面 (恢复完整逻辑)
    # ==================================
    st.title("🔧 管理员总览控制台")
    df_colors, df_schedule = load_full_data()

    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=30, value=1)

    all_students = []
    if not df_schedule.empty and "StudentName" in df_schedule.columns:
        all_students = df_schedule["StudentName"].unique().tolist()
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # 视图1：当周有效课表汇总
    st.subheader(f"📅 第 {target_week} 周 有效课表汇总")
    header_cols = st.columns([1] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        for d, day in enumerate(WEEKDAYS):
            html_content = "<div style='font-size:0.8em; line-height:1.2; min-height:20px;'>"
            if not df_schedule.empty and set(["StudentName", "Weekday", "Period"]).issubset(df_schedule.columns):
                cell_records = df_schedule[(df_schedule["Weekday"] == day) & (df_schedule["Period"] == period)]
                if not cell_records.empty:
                    for _, row in cell_records.iterrows():
                        s_name = row.get("StudentName", "未知")
                        show_this_week = True
                        if not df_colors.empty and "ColorRecordID" in row and pd.notna(row["ColorRecordID"]):
                            color_match = df_colors[df_colors["RecordID"] == row["ColorRecordID"]]
                            if not color_match.empty:
                                s_w = color_match.iloc[0].get("StartWeek", 1)
                                e_w = color_match.iloc[0].get("EndWeek", 17)
                                if not (s_w <= target_week <= e_w):
                                    show_this_week = False
                        if show_this_week:
                            bg_color = student_color_map.get(s_name, "#eeeeee")
                            rgb = mcolors.hex2color(bg_color)
                            text_color = "white" if (rgb[0]*rgb[1]*rgb[2]) < 0.5 else "black"
                            html_content += f"<div style='background-color:{bg_color}; color:{text_color}; padding:4px; margin:2px; border-radius:4px;'>{s_name}</div>"
            html_content += "</div>"
            row_cols[d+1].markdown(html_content, unsafe_allow_html=True)

    st.divider()

    # 视图2：当周集体空闲表
    st.subheader(f"🕳️ 第 {target_week} 周 集体空闲时间表")
    st.caption("🟢 绿色 = 所有人都空闲；🔴 红色 = 至少1人有课")
    free_matrix = {p: {d: True for d in WEEKDAYS} for p in PERIODS}

    if not df_schedule.empty and set(["StudentName", "Weekday", "Period", "ColorRecordID"]).issubset(df_schedule.columns):
        for _, row in df_schedule.iterrows():
            p = row["Period"]
            d = row["Weekday"]
            is_valid = True
            if not df_colors.empty and "ColorRecordID" in row and pd.notna(row["ColorRecordID"]):
                color_match = df_colors[df_colors["RecordID"] == row["ColorRecordID"]]
                if not color_match.empty:
                    s_w = color_match.iloc[0].get("StartWeek", 1)
                    e_w = color_match.iloc[0].get("EndWeek", 17)
                    if not (s_w <= target_week <= e_w):
                        is_valid = False
            if is_valid and p in free_matrix and d in free_matrix[p]:
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
            bg_color = "#dcfce7" if is_free else "#fee2e2"  # 使用更柔和的现代绿/红色系
            text_color = "#166534" if is_free else "#991b1b"
            border_color = "#bbf7d0" if is_free else "#fecaca"
            label = "空闲" if is_free else "有课"
            row_cols[d+1].markdown(
                f"<div style='background-color:{bg_color}; color:{text_color}; padding:10px; border-radius:6px; border:1px solid {border_color}; text-align:center; font-weight:600; height:38px; line-height:16px;'>{label}</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # 一键清空数据库
    st.subheader("⚠️ 危险操作：清空全部数据库")
    st.caption("此操作会删除所有学生的周数配置和课表数据，无法恢复，请谨慎操作！")
    input_pwd = st.text_input("请输入操作密码", type="password")
    if input_pwd == CLEAR_PASSWORD:
        st.warning("密码验证通过！请再次确认是否要清空全部数据")
        if st.button("✅ 确认清空全部数据库", type="primary", use_container_width=True):
            try:
                all_colors = table_colors.all()
                all_schedule = table_schedule.all()
                if all_colors:
                    table_colors.batch_delete([r["id"] for r in all_colors])
                if all_schedule:
                    table_schedule.batch_delete([r["id"] for r in all_schedule])
                st.cache_data.clear()
                st.success("✅ 数据库已全部清空！页面即将刷新...")
                st.rerun()
            except Exception as e:
                st.error(f"清空失败：{e}")
    elif input_pwd:
        st.error("密码错误，无法执行操作")

else:
    # ==================================
    # 学生界面 (现代化浅色排版 & 宽度强制突破)
    # ==================================
    
    st.markdown("""
    <style>
    /* 模块间距定义 */
    .module-spacer { height: 1.5rem; }
    .section-title { font-size: 1.1em; font-weight: 600; color: #333333; margin-bottom: 1rem; border-left: 4px solid #3b82f6; padding-left: 10px; }
    
    /* === 核心：强制破除 Streamlit 列与按钮的宽度限制 === */
    [data-testid="column"] { 
        min-width: 0 !important; 
        padding: 0 !important; 
    }
    [data-testid="column"] > div { 
        width: 100% !important; 
    }
    div[data-testid="stButton"] {
        width: 100% !important;
        display: flex !important;
    }
    
    /* 网格容器间距清零 */
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    [data-testid="stHorizontalBlock"] { gap: 0 !important; }
    [data-testid="element-container"] { margin-bottom: 0 !important; width: 100% !important; }
    
    /* 基础按钮：SaaS 现代网格风格，宽度 100% */
    .stButton > button {
        width: 100% !important;
        flex: 1 1 auto !important; 
        height: 48px !important; 
        border-radius: 0 !important;
        border: 1px solid #eaebec !important; 
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.85rem !important;
        line-height: 48px !important;
        min-height: unset !important;
        padding: 0 4px !important;
        margin: 0 !important;
        transition: all 0.15s ease-in-out;
    }
    
    .stButton > button:hover {
        filter: brightness(0.95);
        cursor: pointer;
    }

    .stMarkdown p { margin: 0 !important; padding: 0 !important; }
    
    /* 表头与时间轴样式 */
    .schedule-header, .schedule-time {
        height: 48px !important;
        line-height: 48px !important;
        border: 1px solid #eaebec !important;
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.85em !important;
        font-weight: 600;
        color: #555555;
        text-align: center !important;
        background-color: transparent !important; 
    }
    .schedule-time {
        text-align: right !important;
        font-weight: 500 !important;
        padding-right: 12px !important;
        color: #777777;
    }
    </style>
    """, unsafe_allow_html=True)

    # 顶栏结构
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(f"### 欢迎登录, {user_name}")
    with head_col2:
        with st.expander("📖 查看操作指南", expanded=False):
            st.markdown("1. 创建课程起止周组合<br>2. 选中周数标签<br>3. 点击网格填充/取消<br>4. 提交同步", unsafe_allow_html=True)

    df_colors, df_schedule = load_full_data()

    if "my_colors" not in st.session_state:
        my_colors, init_schedule, color_id_map = load_user_init_data(user_name, df_colors, df_schedule)
        if my_colors.empty:
            try:
                table_colors.create({
                    "StudentName": user_name, "StartWeek": 1, "EndWeek": 17, "ColorHex": "#e0f2fe"
                })
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"数据总线初始化失败：{e}")
                st.stop()
        st.session_state.my_colors = my_colors
        st.session_state.user_schedule = init_schedule
        st.session_state.color_id_map = color_id_map

    my_colors = st.session_state.my_colors
    user_schedule = st.session_state.user_schedule
    color_id_map = st.session_state.color_id_map

    st.markdown('<div class="module-spacer"></div>', unsafe_allow_html=True)

    # ---------------- 模块一：配置中心 ----------------
    st.markdown('<div class="section-title">课程组合配置</div>', unsafe_allow_html=True)
    
    week_options = []
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        week_options.append({
            "label": week_label, "record_id": row["RecordID"], "color_hex": row["ColorHex"]
        })

    if "selected_week" not in st.session_state:
        st.session_state.selected_week = week_options[0]["record_id"]

    select_cols = st.columns(min(len(week_options), 8))
    for idx, week_info in enumerate(week_options):
        with select_cols[idx % 8]:
            is_selected = st.session_state.selected_week == week_info["record_id"]
            
            hex_c = week_info['color_hex'].lstrip('#')
            rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
            text_color = "white" if (rgb[0]*0.299 + rgb[1]*0.587 + rgb[2]*0.114) < 186 else "#333333"
            
            st.markdown(f"""
            <style>
            #sel_{week_info['record_id']} > button {{
                background-color: {week_info['color_hex']} !important;
                color: {text_color} !important;
                border: 2px solid {'#333333' if is_selected else 'transparent'} !important;
                border-radius: 4px !important;
                height: 38px !important;
                line-height: 34px !important;
            }}
            </style>
            """, unsafe_allow_html=True)
            if st.button(week_info["label"], key=f"sel_{week_info['record_id']}", use_container_width=True):
                st.session_state.selected_week = week_info["record_id"]
                st.rerun()

    col_add1, col_add2, col_add3 = st.columns([2, 8, 2])
    with col_add1:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ 新增周期", use_container_width=True):
            st.session_state.show_add_week = not st.session_state.get("show_add_week", False)

    if st.session_state.get("show_add_week", False):
        with st.container():
            c1, c2, c3 = st.columns([2, 2, 2])
            with c1:
                s_w = st.number_input("开始周", min_value=1, max_value=30, value=1)
            with c2:
                e_w = st.number_input("结束周", min_value=1, max_value=30, value=17)
            with c3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("✅ 确认生成", type="primary", use_container_width=True):
                    existing_hexes = [w["color_hex"] for w in week_options]
                    new_hex = get_random_color(existing_hexes)
                    table_colors.create({
                        "StudentName": user_name, "StartWeek": int(s_w), "EndWeek": int(e_w), "ColorHex": new_hex
                    })
                    st.cache_data.clear()
                    for key in list(st.session_state.keys()):
                        if key not in ["user_name", "selected_week"]:
                            del st.session_state[key]
                    st.rerun()

    current_week = next(w for w in week_options if w["record_id"] == st.session_state.selected_week)
    current_cid, current_hex, current_label = current_week["record_id"], current_week["color_hex"], current_week["label"]

    st.markdown('<div class="module-spacer"></div>', unsafe_allow_html=True)

    # ---------------- 模块二：核心网格 ----------------
    st.markdown('<div class="section-title">排课视图</div>', unsafe_allow_html=True)
    
    header_cols = st.columns([1.5] + [1]*len(WEEKDAYS))
    header_cols[0].markdown(f'<div class="schedule-time">时间段</div>', unsafe_allow_html=True)
    for d, day in enumerate(WEEKDAYS):
        style_ext = "border-right: 1px solid #eaebec !important;" if d == len(WEEKDAYS)-1 else ""
        header_cols[d+1].markdown(f'<div class="schedule-header" style="{style_ext}">{day}</div>', unsafe_allow_html=True)

    total_periods = len(PERIODS)
    for row_idx, period in enumerate(PERIODS):
        is_last_row = row_idx == total_periods - 1
        row_cols = st.columns([1.5] + [1]*len(WEEKDAYS))
        
        time_style = "border-bottom: 1px solid #eaebec !important;" if is_last_row else ""
        row_cols[0].markdown(f'<div class="schedule-time" style="{time_style}">{period}</div>', unsafe_allow_html=True)
        
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{day}-{period}"
            button_key = f"btn_{cell_key}"
            is_last_col = d == len(WEEKDAYS)-1
            
            cell_data = user_schedule.get(cell_key, None)
            cell_cid, cell_hex, cell_label = (None, "transparent", "") if cell_data is None else cell_data

            btn_border_right = "border-right: 1px solid #eaebec !important;" if is_last_col else ""
            btn_border_bottom = "border-bottom: 1px solid #eaebec !important;" if is_last_row else ""
            
            if cell_hex != "transparent":
                h_c = cell_hex.lstrip('#')
                r, g, b = tuple(int(h_c[i:i+2], 16) for i in (0, 2, 4))
                cell_text_color = "white" if (r*0.299 + g*0.587 + b*0.114) < 186 else "#333333"
            else:
                cell_text_color = "transparent"

            st.markdown(f"""
            <style>
            #{button_key} > button {{
                background-color: {cell_hex} !important;
                color: {cell_text_color} !important;
                {btn_border_right}
                {btn_border_bottom}
            }}
            </style>
            """, unsafe_allow_html=True)

            with row_cols[d+1]:
                if st.button(cell_label if cell_label else "空", key=button_key, use_container_width=True):
                    if cell_cid == current_cid:
                        if cell_key in user_schedule:
                            del user_schedule[cell_key]
                    else:
                        user_schedule[cell_key] = (current_cid, current_hex, current_label)
                    st.session_state.user_schedule = user_schedule
                    st.rerun()

    st.markdown('<div class="module-spacer"></div>', unsafe_allow_html=True)

    # ---------------- 模块三：数据提交 ----------------
    op_cols = st.columns([6, 2, 2])
    with op_cols[1]:
        if st.button("🔄 丢弃本地修改", use_container_width=True):
            df_colors, df_schedule = load_full_data()
            _, init_schedule, _ = load_user_init_data(user_name, df_colors, df_schedule)
            st.session_state.user_schedule = init_schedule
            st.rerun()
            
    with op_cols[2]:
        if st.button("✅ 同步至云端", type="primary", use_container_width=True):
            try:
                with st.spinner("执行差量同步中..."):
                    existing_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
                    existing_map = {f"{r['fields']['Weekday']}-{r['fields']['Period']}": r for r in existing_records}

                    to_create, to_update, to_delete = [], [], []

                    for cell_key, (cid, _, _) in user_schedule.items():
                        if cell_key in existing_map:
                            if existing_map[cell_key]['fields'].get('ColorRecordID') != cid:
                                to_update.append({"id": existing_map[cell_key]['id'], "fields": {"ColorRecordID": cid}})
                            del existing_map[cell_key]
                        else:
                            weekday, period = cell_key.split("-", 1)
                            to_create.append({"StudentName": user_name, "Weekday": weekday, "Period": period, "ColorRecordID": cid})

                    to_delete = [r['id'] for r in existing_map.values()]

                    if to_create: table_schedule.batch_create(to_create)
                    if to_update: table_schedule.batch_update(to_update)
                    if to_delete: table_schedule.batch_delete(to_delete)

                    st.cache_data.clear()
                st.success("✅ 数据校验并写入成功。")
            except Exception as e:
                st.error(f"网络层发生异常：{e}")
