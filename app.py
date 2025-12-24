import streamlit as st
import requests
import json
import time
import re

# 设置页面配置
st.set_page_config(
    page_title="Coze 智能体交互工具",
    page_icon="🤖",
    layout="wide"
)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_url" not in st.session_state:
    st.session_state.api_url = "https://zfwgj2s2zx.coze.site/stream_run"
if "api_token" not in st.session_state:
    st.session_state.api_token = ""
if "project_id" not in st.session_state:
    st.session_state.project_id = ""

def parse_curl(curl_str):
    """
    解析 Curl 命令并提取 URL, Token 和 Project ID
    """
    results = {}
    
    # 提取 URL
    url_match = re.search(r'https?://[^\s\"`]+', curl_str)
    if url_match:
        results['api_url'] = url_match.group(0).strip('`').strip()
    
    # 提取 Authorization Token
    token_match = re.search(r'Bearer\s+([^\s\'\"]+)', curl_str)
    if token_match:
        results['api_token'] = token_match.group(1).strip()
    
    # 提取 project_id (从 JSON 数据中)
    project_id_match = re.search(r'["\']project_id["\']\s*:\s*(\d+)', curl_str)
    if project_id_match:
        results['project_id'] = project_id_match.group(1).strip()
    
    return results

def extract_content_universally(obj):
    """
    先进的递归内容提取算法：一劳永逸地处理所有嵌套 JSON 结构。
    通过黑名单过滤元数据，提取所有可能的有效文本。
    """
    # 定义元数据黑名单（这些字段通常包含 ID、状态码或配置，不是我们要显示的文本）
    METADATA_KEYS = {
        'msg_id', 'log_id', 'session_id', 'reply_id', 'sequence_id', 
        'type', 'event', 'finish', 'tool_call_id', 'code', 'execute_id',
        'local_msg_id', 'query_msg_id', 'is_finished', 'time_cost_ms'
    }
    
    # 定义高优先级内容键（如果找到这些键，直接返回其值）
    PRIORITY_KEYS = ['answer', 'result', 'text', 'thinking', 'content']

    if isinstance(obj, dict):
        # 1. 特殊处理工具调用请求
        if obj.get('type') == 'tool_request' or 'tool_request' in obj:
            tool_data = obj.get('tool_request') or obj
            if isinstance(tool_data, dict) and 'tool_name' in tool_data:
                return f"\n> 🛠️ **正在调用工具: {tool_data['tool_name']}...**\n"

        # 2. 尝试高优先级键
        for key in PRIORITY_KEYS:
            if key in obj and obj[key]:
                res = extract_content_universally(obj[key])
                if res: return res

        # 3. 递归搜索所有其他键（排除黑名单）
        for k, v in obj.items():
            if k not in METADATA_KEYS and v:
                res = extract_content_universally(v)
                if res: return res
                
    elif isinstance(obj, list):
        for item in obj:
            res = extract_content_universally(item)
            if res: return res
            
    elif isinstance(obj, str):
        # 排除掉看起来像 ID 或 UUID 的字符串
        if len(obj) > 0 and not (len(obj) > 20 and '-' in obj and obj.replace('-', '').isalnum()):
            return obj
            
    return ""

def call_coze_api_stream(api_url, api_token, project_id, user_query):
    """
    调用 Coze 智能体 API 并返回生成器以支持流式显示
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

    try:
        # 使用占位符显示状态，方便后续清除
        status_placeholder = st.empty()
        status_placeholder.info(f"🚀 正在发送请求并等待智能体思考 (复杂问题可能需要较长时间)...")
        
        # 增加超时时间：连接超时 15s，读取超时 600s (10分钟)
        # 针对深度搜索或复杂逻辑，智能体可能需要很久才开始输出
        response = requests.post(api_url, headers=headers, json=payload, stream=True, timeout=(15, 600))
        
        if response.status_code != 200:
            status_placeholder.empty()
            error_msg = f"❌ 错误: 状态码 {response.status_code}\n\n响应详情: {response.text}"
            st.error(error_msg)
            yield error_msg
            return

        has_data = False
        for line in response.iter_lines():
            if line:
                if not has_data:
                    status_placeholder.empty() # 收到第一行数据时清除提示
                has_data = True
                decoded_line = line.decode('utf-8').strip()
                
                # 调试日志：发送给 UI
                yield f"DEBUG_RAW: {decoded_line}"
                
                if decoded_line.startswith('data:'):
                    try:
                        json_str = decoded_line[5:].strip()
                        if not json_str:
                            continue
                        
                        data_json = json.loads(json_str)
                        
                        # 使用先进的递归通用解析器
                        content = extract_content_universally(data_json)
                        
                        if content:
                            # 确保内容是字符串
                            content_str = str(content)
                            if content_str.strip():
                                yield content_str
                        
                        # 检查结束标识
                        event = data_json.get('event') or data_json.get('type')
                        if event in ['done', 'conversation.message.completed'] or data_json.get('is_finished'):
                            break
                            
                    except json.JSONDecodeError:
                        # 如果不是 JSON，尝试直接输出（排除一些心跳包或空行）
                        if len(decoded_line) > 5:
                            pass 
                
        if not has_data:
            yield "⚠️ 收到响应但无数据流返回。请检查 Project ID 或 API Token 是否正确，或者该 API 链接是否支持流式输出。"

    except requests.exceptions.ReadTimeout:
        status_placeholder.empty()
        yield "❌ 读取超时：智能体生成内容时间过长。这通常发生在处理极其复杂的任务时，请尝试拆分问题或稍后再试。"
    except requests.exceptions.ConnectTimeout:
        status_placeholder.empty()
        yield "❌ 连接超时：无法连接到 Coze 服务器，请检查网络设置。"
    except requests.exceptions.RequestException as e:
        status_placeholder.empty()
        yield f"❌ 网络请求异常: {str(e)}"
    except Exception as e:
        status_placeholder.empty()
        yield f"❌ 发生未知异常: {str(e)}"

# 侧边栏配置
with st.sidebar:
    st.title("⚙️ 配置中心")
    
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
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("输入您想说的话..."):
    if not api_token or not project_id:
        st.error("请先在侧边栏配置 API Token 和 Project ID！")
    else:
        # 添加用户消息到历史
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 调用 API 并流式显示回复
        with st.chat_message("assistant"):
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
            
            response_placeholder.markdown(full_response)
        
        # 添加助手消息到历史
        st.session_state.messages.append({"role": "assistant", "content": full_response})
