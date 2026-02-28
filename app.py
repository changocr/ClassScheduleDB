
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
    # 管理员界面代码保持原样（未请求修改）
    st.title("🔧 管理员总览控制台")
    st.info("检测到管理员权限，控制台加载中...")
    # ... (省略管理员模块以控制回答篇幅，如需一并处理请指出)
    st.stop()

else:
    # ==================================
    # 学生界面 (现代化排版)
    # ==================================
    
    # 全局美化 CSS 注入
    st.markdown("""
    <style>
    /* 模块间距定义 */
    .module-spacer { height: 2rem; }
    .section-title { font-size: 1.1em; font-weight: 600; color: #1e293b; margin-bottom: 1rem; border-left: 4px solid #3b82f6; padding-left: 10px; }
    
    /* 强制重置网格列宽，实现真正的100%填充 */
    [data-testid="column"] { min-width: 0 !important; }
    [data-testid="column"] > div { width: 100% !important; }
    
    /* 核心网格清除间距 */
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    [data-testid="stHorizontalBlock"] { gap: 0 !important; }
    [data-testid="element-container"] { margin-bottom: 0 !important; width: 100% !important; }
    
    /* 基础按钮：SaaS 现代网格风格 */
    .stButton > button {
        width: 100% !important;
        height: 42px !important; /* 提升触达面积 */
        border-radius: 0 !important;
        border: 1px solid #e2e8f0 !important;
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.8rem !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        line-height: 42px !important;
        min-height: unset !important;
        padding: 0 4px !important;
        margin: 0 !important;
        transition: all 0.2s ease-in-out;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    /* 鼠标悬停动效反馈 */
    .stButton > button:hover {
        filter: brightness(0.95);
        cursor: pointer;
    }

    .stMarkdown p { margin: 0 !important; padding: 0 !important; }
    
    /* 表头与时间轴样式 */
    .schedule-header, .schedule-time {
        height: 42px !important;
        line-height: 42px !important;
        border: 1px solid #e2e8f0 !important;
        border-right: none !important;
        border-bottom: none !important;
        font-size: 0.85em !important;
        font-weight: 600;
        color: #475569;
        text-align: center !important;
        background-color: #f8fafc;
    }
    .schedule-time {
        text-align: right !important;
        font-weight: 500 !important;
        background-color: #ffffff !important;
        padding-right: 12px !important;
        color: #64748b;
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
                    "StudentName": user_name, "StartWeek": 1, "EndWeek": 17, "ColorHex": "#e2e8f0"
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

    # 周数选择器
    select_cols = st.columns(min(len(week_options), 8)) # 限制最大并排数量防止拥挤
    for idx, week_info in enumerate(week_options):
        with select_cols[idx % 8]:
            is_selected = st.session_state.selected_week == week_info["record_id"]
            
            # 动态计算高对比度文本颜色
            hex_c = week_info['color_hex'].lstrip('#')
            rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
            text_color = "white" if (rgb[0]*0.299 + rgb[1]*0.587 + rgb[2]*0.114) < 186 else "#1e293b"
            
            st.markdown(f"""
            <style>
            #sel_{week_info['record_id']} > button {{
                background-color: {week_info['color_hex']} !important;
                color: {text_color} !important;
                border: 2px solid {'#1e293b' if is_selected else 'transparent'} !important;
                border-radius: 6px !important;
                height: 36px !important;
                line-height: 32px !important;
                box-shadow: {'0 4px 6px -1px rgba(0,0,0,0.1)' if is_selected else 'none'} !important;
                transform: {'scale(1.02)' if is_selected else 'scale(1)'} !important;
            }}
            </style>
            """, unsafe_allow_html=True)
            if st.button(week_info["label"], key=f"sel_{week_info['record_id']}", use_container_width=True):
                st.session_state.selected_week = week_info["record_id"]
                st.rerun()

    # 新增控件
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
        style_ext = "border-right: 1px solid #e2e8f0 !important;" if d == len(WEEKDAYS)-1 else ""
        header_cols[d+1].markdown(f'<div class="schedule-header" style="{style_ext}">{day}</div>', unsafe_allow_html=True)

    total_periods = len(PERIODS)
    for row_idx, period in enumerate(PERIODS):
        is_last_row = row_idx == total_periods - 1
        row_cols = st.columns([1.5] + [1]*len(WEEKDAYS))
        
        time_style = "border-bottom: 1px solid #e2e8f0 !important;" if is_last_row else ""
        row_cols[0].markdown(f'<div class="schedule-time" style="{time_style}">{period}</div>', unsafe_allow_html=True)
        
        for d, day in enumerate(WEEKDAYS):
            cell_key = f"{day}-{period}"
            button_key = f"btn_{cell_key}"
            is_last_col = d == len(WEEKDAYS)-1
            
            cell_data = user_schedule.get(cell_key, None)
            cell_cid, cell_hex, cell_label = (None, "#ffffff", "") if cell_data is None else cell_data

            btn_border_right = "border-right: 1px solid #e2e8f0 !important;" if is_last_col else ""
            btn_border_bottom = "border-bottom: 1px solid #e2e8f0 !important;" if is_last_row else ""
            
            # 字体颜色对比度算法
            if cell_hex != "#ffffff":
                h_c = cell_hex.lstrip('#')
                r, g, b = tuple(int(h_c[i:i+2], 16) for i in (0, 2, 4))
                cell_text_color = "white" if (r*0.299 + g*0.587 + b*0.114) < 186 else "#1e293b"
            else:
                cell_text_color = "transparent" # 隐藏空内容的文字

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
                if st.button(cell_label if cell_label else "空", key=button_key):
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
