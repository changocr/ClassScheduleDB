
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

# 从 Streamlit Secrets 读取密钥
try:
    AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
except Exception as e:
    st.error(f"部署失败：请先在 Streamlit 后台配置 Secrets 密钥 | 错误信息：{e}")
    st.stop()

# 初始化 Airtable 表
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
st.set_page_config(page_title="课表系统", layout="wide")

# 1. 登录界面
if "user_name" not in st.session_state:
    st.title("👋 欢迎使用课表系统")
    input_name = st.text_input("请输入你的名字", max_chars=20)
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
    # 管理员界面
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
                            html_content += f"<div style='background-color:{bg_color}; color:{text_color}; padding:2px; margin:1px; border-radius:3px;'>{s_name}</div>"
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
            bg_color = "#90EE90" if is_free else "#FFB6C1"
            label = "空闲" if is_free else "有课"
            row_cols[d+1].markdown(
                f"<div style='background-color:{bg_color}; padding:10px; border-radius:0; border:1px solid #ccc; border-right:none; text-align:center; font-weight:bold; height:34px; line-height:14px;'>{label}</div>",
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
    # 学生界面
    # ==================================
    st.write(f"**你好，{user_name}**")
    
    with st.expander("使用说明", expanded=False):
        st.markdown("""
        1. 首先根据课表创建所有课程的起止周组合
        2. 点击下方周数条选中，然后点击课表格子填入
        3. 再次点击格子可清空
        4. 全部选完后，点击底部「提交」完成同步
        """)

    df_colors, df_schedule = load_full_data()

    if "my_colors" not in st.session_state:
        my_colors, init_schedule, color_id_map = load_user_init_data(user_name, df_colors, df_schedule)
        if my_colors.empty:
            try:
                table_colors.create({
                    "StudentName": user_name, "StartWeek": 1, "EndWeek": 17, "ColorHex": "#000000"
                })
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"初始化失败：{e}")
                st.stop()
        st.session_state.my_colors = my_colors
        st.session_state.user_schedule = init_schedule
        st.session_state.color_id_map = color_id_map

    my_colors = st.session_state.my_colors
    user_schedule = st.session_state.user_schedule
    color_id_map = st.session_state.color_id_map

    # ---------------- 顶部：周数选择器 ----------------
    st.caption("📌 当前选中周数：")
    week_options = []
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        week_options.append({
            "label": week_label,
            "record_id": row["RecordID"],
            "color_hex": row["ColorHex"]
        })

    if "selected_week" not in st.session_state:
        st.session_state.selected_week = week_options[0]["record_id"]

    select_cols = st.columns(len(week_options))
    for idx, week_info in enumerate(week_options):
        with select_cols[idx]:
            is_selected = st.session_state.selected_week == week_info["record_id"]
            st.markdown(f"""
            <style>
            #sel_{week_info['record_id']} > button {{
                background-color: {week_info['color_hex']} !important;
                color: {'white' if is_selected else '#333'} !important;
                border: 2px solid {'#0066ff' if is_selected else '#ccc'} !important;
                height: 28px;
                padding: 0 4px;
                font-size: 0.8em;
            }}
            </style>
            """, unsafe_allow_html=True)
            if st.button(week_info["label"], key=f"sel_{week_info['record_id']}", use_container_width=True):
                st.session_state.selected_week = week_info["record_id"]
                st.rerun()

    current_week = next(w for w in week_options if w["record_id"] == st.session_state.selected_week)
    current_cid = current_week["record_id"]
    current_hex = current_week["color_hex"]
    current_label = current_week["label"]

    # ---------------- 新增周数组合 ----------------
    st.write("")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("➕ 新增周数组合", use_container_width=True):
            st.session_state.show_add_week = not st.session_state.get("show_add_week", False)

    if st.session_state.get("show_add_week", False):
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                s_w = st.number_input("开始周", min_value=1, max_value=30, value=1, label_visibility="collapsed")
            with c2:
                e_w = st.number_input("结束周", min_value=1, max_value=30, value=17, label_visibility="collapsed")
            with c3:
                if st.button("确认创建", use_container_width=True):
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

    # ---------------- 核心：零间距课表网格样式注入 ----------------
    # 仅在学生端界面注入，穿透 Streamlit 底层布局限制
    st.markdown("""
    <style>
    /* 清除所有网格容器间距 */
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    [data-testid="stHorizontalBlock"] { gap: 0 !important; }
    [data-testid="column"] { padding: 0 !important; gap: 0 !important; }
    [data-testid="element-container"] { margin-bottom: 0 !important; }
    
    /* 基础按钮：重置为 Excel 单元格风格 */
    .stButton > button {
        width: 100% !important;
        height: 34px !important;
        border-radius: 0 !important;
        border: 1px solid #ccc !important;
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.75em !important;
        line-height: 34px !important;
        min-height: unset !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    .stMarkdown p { margin: 0 !important; padding: 0 !important; }
    
    /* 表头与时间轴样式 */
    .schedule-header, .schedule-time {
        height: 34px !important;
        line-height: 34px !important;
        border: 1px solid #ccc !important;
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.85em !important;
        text-align: center !important;
        background-color: #f5f5f5;
    }
    .schedule-time {
        text-align: right !important;
        font-weight: normal !important;
        background-color: transparent !important;
        padding-right: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.write("")
    st.caption("📅 课表：")
    
    # 渲染表头
    header_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
    header_cols[0].markdown(f'<div class="schedule-time">时间</div>', unsafe_allow_html=True)
    for d, day in enumerate(WEEKDAYS):
        # 最后一列单独补齐右边框，避免叠加
        style_ext = "border-right: 1px solid #ccc !important;" if d == len(WEEKDAYS)-1 else ""
        header_cols[d+1].markdown(f'<div class="schedule-header" style="{style_ext}">{day}</div>', unsafe_allow_html=True)

    # 渲染课表主体
    total_periods = len(PERIODS)
    for row_idx, period in enumerate(PERIODS):
        is_last_row = row_idx == total_periods - 1
        row_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
        
        # 渲染时间单元格
        time_style = "border-bottom: 1px solid #ccc !important;" if is_last_row else ""
        row_cols[0].markdown(f'<div class="schedule-time" style="{time_style}">{period}</div>', unsafe_allow_html=True)
        
        # 渲染交互网格
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{day}-{period}"
            button_key = f"btn_{cell_key}"
            is_last_col = d == len(WEEKDAYS)-1
            
            cell_data = user_schedule.get(cell_key, None)
            cell_cid, cell_hex, cell_label = (None, "#f0f2f6", "") if cell_data is None else cell_data

            # 动态计算边界线样式与背景色
            btn_border_right = "border-right: 1px solid #ccc !important;" if is_last_col else ""
            btn_border_bottom = "border-bottom: 1px solid #ccc !important;" if is_last_row else ""
            
            st.markdown(f"""
            <style>
            #{button_key} > button {{
                background-color: {cell_hex} !important;
                color: {'white' if cell_hex != '#f0f2f6' else '#333'} !important;
                {btn_border_right}
                {btn_border_bottom}
            }}
            </style>
            """, unsafe_allow_html=True)

            with row_cols[d+1]:
                if st.button(cell_label, key=button_key):
                    if cell_cid == current_cid:
                        if cell_key in user_schedule:
                            del user_schedule[cell_key]
                    else:
                        user_schedule[cell_key] = (current_cid, current_hex, current_label)
                    st.session_state.user_schedule = user_schedule
                    st.rerun()

    # ---------------- 底部提交按钮 (差量更新逻辑) ----------------
    st.write("")
    op_cols = st.columns(2)
    with op_cols[0]:
        if st.button("✅ 提交所有修改", type="primary", use_container_width=True):
            try:
                # 1. 获取线上该用户的全部记录，构建哈希映射
                existing_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
                existing_map = {f"{r['fields']['Weekday']}-{r['fields']['Period']}": r for r in existing_records}

                to_create, to_update, to_delete = [], [], []

                # 2. 对比当前本地状态与线上状态
                for cell_key, (cid, _, _) in user_schedule.items():
                    if cell_key in existing_map:
                        # 线上存在，检查颜色分类是否变更
                        if existing_map[cell_key]['fields'].get('ColorRecordID') != cid:
                            to_update.append({"id": existing_map[cell_key]['id'], "fields": {"ColorRecordID": cid}})
                        del existing_map[cell_key] # 匹配成功，从字典中移除
                    else:
                        # 线上不存在，标记为新增
                        weekday, period = cell_key.split("-", 1)
                        to_create.append({"StudentName": user_name, "Weekday": weekday, "Period": period, "ColorRecordID": cid})

                # 3. 留在映射中的记录即为本地已删除的课程
                to_delete = [r['id'] for r in existing_map.values()]

                # 4. 执行批量网络请求
                if to_create:
                    table_schedule.batch_create(to_create)
                if to_update:
                    table_schedule.batch_update(to_update)
                if to_delete:
                    table_schedule.batch_delete(to_delete)

                st.cache_data.clear()
                st.success("✅ 差异同步完成！数据已安全写入服务器。")
            except Exception as e:
                st.error(f"提交失败：{e}")
                
    with op_cols[1]:
        if st.button("🔄 重置本地修改", use_container_width=True):
            df_colors, df_schedule = load_full_data()
            _, init_schedule, _ = load_user_init_data(user_name, df_colors, df_schedule)
            st.session_state.user_schedule = init_schedule
            st.rerun()
