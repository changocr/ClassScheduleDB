
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

# 初始化 Airtable 表（仅全局初始化一次，不随点击重复执行）
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
    """加载全量数据，缓存30秒，避免重复请求"""
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
    """加载用户初始数据，仅首次进入执行"""
    # 加载用户颜色配置
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    # 加载用户已有课表，转为本地字典格式：{weekday-period: (color_id, color_hex, week_label)}
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

# 全局无缝表格CSS（核心：完全依靠CSS消除间距）
st.markdown("""
<style>
/* 强制消除所有列间距 */
[data-testid="column"] {
    padding: 0 !important;
    margin: 0 !important;
}
/* 课表按钮：Excel无缝单元格样式 */
.schedule-btn > button {
    width: 100% !important;
    height: 32px !important;
    margin: 0 !important;
    padding: 0 !important;
    border-radius: 0 !important;
    border: 1px solid #ccc !important;
    border-right: none !important;
    border-bottom: none !important;
    font-size: 0.75em !important;
    line-height: 32px !important;
    min-height: unset !important;
}
/* 最后一列补右边框 */
.schedule-btn-last > button {
    border-right: 1px solid #ccc !important;
}
/* 最后一行补下边框 */
.schedule-row-last .schedule-btn > button {
    border-bottom: 1px solid #ccc !important;
}
/* 表头样式 */
.schedule-header {
    height: 32px !important;
    line-height: 32px !important;
    margin: 0 !important;
    padding: 0 4px !important;
    border: 1px solid #ccc !important;
    border-right: none !important;
    border-bottom: none !important;
    font-weight: bold !important;
    font-size: 0.85em !important;
    text-align: center !important;
    background-color: #f5f5f5;
}
.schedule-header-last {
    border-right: 1px solid #ccc !important;
}
/* 时间列样式 */
.schedule-time {
    height: 32px !important;
    line-height: 32px !important;
    margin: 0 !important;
    padding: 0 4px !important;
    border: 1px solid #ccc !important;
    border-right: none !important;
    border-bottom: none !important;
    font-size: 0.75em !important;
    text-align: right !important;
}
.schedule-time-last {
    border-bottom: 1px solid #ccc !important;
}
</style>
""", unsafe_allow_html=True)

# 1. 登录界面
if "user_name" not in st.session_state:
    st.title("👋 欢迎使用课表系统")
    input_name = st.text_input("请输入你的名字", max_chars=20)
    if st.button("进入系统", type="primary", use_container_width=True):
        if input_name.strip():
            st.session_state.user_name = input_name.strip()
            # 清空之前的编辑缓存，避免串数据
            for key in list(st.session_state.keys()):
                if key not in ["user_name"]:
                    del st.session_state[key]
            st.rerun()
    st.stop()

user_name = st.session_state.user_name

