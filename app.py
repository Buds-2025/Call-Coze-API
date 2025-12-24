import streamlit as st
import requests
import json
import time
import re
from utils import parse_curl, extract_content_universally, load_presets, save_presets

# 设置页面配置
st.set_page_config(
    page_title="Coze 智能体交互工具",
    page_icon="🤖",
    layout="wide"
)

# 初始化预设
if "presets" not in st.session_state:
    st.session_state.presets = load_presets()

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_url" not in st.session_state:
    st.session_state.api_url = ""
if "api_token" not in st.session_state:
    st.session_state.api_token = ""
if "project_id" not in st.session_state:
    st.session_state.project_id = ""
if "stop_generation" not in st.session_state:
    st.session_state.stop_generation = False

def is_image_url(text):
    """简单判断是否为图片链接"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    return any(text.lower().endswith(ext) for ext in image_extensions) or "image" in text.lower() and "http" in text.lower()

def call_coze_api_stream(api_url, api_token, project_id, user_query, retries=1):
    """
    调用 Coze 智能体 API 并返回生成器以支持流式显示
    包含自动重试机制
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": {
            "query": {
                "prompt": [
                    {
                        "type": "text",
                        "content": {
                            "text": user_query
                        }
                    }
                ]
            }
        },
        "type": "query",
        "project_id": project_id
    }

    attempt = 0
    while attempt <= retries:
        try:
            # 使用占位符显示状态
            status_placeholder = st.empty()
            if attempt > 0:
                status_placeholder.warning(f"🔄 正在进行第 {attempt} 次重试...")
            else:
                status_placeholder.info(f"🚀 正在发送请求并等待智能体思考...")
            
            response = requests.post(api_url, headers=headers, json=payload, stream=True, timeout=(15, 600))
            
            if response.status_code == 401:
                status_placeholder.empty()
                st.error("❌ 授权失败 (401): 请检查您的 API Token 是否正确且未过期。")
                return
            elif response.status_code == 404:
                status_placeholder.empty()
                st.error("❌ 路径未找到 (404): 请检查您的 API 调用链接是否正确。")
                return
            elif response.status_code != 200:
                status_placeholder.empty()
                st.error(f"❌ 状态码 {response.status_code}: {response.text}")
                return

            has_data = False
            for line in response.iter_lines():
                if st.session_state.get('stop_generation', False):
                    yield "\n\n⚠️ **生成已由用户停止。**"
                    return
                    
                if line:
                    if not has_data:
                        status_placeholder.empty()
                    has_data = True
                    decoded_line = line.decode('utf-8').strip()
                    
                    yield f"DEBUG_RAW: {decoded_line}"
                    
                    if decoded_line.startswith('data:'):
                        try:
                            json_str = decoded_line[5:].strip()
                            if not json_str: continue
                            data_json = json.loads(json_str)
                            content = extract_content_universally(data_json)
                            if content:
                                yield str(content)
                            
                            event = data_json.get('event') or data_json.get('type')
                            if event in ['done', 'conversation.message.completed'] or data_json.get('is_finished'):
                                return
                        except json.JSONDecodeError:
                            pass
            
            if not has_data:
                status_placeholder.empty()
                if attempt < retries:
                    attempt += 1
                    continue
                yield "⚠️ 收到响应但无数据流。请检查配置。"
                return
            return # 成功执行，退出循环

        except (requests.exceptions.RequestException, Exception) as e:
            status_placeholder.empty()
            if attempt < retries:
                attempt += 1
                time.sleep(1) # 重试前稍等
                continue
            yield f"❌ 最终失败: {str(e)}"
            return

