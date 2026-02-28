
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

table_colors = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Colors")
table_schedule = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Schedule")
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

def load_user_schedule(user_name, df_schedule):
    if df_schedule.empty or "StudentName" not in df_schedule.columns:
        return {}
    user_data = df_schedule[df_schedule["StudentName"] == user_name]
    schedule_dict = {}
    for _, row in user_data.iterrows():
        key = f"{row['Weekday']}-{row['Period']}"
        schedule_dict[key] = row["ColorRecordID"]
    return schedule_dict

# ================= 页面逻辑 =================
st.set_page_config(page_title="离线选课课表系统", layout="wide")

if "user_name" not in st.session_state:
    st.title("👋 欢迎使用离线选课课表系统")
    input_name = st.text_input("请输入你的名字（管理员请输入 admin）", max_chars=20)
    if st.button("进入系统", type="primary", use_container_width=True):
        if input_name.strip():
            st.session_state.user_name = input_name.strip()
            st.rerun()
    st.stop()

user_name = st.session_state.user_name

if user_name.lower() == "admin":
    # ==================================
    # 管理员界面（彻底修复 KeyError）
    # ==================================
    st.title("🔧 管理员总览控制台")
    df_colors, df_schedule = load_data()

    # 侧边栏周数筛选
    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=30, value=1)

    # 给每个学生分配唯一显示颜色
    all_students = []
    if not df_schedule.empty and "StudentName" in df_schedule.columns:
        all_students = df_schedule["StudentName"].unique().tolist()
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # ---------------- 视图1：当周有效课表汇总 ----------------
    st.subheader(f"📅 第 {target_week} 周 有效课表汇总")
    
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
            
            # [核心修复] 直接遍历原始 df_schedule，不依赖合并结果
            if not df_schedule.empty and set(["StudentName", "Weekday", "Period"]).issubset(df_schedule.columns):
                # 先找出这个时间点的所有记录
                cell_records = df_schedule[
                    (df_schedule["Weekday"] == day) & 
                    (df_schedule["Period"] == period)
                ]
                
                if not cell_records.empty:
                    for _, row in cell_records.iterrows():
                        s_name = "未知"
                        # 安全获取学生姓名
                        if "StudentName" in row and pd.notna(row["StudentName"]):
                            s_name = row["StudentName"]
                        
                        # 安全检查周数：只有当周有效才显示
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

    # ---------------- 视图2：当周集体空闲表 ----------------
    st.subheader(f"🕳️ 第 {target_week} 周 集体空闲时间表")
    st.caption("🟢 绿色 = 所有人都空闲；🔴 红色 = 至少1人有课")
    
    # 初始化空闲矩阵
    free_matrix = {p: {d: True for d in WEEKDAYS} for p in PERIODS}
    
    # 计算空闲状态
    if not df_schedule.empty and set(["StudentName", "Weekday", "Period", "ColorRecordID"]).issubset(df_schedule.columns):
        for _, row in df_schedule.iterrows():
            p = row["Period"]
            d = row["Weekday"]
            
            # 检查周数有效性
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
                f"<div style='background-color:{bg_color}; padding:10px; border-radius:5px; text-align:center; font-weight:bold;'>{label}</div>",
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
                st.success("✅ 数据库已全部清空！页面即将刷新...")
                st.rerun()
            except Exception as e:
                st.error(f"清空失败：{e}")
    elif input_pwd:
        st.error("密码错误，无法执行操作")

