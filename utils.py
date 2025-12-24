import re
import json

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
    通用递归解析算法，从复杂的 JSON 结构中提取人类可读内容
    """
    # 元数据黑名单：这些字段通常是 ID 或技术元数据，不需要展示给用户
    METADATA_KEYS = {
        'msg_id', 'log_id', 'session_id', 'reply_id', 'sequence_id', 
        'type', 'event', 'finish', 'tool_call_id', 'code', 'execute_id',
        'local_msg_id', 'query_msg_id', 'is_finished', 'time_cost_ms'
    }
    
    # 高优先级内容键
    PRIORITY_KEYS = ['answer', 'result', 'text', 'thinking', 'content']
    
    if isinstance(obj, dict):
        # 1. 识别并格式化工具调用提示
        if obj.get('type') == 'tool_request' or 'tool_request' in obj:
            tool_data = obj.get('tool_request') or obj
            if isinstance(tool_data, dict) and 'tool_name' in tool_data:
                return f"\n> 🛠️ **正在调用工具: {tool_data['tool_name']}...**\n"
        
        # 2. 优先按顺序查找核心内容键
        for key in PRIORITY_KEYS:
            if key in obj and obj[key]:
                res = extract_content_universally(obj[key])
                if res: return res
        
        # 3. 递归遍历所有其他非黑名单键
        for k, v in obj.items():
            if k not in METADATA_KEYS and v:
                res = extract_content_universally(v)
                if res: return res
                
    elif isinstance(obj, list):
        for item in obj:
            res = extract_content_universally(item)
            if res: return res
            
    elif isinstance(obj, str):
        # 简单的启发式过滤：排除掉看起来像 UUID 或长串随机字符的字符串
        # 规则：长度大于20且包含连字符，且大部分是字母数字
        if len(obj) > 0:
            if not (len(obj) > 20 and '-' in obj and obj.replace('-', '').isalnum()):
                return obj
                
    return ""

def load_presets(config_file="config.json"):
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_presets(presets, config_file="config.json"):
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=4)
