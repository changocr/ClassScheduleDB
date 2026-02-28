import streamlit as st
import pandas as pd
import matplotlib.colors as mcolors
from pyairtable import Table
import random

# ================= 配置与常量 =================
# 课表时间段（完全匹配需求）
PERIODS = [
    "08:00~08:45", "08:55~09:40", "10:00~10:45", "10:55~11:40",
    "12:40~13:25", "13:35~14:20", "14:30~15:15", "15:25~16:10",
    "16:20~17:05", "17:15~18:00", "19:00~19:45", "19:55~20:40", "20:50~21:35"
]
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 从 Streamlit Secrets 读取密钥（部署时在设置里配置）
try:
    AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
except Exception as e:
    st.error(f"部署失败：请先在 Streamlit 后台配置 Secrets 密钥 | 错误信息：{e}")
    st.stop()

# 初始化 Airtable 表
table_colors = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Colors")
table_schedule = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Schedule")

# 颜色池（自动生成不重复的新颜色）
COLOR_POOL = list(mcolors.TABLEAU_COLORS.values()) + list(mcolors.CSS4_COLORS.values())

# ================= 辅助函数 =================
def get_random_color(existing_hexes):
    """生成不重复的随机颜色"""
    random.shuffle(COLOR_POOL)
    for color in COLOR_POOL:
        if color not in existing_hexes:
            return color
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def load_data():
    """加载Airtable数据，空表自动补全结构，避免KeyError"""
    # 加载颜色表
    colors_records = table_colors.all()
    if colors_records:
        df_colors = pd.DataFrame([r["fields"] for r in colors_records])
        df_colors["RecordID"] = [r["id"] for r in colors_records]
    else:
        df_colors = pd.DataFrame(columns=["StudentName", "StartWeek", "EndWeek", "ColorHex", "RecordID"])
    
    # 加载课表数据
    schedule_records = table_schedule.all()
    if schedule_records:
        df_schedule = pd.DataFrame([r["fields"] for r in schedule_records])
    else:
        df_schedule = pd.DataFrame(columns=["StudentName", "Weekday", "Period", "ColorRecordID"])
    
    return df_colors, df_schedule

# ================= 页面基础配置 =================
st.set_page_config(page_title="一键填色课表系统", layout="wide")

# 1. 登录界面（仅首次输入姓名）
if "user_name" not in st.session_state:
    st.title("👋 欢迎使用一键填色课表系统")
    input_name = st.text_input("请输入你的名字（管理员请输入 admin）", max_chars=20)
    if st.button("进入系统", type="primary", use_container_width=True):
        if input_name.strip():
            st.session_state.user_name = input_name.strip()
            st.rerun()
    st.stop()

user_name = st.session_state.user_name

# 2. 区分管理员/学生界面
if user_name.lower() == "admin":
    # ==================================
    # 管理员界面（完全保留原有功能）
    # ==================================
    st.title("🔧 管理员总览控制台")
    df_colors, df_schedule = load_data()

    # 合并课表与周数数据
    df_merged = pd.DataFrame()
    if not df_schedule.empty and not df_colors.empty:
        df_merged = pd.merge(df_schedule, df_colors, left_on="ColorRecordID", right_on="RecordID", how="left")
    elif not df_schedule.empty:
        df_merged = df_schedule.copy()

    # 侧边栏周数筛选
    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=30, value=1)

    # 给每个学生分配唯一显示颜色
    all_students = df_merged["StudentName"].unique().tolist() if "StudentName" in df_merged.columns else []
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # ---------------- 视图1：当周有效课表汇总 ----------------
    st.subheader(f"📅 第 {target_week} 周 有效课表汇总")
    # 过滤当周有效课程
    df_filtered = pd.DataFrame()
    if not df_merged.empty and "StartWeek" in df_merged.columns:
        df_filtered = df_merged[
            (df_merged["StartWeek"] <= target_week) & 
            (df_merged["EndWeek"] >= target_week)
        ]

    # 渲染课表网格
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

    # 初始化空闲矩阵
    free_matrix = {p: {d: True for d in WEEKDAYS} for p in PERIODS}
    # 标记有课的格子
    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            p = row["Period"]
            d = row["Weekday"]
            if p in free_matrix and d in free_matrix[p]:
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
                f"<div style='background-color:{bg_color}; padding:10px; border-radius:5px; text-align:center; font-weight:bold;'>{label}</div>",
                unsafe_allow_html=True
            )