else:
    # ==================================
    # 学生界面（保持不变）
    # ==================================
    st.title(f"📝 你好，{user_name}")
    
    with st.expander("📖 使用说明", expanded=True):
        st.markdown("""
        1. 系统默认创建「黑色 1-17周」，可点击下方「➕」新增自定义周数的颜色
        2. 在下方「当前选中颜色」中选择要使用的颜色
        3. 直接点击课表格子，即可填入/清空当前选中的颜色，**本地操作无延迟**
        4. 全部选完后，点击「提交所有修改到服务器」，一次性同步所有选课数据
        """)

    df_colors, df_schedule = load_data()

    # ---------------- 1. 初始化默认颜色 ----------------
    my_colors = pd.DataFrame()
    if not df_colors.empty and "StudentName" in df_colors.columns:
        my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    
    if my_colors.empty:
        try:
            table_colors.create({
                "StudentName": user_name,
                "StartWeek": 1,
                "EndWeek": 17,
                "ColorHex": "#000000"
            })
            st.success("已为您创建默认颜色，页面即将刷新...")
            st.rerun()
        except Exception as e:
            st.error(f"初始化失败：{e}")
            st.stop()

    df_colors, df_schedule = load_data()
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()

    # ---------------- 2. 初始化本地缓存 ----------------
    if "user_schedule" not in st.session_state:
        st.session_state.user_schedule = load_user_schedule(user_name, df_schedule)
    if "selected_color" not in st.session_state:
        st.session_state.selected_color = None

    # ---------------- 3. 顶部颜色选择器 ----------------
    st.subheader("🎨 当前选中颜色")
    color_options = {}
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        display_text = f"{week_label}"
        color_options[display_text] = {
            "record_id": row["RecordID"],
            "color_hex": row["ColorHex"],
            "week_label": week_label
        }

    if st.session_state.selected_color not in color_options:
        st.session_state.selected_color = list(color_options.keys())[0]

    select_cols = st.columns(len(color_options))
    for idx, (display_text, color_info) in enumerate(color_options.items()):
        with select_cols[idx]:
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

    current_color_info = color_options[st.session_state.selected_color]
    current_color_id = current_color_info["record_id"]

    # ---------------- 4. 批量提交/重置 ----------------
    st.divider()
    op_cols = st.columns(2)
    with op_cols[0]:
        if st.button("✅ 提交所有修改到服务器", type="primary", use_container_width=True):
            try:
                old_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
                if old_records:
                    table_schedule.batch_delete([r["id"] for r in old_records])
                new_records = []
                for cell_key, color_id in st.session_state.user_schedule.items():
                    weekday, period = cell_key.split("-", 1)
                    new_records.append({
                        "StudentName": user_name,
                        "Weekday": weekday,
                        "Period": period,
                        "ColorRecordID": color_id
                    })
                if new_records:
                    table_schedule.batch_create(new_records)
                st.success("✅ 所有修改已同步到服务器！")
            except Exception as e:
                st.error(f"提交失败：{e}")
    with op_cols[1]:
        if st.button("🔄 重置本地修改", use_container_width=True):
            st.session_state.user_schedule = load_user_schedule(user_name, df_schedule)
            st.success("本地修改已重置为服务器最新数据")
            st.rerun()

    # ---------------- 5. 颜色管理区 ----------------
    st.divider()
    st.subheader("📌 我的颜色管理")
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

    # ---------------- 6. 课表网格 ----------------
    st.subheader("📅 课表（点击格子直接填色/清空，本地操作无延迟）")
    
    header_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1.2] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{day}-{period}"
            button_key = f"{user_name}_{cell_key}"
            
            cell_color_id = st.session_state.user_schedule.get(cell_key, None)
            cell_color_hex = "#f0f2f6"
            cell_label = ""
            
            if cell_color_id:
                color_match = my_colors[my_colors["RecordID"] == cell_color_id]
                if not color_match.empty:
                    cell_color_hex = color_match.iloc[0]["ColorHex"]
                    cell_label = f"{int(color_match.iloc[0]['StartWeek'])}-{int(color_match.iloc[0]['EndWeek'])}周"

            st.markdown(f"""
            <style>
            div.stButton > button[key="{button_key}"] {{
                background-color: {cell_color_hex};
                color: {'white' if cell_color_hex != '#f0f2f6' else '#333'};
                height: 55px;
                border: 1px solid #ddd;
            }}
            </style>
            """, unsafe_allow_html=True)

            with row_cols[d+1]:
                if st.button(cell_label, key=button_key, use_container_width=True):
                    if cell_color_id == current_color_id:
                        if cell_key in st.session_state.user_schedule:
                            del st.session_state.user_schedule[cell_key]
                    else:
                        st.session_state.user_schedule[cell_key] = current_color_id
                    st.rerun()
