# --- rich 自动安装与导入 ---
from rich.console import Console
from rich.panel import Panel
from rich.console import Console
from rich.panel import Panel

from config import load_environment_variables, get_available_apis, select_api_provider
from github_utils import get_github_readme_content
from llm_providers import create_llm_provider
from command_executor import execute_command_interactive
import os
console = Console()

def main():
    """Main function to run the installer script."""
    console.print(Panel.fit("🚀 GitHub 项目智能安装器", style="bold blue"))
    
    # 加载环境变量并配置API
    load_environment_variables()
    available_apis = get_available_apis()
    
    if not available_apis:
        console.print("[ERROR] 没有可用的API配置。请检查环境变量设置。")
        console.print("需要设置 DASHSCOPE_API_KEY 或 GOOGLE_API_KEY")
        return
    
    # 选择API提供商
    selected_provider = select_api_provider(available_apis)
    if not selected_provider:
        return
        
    # 获取安装目录
    install_directory = input("请输入项目安装目录路径 (留空使用当前目录): ").strip()
    if not install_directory:
        install_directory = os.getcwd()
    else:
        #install_directory = os.path.abspath(install_directory)
        # 确保目录存在
        os.makedirs(install_directory, exist_ok=True)

    console.print(f"[INFO] 将使用安装目录: {install_directory}")

    # 创建LLM提供商实例
    llm_provider = create_llm_provider(selected_provider, available_apis[selected_provider], install_directory)
    # 获取GitHub项目URL
    github_project_url = input("请输入 GitHub 项目链接: ")
    
    # 获取README内容
    owner, repo_name, readme = get_github_readme_content(github_project_url)
    if not readme:
        console.print("无法获取 README，脚本终止。")
        return
    
    console.print(f"[INFO] 成功获取项目信息: {owner}/{repo_name}")
    
    # 获取初始命令
    current_commands, message_history = llm_provider.generate_initial_commands(readme)
    
    if not message_history and not current_commands:
        console.print("无法初始化与大模型的会话或获取初始命令，脚本终止。")
        return
    if not current_commands:
        console.print("大模型未能生成初始命令，脚本终止。")
        return

    # 主执行循环
    command_index = 0
    while True:
        if current_commands and current_commands[command_index].upper() == "DONE_SETUP_COMMANDS":
            console.print("\n[INFO] 大模型认为设置已完成。")
            break
        if not current_commands:
            console.print("\n[INFO] 大模型未提供更多命令，或认为设置已完成。")
            break
        if command_index >= len(current_commands):
            console.print("\n[INFO] 当前批次命令已处理完毕。")
            break 

        command = current_commands[command_index]

        # 处理占位符
        if "<YOUR_" in command and "_HERE>" in command:
            try:
                placeholder_start = command.find("<YOUR_")
                placeholder_end = command.find("_HERE>", placeholder_start) + len("_HERE>")
                placeholder = command[placeholder_start:placeholder_end]
                
                # 提供更清晰的提示信息
                console.print(f"\n[bold yellow][INPUT][/bold yellow] 当前命令需要用户输入信息:")
                console.print(f"命令: [cyan]{command}[/cyan]")
                console.print(f"需要输入: [yellow]{placeholder}[/yellow]")
                
                user_value = input(f"请输入 {placeholder} 的值: ")
                command = command.replace(placeholder, user_value)
                
                console.print(f"[green]已替换占位符，新命令为:[/green] {command}")
            except Exception as e:
                console.print(f"[WARN] 处理占位符时出错: {e}。将按原样使用命令。")

        # 执行命令
        stdout, stderr, success, quit_script = execute_command_interactive(command)

        if quit_script:
            break
        
        last_executed_command_for_ai = current_commands[command_index]

        if success:
            command_index += 1
            if command_index >= len(current_commands):
                console.print("\n[INFO] 当前批次命令已成功处理，询问大模型是否有后续步骤...")
                new_commands, message_history = llm_provider.generate_next_commands(message_history, last_executed_command_for_ai, stdout, stderr)
                current_commands = new_commands
                command_index = 0
        else:
            console.print("\n[INFO] 命令执行失败，将输出反馈给大模型请求修正...")
            
            new_commands, message_history = llm_provider.generate_next_commands(message_history, last_executed_command_for_ai, stdout, stderr)
            console.print("\n[INFO] 大模型生成了新的命令。")
            console.print("是否需要添加prompt来帮助生成命令？")
            console.print("[bold green]请选择操作：[/bold green][yellow](y)[/yellow] 是  [yellow](n)[/yellow] 不需要")
            yes_or_no = input("请输入 (y/n): ").strip().lower()
            if yes_or_no == 'y':
                user_prompt = input("请输入prompt: ")
                new_commands, message_history = llm_provider.generate_next_commands(message_history, last_executed_command_for_ai, stdout, stderr, user_prompt)
            current_commands = new_commands
            command_index = 0

    console.print("\n[INFO] 脚本执行完毕。")

if __name__ == "__main__":
    main()