else:
    # ==================================
    # 学生界面（核心新功能：一键填色）
    # ==================================
    st.title(f"📝 你好，{user_name}")
    
    # 使用说明
    with st.expander("📖 使用说明", expanded=True):
        st.markdown("""
        1. 系统默认创建「黑色 1-17周」，可点击下方「➕」新增自定义周数的颜色
        2. 在下方「当前选中颜色」中选择要使用的颜色
        3. 直接点击课表格子，即可填入当前选中的颜色；再次点击同一格子可清空
        4. 所有操作实时同步，无需二次确认
        """)

    # 加载最新数据
    df_colors, df_schedule = load_data()

    # ---------------- 1. 自动初始化默认颜色 ----------------
    my_colors = pd.DataFrame()
    if not df_colors.empty and "StudentName" in df_colors.columns:
        my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    
    # 无颜色时自动创建默认黑色
    if my_colors.empty:
        try:
            table_colors.create({
                "StudentName": user_name,
                "StartWeek": 1,
                "EndWeek": 17,
                "ColorHex": "#000000"
            })
            st.success("已为您创建默认颜色「黑色 1-17周」，页面即将刷新...")
            st.rerun()
        except Exception as e:
            st.error(f"初始化失败，请检查Airtable表字段名是否正确：{e}")
            st.stop()

    # 重新加载确保拿到最新颜色数据
    df_colors, df_schedule = load_data()
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()

    # ---------------- 2. 顶部颜色选择器（核心改动） ----------------
    st.subheader("🎨 当前选中颜色")
    # 构建颜色选项：{显示文本: 颜色RecordID}
    color_options = {}
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        display_text = f"{week_label}"
        color_options[display_text] = {
            "record_id": row["RecordID"],
            "color_hex": row["ColorHex"],
            "week_label": week_label
        }

    # 初始化默认选中的颜色
    if "selected_color" not in st.session_state or st.session_state.selected_color not in color_options:
        st.session_state.selected_color = list(color_options.keys())[0]

    # 横向排列颜色单选按钮（带颜色预览）
    select_cols = st.columns(len(color_options))
    for idx, (display_text, color_info) in enumerate(color_options.items()):
        with select_cols[idx]:
            # 带颜色预览的单选按钮
            is_selected = st.session_state.selected_color == display_text
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:8px; margin-bottom:5px;'>"
                f"<div style='width:18px; height:18px; background-color:{color_info['color_hex']}; border:1px solid #ccc; border-radius:3px;'></div>"
                f"<span>{display_text}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            if st.button("选中", key=f"select_{color_info['record_id']}", type="primary" if is_selected else "secondary", use_container_width=True):
                st.session_state.selected_color = display_text
                st.rerun()

    # 获取当前选中的颜色信息
    current_color_info = color_options[st.session_state.selected_color]
    current_color_id = current_color_info["record_id"]
    current_color_hex = current_color_info["color_hex"]
    current_week_label = current_color_info["week_label"]

    # ---------------- 3. 颜色管理区（新增自定义颜色） ----------------
    st.divider()
    st.subheader("📌 我的颜色管理")
    
    # 显示所有颜色
    display_cols = st.columns(4)
    for idx, (_, row) in enumerate(my_colors.iterrows()):
        with display_cols[idx % 4]:
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:10px;'>"
                f"<div style='background-color:{row['ColorHex']}; width:20px; height:20px; border:1px solid #ccc;'></div>"
                f"<span>{int(row['StartWeek'])}-{int(row['EndWeek'])}周</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    # 新增颜色按钮
    if st.button("➕ 新增自定义周数颜色", use_container_width=True):
        st.session_state.show_add_color = not st.session_state.get("show_add_color", False)

    if st.session_state.get("show_add_color", False):
        with st.form("add_color_form"):
            st.write("新增颜色配置")
            s_w = st.number_input("开始周", min_value=1, max_value=30, value=1)
            e_w = st.number_input("结束周", min_value=1, max_value=30, value=17)
            submitted = st.form_submit_button("确认创建", use_container_width=True)
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
                st.success("新颜色创建成功！")
                st.rerun()

    st.divider()

    # ---------------- 4. 课表网格（一键填色，无弹窗） ----------------
    st.subheader("📅 课表（点击格子直接填色/清空）")
    
    # 渲染课表表头
    header_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    # 逐行渲染课表
    for period in PERIODS:
        row_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{user_name}_{day}_{period}"
            
            # 查询当前格子的已有数据
            cell_record_id = None
            cell_color_hex = "#f0f2f6"
            cell_label = ""
            
            if not df_schedule.empty and set(["StudentName", "Weekday", "Period"]).issubset(df_schedule.columns):
                my_record = df_schedule[
                    (df_schedule["StudentName"] == user_name) &
                    (df_schedule["Weekday"] == day) &
                    (df_schedule["Period"] == period)
                ]
                if not my_record.empty:
                    cell_color_id = my_record.iloc[0]['ColorRecordID']
                    cell_record_id = my_record.index[0]
                    # 匹配颜色信息
                    color_match = my_colors[my_colors["RecordID"] == cell_color_id]
                    if not color_match.empty:
                        cell_color_hex = color_match.iloc[0]["ColorHex"]
                        cell_label = f"{int(color_match.iloc[0]['StartWeek'])}-{int(color_match.iloc[0]['EndWeek'])}周"

            # 自定义按钮样式（匹配当前颜色）
            st.markdown(f"""
            <style>
            div.stButton > button[key="{cell_key}"] {{
                background-color: {cell_color_hex};
                color: {'white' if cell_color_hex != '#f0f2f6' else '#333333'};
                height: 55px;
                white-space: pre-wrap;
                border: 1px solid #ddd;
            }}
            </style>
            """, unsafe_allow_html=True)

            # 点击按钮直接执行填色/清空操作
            with row_cols[d+1]:
                if st.button(cell_label, key=cell_key, use_container_width=True):
                    # 核心逻辑：点击直接操作，无二次确认
                    formula = f"AND({{StudentName}}='{user_name}', {{Weekday}}='{day}', {{Period}}='{period}')"
                    try:
                        # 先删除旧记录
                        old_records = table_schedule.all(formula=formula)
                        for r in old_records:
                            table_schedule.delete(r['id'])
                        
                        # 判断：如果当前格子不是选中的颜色，就写入新颜色；否则保持删除（清空）
                        if cell_color_id != current_color_id:
                            table_schedule.create({
                                "StudentName": user_name,
                                "Weekday": day,
                                "Period": period,
                                "ColorRecordID": current_color_id
                            })
                    except Exception as e:
                        st.error(f"操作失败：{e}")
                    
                    # 刷新页面显示最新状态
                    st.rerun()