# 2. 区分管理员/学生界面
if user_name.lower() == "admin":
    # ==================================
    # 管理员界面（保持不变）
    # ==================================
    st.title("🔧 管理员总览控制台")
    df_colors, df_schedule = load_full_data()

    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=30, value=1)

    # 给每个学生分配唯一显示颜色
    all_students = []
    if not df_schedule.empty and "StudentName" in df_schedule.columns:
        all_students = df_schedule["StudentName"].unique().tolist()
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # ---------------- 视图1：当周有效课表汇总 ----------------
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
                        # 周数有效性校验
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

    # ---------------- 视图2：当周集体空闲表 ----------------
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

    # 渲染空闲表
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
                f"<div style='background-color:{bg_color}; padding:10px; border-radius:0; border:1px solid #ccc; border-right:none; text-align:center; font-weight:bold; height:32px; line-height:12px;'>{label}</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # ---------------- 一键清空数据库 ----------------
    st.subheader("⚠️ 危险操作：清空全部数据库")
    st.caption("此操作会删除所有学生的颜色配置和课表数据，无法恢复，请谨慎操作！")
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
    # 学生界面（Excel无缝极致紧凑版）
    # ==================================
    st.write(f"**你好，{user_name}**")
    
    # 使用说明（折叠紧凑版）
    with st.expander("使用说明", expanded=False):
        st.markdown("""
        1. 每种颜色代表一组课程起止周，先创建所有课程的起止周组合
        2. 点击下方颜色条选中颜色，点击课表格子填入
        3. 再次点击格子可清空
        4. 全部选完后，点击底部「提交」完成同步
        """)

    # 加载全量数据
    df_colors, df_schedule = load_full_data()

    # ---------------- 1. 初始化用户数据 ----------------
    if "my_colors" not in st.session_state:
        my_colors, init_schedule, color_id_map = load_user_init_data(user_name, df_colors, df_schedule)
        if my_colors.empty:
            try:
                table_colors.create({
                    "StudentName": user_name,
                    "StartWeek": 1,
                    "EndWeek": 17,
                    "ColorHex": "#000000"
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

    # ---------------- 2. 顶部颜色选择器（极致紧凑版） ----------------
    st.caption("🎨 点击选择颜色：")
    
    # 构建颜色选项
    color_options = []
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        color_options.append({
            "label": week_label,
            "record_id": row["RecordID"],
            "color_hex": row["ColorHex"]
        })

    if "selected_color" not in st.session_state:
        st.session_state.selected_color = color_options[0]["record_id"]

    # 紧凑横向排列
    select_cols = st.columns(len(color_options))
    for idx, color_info in enumerate(color_options):
        with select_cols[idx]:
            is_selected = st.session_state.selected_color == color_info["record_id"]
            # 自定义颜色按钮样式
            st.markdown(f"""
            <style>
            #sel_{color_info['record_id']} > button {{
                background-color: {color_info['color_hex']} !important;
                color: {'white' if is_selected else '#333'} !important;
                border: 2px solid {'#0066ff' if is_selected else '#ccc'} !important;
                height: 28px;
                padding: 0 4px;
                font-size: 0.8em;
            }}
            </style>
            """, unsafe_allow_html=True)
            if st.button(
                color_info["label"],
                key=f"sel_{color_info['record_id']}",
                use_container_width=True
            ):
                st.session_state.selected_color = color_info["record_id"]
                st.rerun()

    # 获取当前选中颜色
    current_color = next(c for c in color_options if c["record_id"] == st.session_state.selected_color)
    current_cid = current_color["record_id"]
    current_hex = current_color["color_hex"]
    current_label = current_color["label"]

    # ---------------- 3. 新增自定义颜色（紧凑版） ----------------
    st.write("")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("➕ 新增周数颜色", use_container_width=True):
            st.session_state.show_add_color = not st.session_state.get("show_add_color", False)

    if st.session_state.get("show_add_color", False):
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                s_w = st.number_input("开始周", min_value=1, max_value=30, value=1, label_visibility="collapsed")
            with c2:
                e_w = st.number_input("结束周", min_value=1, max_value=30, value=17, label_visibility="collapsed")
            with c3:
                if st.button("确认创建", use_container_width=True):
                    existing_hexes = [c["color_hex"] for c in color_options]
                    new_hex = get_random_color(existing_hexes)
                    table_colors.create({
                        "StudentName": user_name, "StartWeek": int(s_w), "EndWeek": int(e_w), "ColorHex": new_hex
                    })
                    st.cache_data.clear()
                    for key in list(st.session_state.keys()):
                        if key not in ["user_name", "selected_color"]:
                            del st.session_state[key]
                    st.rerun()

    # ---------------- 4. 核心：Excel无缝课表网格 ----------------
    st.write("")
    st.caption("📅 课表：")
    
    # 课表容器
    with st.container():
        # 表头行
        header_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
        header_cols[0].markdown(f'<div class="schedule-header">时间</div>', unsafe_allow_html=True)
        for d, day in enumerate(WEEKDAYS):
            last_class = "schedule-header-last" if d == len(WEEKDAYS)-1 else ""
            header_cols[d+1].markdown(f'<div class="schedule-header {last_class}">{day}</div>', unsafe_allow_html=True)

        # 逐行渲染课表
        total_periods = len(PERIODS)
        for row_idx, period in enumerate(PERIODS):
            is_last_row = row_idx == total_periods - 1
            row_class = "schedule-row-last" if is_last_row else ""
            row_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
            
            # 时间列
            time_class = "schedule-time-last" if is_last_row else ""
            row_cols[0].markdown(f'<div class="schedule-time {time_class}">{period}</div>', unsafe_allow_html=True)
            
            # 课表单元格
            for d, day in enumerate(WEEKDAYS):
                cell_key = f"{day}-{period}"
                button_key = f"btn_{cell_key}"
                is_last_col = d == len(WEEKDAYS)-1
                btn_class = "schedule-btn-last" if is_last_col else ""
                
                # 读取单元格状态
                cell_data = user_schedule.get(cell_key, None)
                cell_cid, cell_hex, cell_label = (None, "#f0f2f6", "") if cell_data is None else cell_data

                # 动态按钮样式
                st.markdown(f"""
                <style>
                #{button_key} > button {{
                    background-color: {cell_hex} !important;
                    color: {'white' if cell_hex != '#f0f2f6' else '#333'} !important;
                }}
                </style>
                """, unsafe_allow_html=True)

                # 渲染无缝按钮
                with row_cols[d+1]:
                    st.markdown(f'<div class="schedule-btn {btn_class} {row_class}">', unsafe_allow_html=True)
                    if st.button(cell_label, key=button_key):
                        # 核心点击逻辑
                        if cell_cid == current_cid:
                            if cell_key in user_schedule:
                                del user_schedule[cell_key]
                        else:
                            user_schedule[cell_key] = (current_cid, current_hex, current_label)
                        st.session_state.user_schedule = user_schedule
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- 5. 底部提交按钮 ----------------
    st.write("")
    op_cols = st.columns(2)
    with op_cols[0]:
        if st.button("✅ 提交所有修改", type="primary", use_container_width=True):
            try:
                old_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
                if old_records:
                    table_schedule.batch_delete([r["id"] for r in old_records])
                new_records = []
                for cell_key, (cid, _, _) in user_schedule.items():
                    weekday, period = cell_key.split("-", 1)
                    new_records.append({
                        "StudentName": user_name, "Weekday": weekday, "Period": period, "ColorRecordID": cid
                    })
                if new_records:
                    table_schedule.batch_create(new_records)
                st.cache_data.clear()
                st.success("✅ 已同步到服务器！")
            except Exception as e:
                st.error(f"提交失败：{e}")
    with op_cols[1]:
        if st.button("🔄 重置本地修改", use_container_width=True):
            df_colors, df_schedule = load_full_data()
            _, init_schedule, _ = load_user_init_data(user_name, df_colors, df_schedule)
            st.session_state.user_schedule = init_schedule
            st.rerun()
