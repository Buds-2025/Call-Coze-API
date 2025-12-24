import requests
import json
import sys
import argparse

def call_coze_api(api_url, api_token, project_id, user_query):
    """
    调用 Coze 智能体 API
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

    print(f"\n[发送请求] URL: {api_url}")
    print(f"[项目 ID]: {project_id}")
    print(f"[对话内容]: {user_query}")
    print("-" * 50)

    try:
        # 使用 stream=True 处理流式输出
        response = requests.post(api_url, headers=headers, json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"错误: 状态码 {response.status_code}")
            print(f"响应内容: {response.text}")
            return

        print("收到回复 (流式输出):\n")
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                
                # Coze 的流式输出通常以 'data:' 开头
                if decoded_line.startswith('data:'):
                    try:
                        # 提取 JSON 部分
                        json_str = decoded_line[5:].strip()
                        if not json_str:
                            continue
                            
                        data_json = json.loads(json_str)
                        
                        # 处理 Coze 的各种事件类型
                        # conversation.message.delta: 消息增量
                        # conversation.message.completed: 消息完成
                        event = data_json.get('event') or data_json.get('type')
                        
                        # 尝试提取内容
                        content = ""
                        if 'content' in data_json:
                            raw_content = data_json['content']
                            if isinstance(raw_content, str):
                                content = raw_content
                            elif isinstance(raw_content, dict) and 'text' in raw_content:
                                content = raw_content['text']
                        
                        if content:
                            print(content, end='', flush=True)
                            full_response += content
                        
                        # 检查完成标识
                        if event in ['done', 'conversation.message.completed'] or data_json.get('is_finished'):
                            # 有些 API 在 done 时可能还会带上最后的完整内容，这里我们已经通过 delta 输出了
                            pass
                            
                    except json.JSONDecodeError:
                        # 忽略非 JSON 行
                        pass
                elif decoded_line.startswith('event:'):
                    # 可以记录事件类型，但不一定需要输出
                    pass

        print("\n" + "-" * 50)
        print("对话结束。")

    except Exception as e:
        print(f"调用 API 时发生错误: {e}")

def main():
    parser = argparse.ArgumentParser(description="Coze 智能体 API 调用工具")
    parser.add_argument("--url", help="API 调用链接", default="https://zfwgj2s2zx.coze.site/stream_run")
    parser.add_argument("--token", help="API Token")
    parser.add_argument("--project_id", help="Project ID")
    parser.add_argument("--query", help="对话内容")
    
    args = parser.parse_args()

    print("=== Coze 智能体 API 调用工具 ===")
    
    # 优先使用命令行参数，如果没有则进入交互模式
    api_url = args.url
    api_token = args.token
    project_id = args.project_id
    
    if not api_token:
        api_token = input("请输入 API Token: ").strip()
    if not project_id:
        project_id = input("请输入 project_id: ").strip()

    if not api_token or not project_id:
        print("错误: API Token 和 Project ID 是必须的。")
        return

    # 如果命令行提供了 query，则只执行一次
    if args.query:
        call_coze_api(api_url, api_token, project_id, args.query)
        return

    # 否则进入循环对话模式
    while True:
        try:
            user_query = input("\n请输入对话内容 (输入 'exit' 退出): ").strip()
            if user_query.lower() in ['exit', 'quit', '退出']:
                break
            
            if not user_query:
                continue
                
            call_coze_api(api_url, api_token, project_id, user_query)
        except KeyboardInterrupt:
            print("\n程序已退出。")
            break

if __name__ == "__main__":
    main()
