import requests
import json
import argparse
import sys
from utils import parse_curl, extract_content_universally, load_presets
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live

console = Console()

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
        # 增加超时时间：连接超时 15s，读取超时 600s
        response = requests.post(api_url, headers=headers, json=payload, stream=True, timeout=(15, 600))
        
        if response.status_code != 200:
            console.print(f"[bold red]❌ 错误: 状态码 {response.status_code}[/bold red]")
            console.print(f"响应详情: {response.text}")
            return

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8').strip()
                if decoded_line.startswith('data:'):
                    try:
                        json_str = decoded_line[5:].strip()
                        if not json_str: continue
                        data_json = json.loads(json_str)
                        
                        # 使用通用的递归内容提取
                        content = extract_content_universally(data_json)
                        if content:
                            yield content
                            
                        # 检查结束标识
                        event = data_json.get('event') or data_json.get('type')
                        if event in ['done', 'conversation.message.completed'] or data_json.get('is_finished'):
                            break
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        console.print(f"[bold red]❌ 发生异常: {str(e)}[/bold red]")

def main():
    parser = argparse.ArgumentParser(description="Coze 智能体 API 调用工具")
    parser.add_argument("--url", help="API 调用链接")
    parser.add_argument("--token", help="API Token")
    parser.add_argument("--project_id", help="Project ID")
    parser.add_argument("--query", help="对话内容")
    parser.add_argument("--config", help="从 JSON 配置文件加载预设")
    
    args = parser.parse_args()

    console.print(Panel("[bold blue]🤖 Coze 智能体终端工具[/bold blue]", expand=False))
    
    api_url = args.url
    api_token = args.token
    project_id = args.project_id
    
    # 如果指定了配置文件
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
                api_url = config.get("api_url", api_url)
                api_token = config.get("api_token", api_token)
                project_id = config.get("project_id", project_id)
                console.print(f"[green]✅ 已从配置文件 {args.config} 加载配置[/green]")
        except Exception as e:
            console.print(f"[red]❌ 加载配置文件失败: {e}[/red]")

    # 交互式输入
    if not api_url: api_url = console.input("[bold yellow]请输入 API URL:[/bold yellow] ").strip()
    if not api_token: api_token = console.input("[bold yellow]请输入 API Token:[/bold yellow] ", password=True).strip()
    if not project_id: project_id = console.input("[bold yellow]请输入 Project ID:[/bold yellow] ").strip()

    if not api_url or not api_token or not project_id:
        console.print("[red]错误: API URL, Token 和 Project ID 都是必须的。[/red]")
        return

    # 进入对话循环
    console.print("\n[dim]提示: 输入 'exit' 或 'quit' 退出，输入 'clear' 清屏。[/dim]")
    
    while True:
        if args.query:
            user_query = args.query
        else:
            user_query = console.input("\n[bold green]👤 您:[/bold green] ").strip()
        
        if not user_query: continue
        if user_query.lower() in ['exit', 'quit']: break
        if user_query.lower() == 'clear':
            console.clear()
            continue

        console.print("[bold blue]🤖 助手:[/bold blue] ", end="")
        
        full_response = ""
        with Live(console=console, refresh_per_second=10) as live:
            for chunk in call_coze_api_stream(api_url, api_token, project_id, user_query):
                full_response += chunk
                # 实时渲染 Markdown 可能会有性能开销，但对于流式文本效果很好
                live.update(Markdown(full_response))
        
        # 如果是命令行一次性查询，则退出
        if args.query: break

if __name__ == "__main__":
    main()