# 侧边栏配置
with st.sidebar:
    st.title("⚙️ 配置中心")
    
    # 预设管理
    with st.expander("📂 配置预设 (Presets)", expanded=True):
        preset_names = list(st.session_state.presets.keys())
        selected_preset = st.selectbox("选择现有预设:", ["-- 请选择 --"] + preset_names)
        
        if selected_preset != "-- 请选择 --":
            if st.button("📥 加载预设"):
                p = st.session_state.presets[selected_preset]
                st.session_state.api_url = p.get('api_url', "")
                st.session_state.api_token = p.get('api_token', "")
                st.session_state.project_id = p.get('project_id', "")
                st.success(f"已加载: {selected_preset}")
                time.sleep(0.5)
                st.rerun()
        
        st.divider()
        new_preset_name = st.text_input("新预设名称:", placeholder="例如: 绘图助手")
        if st.button("💾 保存当前配置为新预设"):
            if new_preset_name:
                st.session_state.presets[new_preset_name] = {
                    "api_url": st.session_state.api_url,
                    "api_token": st.session_state.api_token,
                    "project_id": st.session_state.project_id
                }
                save_presets(st.session_state.presets)
                st.success(f"预设 '{new_preset_name}' 已保存！")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("请输入预设名称")

    # Curl 导入功能
    with st.expander("📥 导入 Curl 示例", expanded=False):
        curl_input = st.text_area("在此粘贴 Curl 命令:", height=150, placeholder="curl --location --request POST ...")
        if st.button("🚀 立即解析并导入"):
            if curl_input:
                parsed_data = parse_curl(curl_input)
                if parsed_data:
                    if 'api_url' in parsed_data: st.session_state.api_url = parsed_data['api_url']
                    if 'api_token' in parsed_data: st.session_state.api_token = parsed_data['api_token']
                    if 'project_id' in parsed_data: st.session_state.project_id = parsed_data['project_id']
                    st.success("✅ 解析成功！配置已更新。")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 无法从该命令中提取有效配置。")
            else:
                st.warning("请先粘贴 Curl 命令。")

    st.divider()
    
    # 手动输入框，使用 session_state
    api_url = st.text_input("API 调用链接", value=st.session_state.api_url)
    api_token = st.text_input("API Token", value=st.session_state.api_token, type="password", help="在 Coze 平台生成的 API 令牌")
    project_id = st.text_input("Project ID", value=st.session_state.project_id, help="智能体的项目 ID")
    
    # 更新 session_state，防止 rerun 时丢失手动修改
    st.session_state.api_url = api_url
    st.session_state.api_token = api_token
    st.session_state.project_id = project_id
    
    st.divider()
    if st.button("🗑️ 清除对话历史"):
        st.session_state.messages = []
        st.rerun()

# 主界面
st.title("🤖 Coze 智能体对话终端")
st.caption("基于 Coze API 的可视化交互界面")

# 调试模式开关
debug_mode = st.sidebar.toggle("🛠️ 调试模式", value=False)
if debug_mode:
    st.sidebar.info("调试模式已开启，原始响应数据将显示在对话框下方。")

# 显示历史消息
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # 如果内容看起来像图片链接，尝试渲染
        if is_image_url(message["content"]):
            st.image(message["content"], caption="智能体生成的图片")

# 用户输入
if prompt := st.chat_input("输入您想说的话..."):
    st.session_state.stop_generation = False # 重置停止状态
    if not api_url or not api_token or not project_id:
        st.error("请先在侧边栏配置 API 调用链接、API Token 和 Project ID！")
    else:
        # 添加用户消息到历史
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 调用 API 并流式显示回复
        with st.chat_message("assistant"):
            # 停止按钮
            stop_btn = st.button("🛑 停止生成")
            if stop_btn:
                st.session_state.stop_generation = True
                
            response_placeholder = st.empty()
            full_response = ""
            
            # 用于调试显示
            debug_container = st.empty()
            raw_data_log = []
            
            # 使用流式调用
            for chunk in call_coze_api_stream(api_url, api_token, project_id, prompt):
                if chunk.startswith("DEBUG_RAW: "):
                    raw_data_log.append(chunk[11:])
                    if debug_mode:
                        with debug_container.expander("🔍 原始响应数据流", expanded=False):
                            st.code("\n".join(raw_data_log))
                    continue
                
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
                
                # 如果发现图片链接，实时渲染预览（仅限最后一个 chunk 包含完整链接时）
                # 注意：流式输出中图片链接可能被切分，这里简单处理
            
            response_placeholder.markdown(full_response)
            if is_image_url(full_response):
                st.image(full_response.strip(), caption="智能体生成的图片")
        
        # 添加助手消息到历史
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# 底部功能区
if st.session_state.messages:
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🗑️ 清空当前对话"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        # 导出对话
        chat_text = ""
        for m in st.session_state.messages:
            chat_text += f"{m['role'].upper()}: {m['content']}\n\n"
        st.download_button("📥 导出对话记录", chat_text, file_name=f"coze_chat_{int(time.time())}.txt")
