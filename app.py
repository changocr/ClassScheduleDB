
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

# ================= 页面逻辑 =================
st.set_page_config(page_title="极速选课系统", layout="wide")

if "user_name" not in st.session_state:
    st.title("👋 欢迎使用极速选课系统")
    input_name = st.text_input("请输入你的名字（管理员请输入 admin）", max_chars=20)
    if st.button("进入系统", type="primary", use_container_width=True):
        if input_name.strip():
            st.session_state.user_name = input_name.strip()
            st.rerun()
    st.stop()

user_name = st.session_state.user_name

if user_name.lower() == "admin":
    # ==================================
    # 管理员界面（保持稳定）
    # ==================================
    st.title("🔧 管理员总览控制台")
    df_colors, df_schedule = load_data()

    st.sidebar.header("筛选控制")
    target_week = st.sidebar.number_input("选择要查看的周数", min_value=1, max_value=30, value=1)

    all_students = []
    if not df_schedule.empty and "StudentName" in df_schedule.columns:
        all_students = df_schedule["StudentName"].unique().tolist()
    student_color_map = {s: COLOR_POOL[i % len(COLOR_POOL)] for i, s in enumerate(all_students)}

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
    st.subheader("⚠️ 危险操作：清空全部数据库")
    input_pwd = st.text_input("请输入操作密码", type="password")
    if input_pwd == CLEAR_PASSWORD:
        st.warning("密码验证通过！请再次确认是否要清空全部数据")
        if st.button("✅ 确认清空全部数据库", type="primary", use_container_width=True):
            try:
                all_colors = table_colors.all()
                all_schedule = table_schedule.all()
                if all_colors: table_colors.batch_delete([r["id"] for r in all_colors])
                if all_schedule: table_schedule.batch_delete([r["id"] for r in all_schedule])
                st.success("✅ 数据库已全部清空！")
                st.rerun()
            except Exception as e:
                st.error(f"清空失败：{e}")

else:
    # ==================================
    # 学生界面（核心优化：使用 data_editor）
    # ==================================
    st.title(f"📝 你好，{user_name}")
    
    with st.expander("📖 使用说明（必看）", expanded=True):
        st.markdown("""
        1. **选课方式**：双击表格中的格子，从下拉菜单选择对应的周数（如「1-17周」），选择「无」即可清空
        2. **零延迟**：所有操作在本地完成，表格下方会显示「已修改」提示
        3. **保存**：全部选完后，点击底部的「✅ 提交所有修改到服务器」
        """)

    df_colors, df_schedule = load_data()

    # ---------------- 1. 初始化颜色 ----------------
    my_colors = pd.DataFrame()
    if not df_colors.empty and "StudentName" in df_colors.columns:
        my_colors = df_colors[df_colors["StudentName"] == user_name].copy()
    
    if my_colors.empty:
        try:
            table_colors.create({
                "StudentName": user_name, "StartWeek": 1, "EndWeek": 17, "ColorHex": "#000000"
            })
            st.success("已为您创建默认颜色，页面即将刷新...")
            st.rerun()
        except Exception as e:
            st.error(f"初始化失败：{e}")
            st.stop()

    df_colors, df_schedule = load_data()
    my_colors = df_colors[df_colors["StudentName"] == user_name].copy()

    # ---------------- 2. 构建选项字典 ----------------
    # 格式：{ "显示文本": "ColorRecordID" }
    color_options_map = {"无": None}
    for _, row in my_colors.iterrows():
        label = f"{int(row['StartWeek'])}-{int(row['EndWeek'])}周"
        color_options_map[label] = row["RecordID"]

    # ---------------- 3. 初始化/加载 DataFrame 表格 ----------------
    if "schedule_df" not in st.session_state:
        # 构建空的课表 DataFrame
        data = []
        for period in PERIODS:
            row = {"时间": period}
            for day in WEEKDAYS:
                row[day] = "无"
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # 从服务器加载已有数据填充进去
        if not df_schedule.empty and "StudentName" in df_schedule.columns:
            user_records = df_schedule[df_schedule["StudentName"] == user_name]
            # 建立反向查找：RecordID -> 显示文本
            id_to_label = {v: k for k, v in color_options_map.items()}
            
            for _, record in user_records.iterrows():
                p = record["Period"]
                d = record["Weekday"]
                c_id = record["ColorRecordID"]
                if c_id in id_to_label:
                    df.loc[df["时间"] == p, d] = id_to_label[c_id]
        
        st.session_state.schedule_df = df

    # ---------------- 4. 新增颜色功能 ----------------
    st.subheader("🎨 我的颜色管理")
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

    if st.button("➕ 新增自定义周数颜色"):
        st.session_state.show_add_color = not st.session_state.get("show_add_color", False)

    if st.session_state.get("show_add_color", False):
        with st.form("add_color_form"):
            s_w = st.number_input("开始周", min_value=1, max_value=30, value=1)
            e_w = st.number_input("结束周", min_value=1, max_value=30, value=17)
            if st.form_submit_button("确认创建"):
                existing_hexes = my_colors['ColorHex'].tolist()
                new_hex = get_random_color(existing_hexes)
                table_colors.create({
                    "StudentName": user_name, "StartWeek": int(s_w), "EndWeek": int(e_w), "ColorHex": new_hex
                })
                st.success("新颜色创建成功！请刷新页面以在表格中使用")
                # 注意：这里不 rerun，让用户手动刷新，防止丢失当前表格编辑进度

    st.divider()

    # ---------------- 5. 核心：极速可编辑表格 ----------------
    st.subheader("📅 课表（双击格子选择，零延迟）")
    
    # 配置列：让周一到周日变成下拉选择框
    column_config = {
        "时间": st.column_config.TextColumn("时间", disabled=True),
    }
    for day in WEEKDAYS:
        column_config[day] = st.column_config.SelectboxColumn(
            day,
            options=list(color_options_map.keys()),
            default="无"
        )

    # 显示可编辑表格（这是核心，零延迟！）
    edited_df = st.data_editor(
        st.session_state.schedule_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )

    # 更新 session_state
    st.session_state.schedule_df = edited_df

    # ---------------- 6. 提交按钮 ----------------
    st.divider()
    if st.button("✅ 提交所有修改到服务器", type="primary", use_container_width=True):
        try:
            # 1. 删除旧数据
            old_records = table_schedule.all(formula=f"{{StudentName}}='{user_name}'")
            if old_records:
                table_schedule.batch_delete([r["id"] for r in old_records])
            
            # 2. 解析新数据并上传
            new_records = []
            for _, row in edited_df.iterrows():
                period = row["时间"]
                for day in WEEKDAYS:
                    val = row[day]
                    if val != "无" and val in color_options_map:
                        color_id = color_options_map[val]
                        new_records.append({
                            "StudentName": user_name,
                            "Weekday": day,
                            "Period": period,
                            "ColorRecordID": color_id
                        })
            
            if new_records:
                table_schedule.batch_create(new_records)
            
            st.success("✅ 所有修改已同步到服务器！")
        except Exception as e:
            st.error(f"提交失败：{e}")
