import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pyairtable import Table
import random

# ================= 配置与常量 =================
# 课表时间
PERIODS = [
    "08:00~08:45", "08:55~09:40", "10:00~10:45", "10:55~11:40",
    "12:40~13:25", "13:35~14:20", "14:30~15:15", "15:25~16:10",
    "16:20~17:05", "17:15~18:00", "19:00~19:45", "19:55~20:40", "20:50~21:35"
]
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 从 Streamlit Secrets 读取密钥 (部署时在设置里配)
# 本地运行时，请直接把字符串填在下面，或者建个 .streamlit/secrets.toml
try:
    AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
except:
    # 本地调试临时填入区域
    AIRTABLE_API_KEY = "pat你的token" 
    AIRTABLE_BASE_ID = "app你的BaseID"

# 初始化 Airtable 表
table_colors = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Colors")
table_schedule = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, "Schedule")

# 颜色池（用于自动分配新颜色）
COLOR_POOL = list(mcolors.TABLEAU_COLORS.values()) + list(mcolors.CSS4_COLORS.values())

# ================= 辅助函数 =================

def get_random_color(existing_hexes):
    """获取一个不重复的随机颜色"""
    random.shuffle(COLOR_POOL)
    for color in COLOR_POOL:
        if color not in existing_hexes:
            return color
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def load_data(student_name=None):
    """从 Airtable 加载数据"""
    colors_records = table_colors.all()
    schedule_records = table_schedule.all()
    
    # 转成 DataFrame 方便处理
    df_colors = pd.DataFrame([r["fields"] for r in colors_records])
    df_colors["RecordID"] = [r["id"] for r in colors_records]
    
    df_schedule = pd.DataFrame([r["fields"] for r in schedule_records])
    
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
    
    # 合并数据，把周数信息合并到课表里
    if not df_schedule.empty and not df_colors.empty:
        df_merged = pd.merge(df_schedule, df_colors, left_on="ColorRecordID", right_on="RecordID", how="left")
    else:
        df_merged = pd.DataFrame(columns=["StudentName", "Weekday", "Period", "StartWeek", "EndWeek"])

    # 侧边栏：选择周数
    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=20, value=1)

    # 给每个学生分配一个独特的颜色（用于管理员视图）
    all_students = df_merged["StudentName"].unique().tolist()
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

    # ---------------- 视图 1: 当周汇总课表 ----------------
    st.subheader(f"📅 第 {target_week} 周 实际课表")
    
    # 过滤数据：只显示 StartWeek <= target_week <= EndWeek 的课
    if not df_merged.empty:
        df_filtered = df_merged[
            (df_merged["StartWeek"] <= target_week) & 
            (df_merged["EndWeek"] >= target_week)
        ]
    else:
        df_filtered = pd.DataFrame()

    # 渲染课表
    header_cols = st.columns([1] + [1]*len(WEEKDAYS))
    header_cols[0].markdown("**时间**")
    for d, day in enumerate(WEEKDAYS):
        header_cols[d+1].markdown(f"**{day}**")

    for period in PERIODS:
        row_cols = st.columns([1] + [1]*len(WEEKDAYS))
        row_cols[0].write(period)
        
        for d, day in enumerate(WEEKDAYS):
            # 找出这个格子里的学生
            cell_data = df_filtered[
                (df_filtered["Weekday"] == day) & 
                (df_filtered["Period"] == period)
            ]
            
            html_content = "<div style='font-size:0.8em; line-height:1.2;'>"
            if not cell_data.empty:
                for _, row in cell_data.iterrows():
                    s_name = row['StudentName']
                    bg_color = student_color_map.get(s_name, "#eee")
                    # 计算文字颜色（黑或白）
                    rgb = mcolors.hex2color(bg_color)
                    text_color = "white" if (rgb[0]*rgb[1]*rgb[2]) < 0.5 else "black"
                    
                    html_content += f"<div style='background-color:{bg_color}; color:{text_color}; padding:2px; margin:1px; border-radius:3px;'>{s_name}</div>"
            
            html_content += "</div>"
            row_cols[d+1].markdown(html_content, unsafe_allow_html=True)

    st.divider()

    # ---------------- 视图 2: 集体空闲时间涂色表 ----------------
    st.subheader(f"🕳️ 第 {target_week} 周 集体空闲表")
    st.caption("🟢 绿色 = 所有人都有空；🔴 红色 = 至少有1人有课")

    # 构建空闲矩阵
    free_matrix = {}
    
    # 先把所有格子初始化为 True (空闲)
    for period in PERIODS:
        free_matrix[period] = {}
        for day in WEEKDAYS:
            free_matrix[period][day] = True

    # 遍历有课的数据，把对应格子标为 False
    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            p = row["Period"]
            d = row["Weekday"]
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
            color = "#90EE90" if is_free else "#FFB6C1" # 浅绿/浅红
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
    
    # 顶部说明
    with st.expander("📖 使用说明"):
        st.markdown("""
        1. 系统默认已有「黑色 (1-17周)」。
        2. 点击下方 ➕ 号可以新增属于你的颜色和周数范围。
        3. 在课表中点击格子，选择一个颜色即可占位。
        4. 再次点击格子可以修改或删除。
        """)

    df_colors, df_schedule = load_data()

    # ---------------- 1. 颜色管理区 ----------------
    st.subheader("🎨 我的颜色与周数")
    
    # 筛选出当前学生的颜色
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    
    # 如果没有颜色，创建默认黑色 (1-17周)
    if my_colors.empty:
        default_color = table_colors.create({
            "StudentName": user_name,
            "StartWeek": 1,
            "EndWeek": 17,
            "ColorHex": "#000000" # 黑色
        })
        st.success("已为您创建默认黑色 (1-17周)，请刷新页面。")
        st.rerun()

    # 显示现有颜色
    col1, col2, col3, col4 = st.columns(4)
    for idx, row in my_colors.iterrows():
        with col1:
            st.markdown(f"<div style='background-color:{row['ColorHex']}; width:20px; height:20px; display:inline-block; border:1px solid #ccc;'></div> {row['StartWeek']}-{row['EndWeek']}周", unsafe_allow_html=True)

    # 新增颜色按钮
    if st.button("➕ 新增颜色周数"):
        existing_hexes = my_colors['ColorHex'].tolist()
        new_hex = get_random_color(existing_hexes)
        
        # 弹窗让用户填周数 (这里用 st.number_input 模拟，Streamlit 原生弹窗体验一般，用页面内交互)
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

    # ---------------- 2. 课表点击区 ----------------
    st.subheader("📅 点击课表占位")
    
    # 重新加载最新颜色数据
    df_colors, df_schedule = load_data()
    my_colors = df_colors[df_colors["StudentName"] == user_name]
    
    # 构建我的颜色选项字典 {RecordID: "颜色预览 1-10周"}
    my_color_options = {}
    for _, r in my_colors.iterrows():
        label = f"{r['StartWeek']}-{r['EndWeek']}周"
        my_color_options[r['RecordID']] = (r['ColorHex'], label)

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
            
            # 查找我在这个格子有没有记录
            my_record = df_schedule[
                (df_schedule["StudentName"] == user_name) &
                (df_schedule["Weekday"] == day) &
                (df_schedule["Period"] == period)
            ]
            
            current_color_id = my_record.iloc[0]['ColorRecordID'] if not my_record.empty else None
            current_hex = "#f0f2f6"
            current_label = ""
            
            if current_color_id and current_color_id in my_color_options:
                current_hex = my_color_options[current_color_id][0]
                current_label = my_color_options[current_color_id][1]

            # 渲染按钮
            with row_cols[d+1]:
                # 自定义 HTML 按钮样式
                btn_style = f"background-color: {current_hex}; color: {'white' if current_hex != '#f0f2f6' else 'black'}; border: 1px solid #ccc; border-radius: 4px; width:100%; height: 50px;"
                if st.button(f"{current_label}", key=cell_key, help=f"{day} {period}"):
                    st.session_state[f"edit_{cell_key}"] = True

                # 编辑弹窗
                if st.session_state.get(f"edit_{cell_key}", False):
                    with st.popover("编辑课程", open=True):
                        # 选项列表
                        select_options = ["删除此时间段"]
                        option_map = {"删除此时间段": None}
                        
                        for rec_id, (hex_val, label) in my_color_options.items():
                            opt_str = f"{label}"
                            select_options.append(opt_str)
                            option_map[opt_str] = rec_id

                        choice = st.radio("选择", select_options)
                        
                        if st.button("确认"):
                            # 先删除旧记录
                            old_records = table_schedule.all(formula=f"AND({{StudentName}}='{user_name}', {{Weekday}}='{day}', {{Period}}='{period}')")
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
                            
                            st.session_state[f"edit_{cell_key}"] = False
                            st.rerun()
