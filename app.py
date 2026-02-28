
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
st.set_page_config(page_title="即点即选课表系统", layout="wide")

# 1. 登录界面
if "user_name" not in st.session_state:
    st.title("👋 欢迎使用即点即选课表系统")
    input_name = st.text_input("请输入你的名字（管理员请输入 admin）", max_chars=20)
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
    # 管理员界面（保持稳定，已修复所有报错）
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
                st.cache_data.clear()
                st.success("✅ 数据库已全部清空！页面即将刷新...")
                st.rerun()
            except Exception as e:
                st.error(f"清空失败：{e}")
    elif input_pwd:
        st.error("密码错误，无法执行操作")

else:
    # ==================================
    # 学生界面（核心：即点即选，零延迟）
    # ==================================
    st.title(f"📝 你好，{user_name}")
    
    with st.expander("📖 使用说明", expanded=True):
        st.markdown("""
        1. 先在下方「当前选中颜色」中，点击「选中」按钮选择要使用的周数颜色
        2. 直接点击课表格子，**立刻填入当前选中的颜色**，无任何弹窗和等待
        3. 再次点击同一个格子，**立刻清空**，恢复默认状态
        4. 所有操作均为本地编辑，全部选完后，点击底部「✅ 提交所有修改到服务器」完成同步
        """)

    # 加载全量数据（仅缓存加载，不随点击重复请求）
    df_colors, df_schedule = load_full_data()

    # ---------------- 1. 初始化用户数据（仅首次进入执行） ----------------
    if "my_colors" not in st.session_state:
        my_colors, init_schedule, color_id_map = load_user_init_data(user_name, df_colors, df_schedule)
        # 无颜色时自动创建默认黑色
        if my_colors.empty:
            try:
                table_colors.create({
                    "StudentName": user_name,
                    "StartWeek": 1,
                    "EndWeek": 17,
                    "ColorHex": "#000000"
                })
                st.cache_data.clear()
                st.success("已为您创建默认颜色，页面即将刷新...")
                st.rerun()
            except Exception as e:
                st.error(f"初始化失败：{e}")
                st.stop()
        # 存入session_state，后续仅修改本地缓存
        st.session_state.my_colors = my_colors
        st.session_state.user_schedule = init_schedule
        st.session_state.color_id_map = color_id_map

    # 从session_state读取数据，避免重复请求
    my_colors = st.session_state.my_colors
    user_schedule = st.session_state.user_schedule
    color_id_map = st.session_state.color_id_map

    # ---------------- 2. 顶部颜色选择器 ----------------
    st.subheader("🎨 当前选中颜色")
    # 构建颜色选项
    color_options = []
    for _, row in my_colors.iterrows():
        week_label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        color_options.append({
            "label": week_label,
            "record_id": row["RecordID"],
            "color_hex": row["ColorHex"]
        })

    # 初始化默认选中
    if "selected_color" not in st.session_state:
        st.session_state.selected_color = color_options[0]["record_id"]

    # 横向颜色选择按钮
    select_cols = st.columns(len(color_options))
    for idx, color_info in enumerate(color_options):
        with select_cols[idx]:
            is_selected = st.session_state.selected_color == color_info["record_id"]
            # 颜色预览
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:8px; margin-bottom:5px;'>"
                f"<div style='width:18px; height:18px; background-color:{color_info['color_hex']}; border:1px solid #ccc; border-radius:3px;'></div>"
                f"<span>{color_info['label']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            # 选中按钮
            if st.button(
                "选中",
                key=f"select_{color_info['record_id']}",
                type="primary" if is_selected else "secondary",
                use_container_width=True
            ):
                st.session_state.selected_color = color_info["record_id"]
                st.rerun()

    # 获取当前选中的颜色信息
    current_color = next(c for c in color_options if c["record_id"] == st.session_state.selected_color)
    current_cid = current_color["record_id"]
    current_hex = current_color["color_hex"]
    current_label = current_color["label"]

    # ---------------- 3. 新增自定义颜色 ----------------
    st.divider()
    st.subheader("📌 我的颜色管理")
    display_cols = st.columns(4)
    for idx, color_info in enumerate(color_options):
        with display_cols[idx % 4]:
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:10px;'>"
                f"<div style='background-color:{color_info['color_hex']}; width:20px; height:20px; border:1px solid #ccc;'></div>"
                f"<span>{color_info['label']}</span>"
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
            if st.form_submit_button("确认创建", use_container_width=True):
                existing_hexes = [c["color_hex"] for c in color_options]
                new_hex = get_random_color(existing_hexes)
                # 写入Airtable
                table_colors.create({
                    "StudentName": user_name,
                    "StartWeek": int(s_w),
                    "EndWeek": int(e_w),
                    "ColorHex": new_hex
                })
                # 清空缓存，刷新数据
                st.cache_data.clear()
                for key in list(st.session_state.keys()):
                    if key not in ["user_name", "selected_color"]:
                        del st.session_state[key]
                st.success("新颜色创建成功！页面即将刷新...")
                st.rerun()

    # ---------------- 4. 核心：即点即选课表网格 ----------------
    st.divider()
    st.subheader("📅 课表（点击直接填色/清空，零延迟）")
    
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
            cell_key = f"{day}-{period}"
            button_key = f"btn_{cell_key}"
            
            # 从本地缓存读取当前格子状态
            cell_data = user_schedule.get(cell_key, None)
            cell_cid, cell_hex, cell_label = (None, "#f0f2f6", "") if cell_data is None else cell_data

            # 自定义按钮样式
            st.markdown(f"""
            <style>
            div.stButton > button[key="{button_key}"] {{
                background-color: {cell_hex};
                color: {'white' if cell_hex != '#f0f2f6' else '#333'};
                height: 55px;
                border: 1px solid #ddd;
                white-space: pre-wrap;
            }}
            </style>
            """, unsafe_allow_html=True)

            # 点击按钮：仅修改本地缓存，无任何网络请求，毫秒级响应
            with row_cols[d+1]:
                if st.button(cell_label, key=button_key, use_container_width=True):
                    # 核心逻辑：点击切换
                    if cell_cid == current_cid:
                        # 再次点击，清空
                        if cell_key in user_schedule:
                            del user_schedule[cell_key]
                    else:
                        # 填入当前选中的颜色
                        user_schedule[cell_key] = (current_cid, current_hex, current_label)
                    # 更新session_state，刷新页面
                    st.session_state.user_schedule = user_schedule
                    st.rerun()

    # ---------------- 5. 提交到服务器按钮 ----------------
    st.divider()
    op_cols = st.columns(2)
    with op_cols[0]:
        if st.button("✅ 提交所有修改到服务器", type="primary", use_container_width=True):
            try:
                # 1. 删除该用户所有旧数据
                old_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
                if old_records:
                    table_schedule.batch_delete([r["id"] for r in old_records])
                # 2. 批量写入新数据
                new_records = []
                for cell_key, (cid, _, _) in user_schedule.items():
                    weekday, period = cell_key.split("-", 1)
                    new_records.append({
                        "StudentName": user_name,
                        "Weekday": weekday,
                        "Period": period,
                        "ColorRecordID": cid
                    })
                if new_records:
                    table_schedule.batch_create(new_records)
                # 清空缓存，更新数据
                st.cache_data.clear()
                st.success("✅ 所有修改已成功同步到服务器！")
            except Exception as e:
                st.error(f"提交失败：{e}")
    with op_cols[1]:
        if st.button("🔄 重置本地修改", use_container_width=True):
            # 重新从服务器加载数据，覆盖本地缓存
            df_colors, df_schedule = load_full_data()
            _, init_schedule, _ = load_user_init_data(user_name, df_colors, df_schedule)
            st.session_state.user_schedule = init_schedule
            st.success("本地修改已重置为服务器最新数据")
            st.rerun()
