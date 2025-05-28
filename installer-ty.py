import os
import re
import requests
import subprocess
import dashscope # For Alibaba Cloud Qwen API
from dotenv import load_dotenv

# --- rich 自动安装与导入 ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
except ImportError:
    subprocess.check_call(["python3", "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

console = Console()

# --- Configuration & Setup ---

def load_environment_variables():
    """Loads environment variables from .env file."""
    load_dotenv()

def configure_qwen_api():
    """Configures the DashScope API key."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        console.print("错误：请在 .env 文件中设置 DASHSCOPE_API_KEY 环境变量。")
        console.print("你可以从阿里云 DashScope 控制台获取。")
        exit()
    dashscope.api_key = api_key
    console.print("[INFO] 阿里云通义千问 API 配置成功。")

# Choose a Qwen model. 'qwen-turbo' is often a good balance of speed and capability.
# Other options: 'qwen-plus', 'qwen-max', 'qwen-long', etc.
# Check DashScope documentation for the latest models.
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen-turbo")


# --- GitHub README Fetching ---

def get_github_readme_content(github_url):
    """
    从 GitHub 项目链接中提取 README.md 的原始内容。
    支持常见的 GitHub URL 格式。
    """
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
    if not match:
        console.print(f"错误：无法从 '{github_url}' 中解析 owner/repo。")
        return None

    owner, repo = match.groups()
    repo_cleaned = repo.replace(".git", "")
    
    # 尝试常见的主分支名和 README 文件名
    branches_to_try = ["master", "main"]
    readme_filenames = ["README.md", "README.rst", "README.txt", "readme.md"]
    
    content = None
    readme_url_used = None

    for branch in branches_to_try:
        for filename in readme_filenames:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_cleaned}/{branch}/{filename}"
            try:
                response = requests.get(raw_url)
                response.raise_for_status()
                content = response.text
                readme_url_used = raw_url
                console.print(f"成功获取 README 内容从: {readme_url_used}")
                return content # Found, return immediately
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    console.print(f"在 {raw_url} 未找到 {filename} (分支: {branch})，尝试下一个...")
                else:
                    console.print(f"请求 README 时发生 HTTP 错误: {e} for URL: {raw_url}")
            except requests.exceptions.RequestException as e:
                console.print(f"请求 README 时发生错误: {e} for URL: {raw_url}")
        if content: # If found in any filename for this branch
            break
            
    if not content:
        console.print(f"错误：在 {github_url} 中找不到任何常见的 README 文件。")
        console.print("请检查链接、项目结构或主分支名（尝试了 master/main）。")
        
    return content

# --- Qwen LLM Interaction ---

def generate_initial_commands_qwen(readme_content):
    """
    将 README 内容发送给通义千问大模型，获取初始设置命令。
    """
    if not readme_content:
        return [], [] # commands, message_history

    system_prompt = "你是一个专业的系统管理员和软件工程师。"
    user_prompt = f"""
    这是 GitHub 项目的 README 文件内容：
    --- README START ---
    {readme_content}
    --- README END ---

    请仔细阅读以上内容，并提供一系列清晰、简洁的命令行指令，用于在典型的 Linux 或 macOS 环境中安装、设置和（如果适用）运行此项目。
    如果你发现该项目涉及 pip 等环境安装，请优先推荐使用 conda 虚拟环境进行依赖安装和环境隔离，并在命令中体现。
    请只输出命令，每个命令占一行。
    如果项目有多种设置方法，请选择最常见或推荐的一种。
    如果需要用户输入占位符（例如 API 密钥），请使用 <YOUR_VALUE_HERE> 这样的标记。
    如果设置完成，最后一行输出 "DONE_SETUP_COMMANDS"。
    """

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ]

    console.print(f"\n[AI] 正在向通义千问 ({QWEN_MODEL_NAME}) 请求初始命令...")
    try:
        response = dashscope.Generation.call(
            model=QWEN_MODEL_NAME,
            messages=messages,
            result_format='message',  # Get structured message output
            stream=False
        )
        if response.status_code == 200:
            ai_response_content = response.output.choices[0]['message']['content']
            # print(f"[AI DEBUG] Raw response: {ai_response_content}") # For debugging
            
            commands = [cmd.strip() for cmd in ai_response_content.split('\n') 
                        if cmd.strip() and not cmd.strip().startswith("```")]
            
            # Add AI's response to message history for context
            messages.append({'role': 'assistant', 'content': ai_response_content})
            
            # Remove DONE_SETUP_COMMANDS from the list if it's not the only command
            if "DONE_SETUP_COMMANDS" in commands and len(commands) > 1:
                commands = [cmd for cmd in commands if cmd != "DONE_SETUP_COMMANDS"]
            elif "DONE_SETUP_COMMANDS" in commands and len(commands) == 1:
                # If only DONE_SETUP_COMMANDS is returned, it means setup is considered done.
                pass

            # --- rich 高亮输出命令 ---
            if commands:
                console.rule("[bold green]大模型推荐的初始命令")
                syntax = Syntax("\n".join(commands), "bash", theme="monokai", line_numbers=True)
                console.print(syntax)
                console.rule()

            return commands, messages
        else:
            console.print(f"[AI] 调用通义千问 API 时出错: Code: {response.code}, Message: {response.message}")
            return [], messages # Return empty commands but potentially with history
    except Exception as e:
        console.print(f"[AI] 调用通义千问 API 时发生异常: {e}")
        return [], messages


def generate_next_commands_qwen(message_history, last_command, command_output, error_output):
    """
    将上一条命令的执行结果反馈给通义千问，获取修正或下一步命令。
    """
    if not message_history:
        console.print("[AI] 聊天会话历史未初始化。")
        return [], []

    user_feedback_prompt = f"""
    上一条执行的命令是:
    `{last_command}`

    该命令的标准输出是:
    --- STDOUT START ---
    {command_output}
    --- STDOUT END ---

    该命令的标准错误输出是:
    --- STDERR START ---
    {error_output}
    --- STDERR END ---

    基于以上信息和之前的 README 内容：
    1. 如果上一条命令成功并且还有更多设置步骤，请提供下一条命令。
    2. 如果上一条命令失败，请提供修正后的命令或解决问题的步骤。
    3. 如果你认为项目已经成功设置完毕，请只回复 "DONE_SETUP_COMMANDS"。
    4. 请只输出命令，每个命令占一行。不要包含其他解释性文字。
    """
    
    # Append user feedback to the history
    current_messages = message_history + [{'role': 'user', 'content': user_feedback_prompt}]

    console.print(f"\n[AI] 正在向通义千问 ({QWEN_MODEL_NAME}) 请求下一步命令...")
    try:
        response = dashscope.Generation.call(
            model=QWEN_MODEL_NAME,
            messages=current_messages,
            result_format='message',
            stream=False
        )
        if response.status_code == 200:
            ai_response_content = response.output.choices[0]['message']['content']
            # print(f"[AI DEBUG] Raw response: {ai_response_content}") # For debugging
            
            commands = [cmd.strip() for cmd in ai_response_content.split('\n') 
                        if cmd.strip() and not cmd.strip().startswith("```")]
            
            # Add AI's response to message history for context
            updated_messages = current_messages + [{'role': 'assistant', 'content': ai_response_content}]

            # --- rich 高亮输出下一步命令 ---
            if commands and commands[0] != "DONE_SETUP_COMMANDS":
                console.rule("[bold cyan]大模型推荐的下一步命令")
                syntax = Syntax("\n".join(commands), "bash", theme="monokai", line_numbers=True)
                console.print(syntax)
                console.rule()

            if "DONE_SETUP_COMMANDS" in commands[0]:
                return ["DONE_SETUP_COMMANDS"], updated_messages
            return commands, updated_messages
        else:
            console.print(f"[AI] 调用通义千问 API 时出错: Code: {response.code}, Message: {response.message}")
            return [], current_messages # Return empty on error, but keep history
    except Exception as e:
        console.print(f"[AI] 调用通义千问 API 时发生异常: {e}")
        return [], current_messages

# --- Command Execution ---

def execute_command_interactive(command_str):
    """
    显示命令给用户，请求确认后执行，并返回输出。
    """
    console.rule("[bold yellow]即将执行的命令")
    syntax = Syntax(command_str, "bash", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.rule()

    if "sudo" in command_str.lower():
        console.print("[bold red][警告][/bold red] 此命令包含 'sudo'，将以管理员权限运行。请务必小心！")

    console.print("[bold green]请选择操作：[/bold green][yellow](y)[/yellow] 执行  [yellow](n)[/yellow] 跳过  [yellow](q)[/yellow] 退出脚本")
    user_input = input("你的选择 (y/n/q): ").strip().lower()

    if user_input == 'y':
        console.print("[bold green][CMD] 正在执行...[/bold green]")
        try:
            process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            
            stdout_lines = []
            stderr_lines = []

            # Stream output
            if process.stdout:
                console.print("[bold blue][CMD] 标准输出:[/bold blue]")
                for line in iter(process.stdout.readline, ''):
                    console.print(line, end='')
                    stdout_lines.append(line)
                process.stdout.close()
            
            if process.stderr:
                # Wait for stderr to complete after stdout
                for line in iter(process.stderr.readline, ''):
                    if not line.strip():
                        continue
                    if not stdout_lines: console.print("[bold blue][CMD] 标准输出: <无输出>[/bold blue]")
                    if not stderr_lines : console.print("[bold red][CMD] 标准错误:[/bold red]")
                    console.print(line, end='')
                    stderr_lines.append(line)
                process.stderr.close()

            process.wait(timeout=500)
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            
            if not stdout_lines and not stderr_lines :
                 console.print("[bold blue][CMD] 标准输出: <无输出>[/bold blue]")
                 console.print("[bold red][CMD] 标准错误: <无输出>[/bold red]")

            if process.returncode != 0:
                console.print("\n[bold red][CMD] 命令执行失败，返回码: {}[/bold red]".format(process.returncode))
            else:
                console.print("\n[bold green][CMD] 命令执行成功。[/bold green]")
            console.rule()
            return stdout, stderr, process.returncode == 0, False
        except subprocess.TimeoutExpired:
            console.print("[bold red][CMD] 命令执行超时。[/bold red]")
            if process:
                stdout_after_kill, stderr_after_kill = process.communicate()
                return "".join(stdout_lines) + stdout_after_kill, "".join(stderr_lines) + stderr_after_kill, False, False
            return "".join(stdout_lines), "".join(stderr_lines), False, False
        except Exception as e:
            console.print(f"[bold red][CMD] 执行命令时发生错误: {e}[/bold red]")
            return "", str(e), False, False
    elif user_input == 'q':
        console.print("[bold magenta][INFO] 用户选择退出脚本。[/bold magenta]")
        console.rule()
        return "", "", False, True 
    else:
        console.print("[bold yellow][INFO] 跳过命令。[/bold yellow]")
        console.rule()
        return "", "", True, False

# --- Main Application Logic ---

def main():
    """Main function to run the installer script."""
    load_environment_variables()
    configure_qwen_api()

    github_project_url = input("请输入 GitHub 项目链接: ")
    
    readme = get_github_readme_content(github_project_url)
    if not readme:
        console.print("无法获取 README，脚本终止。")
        return

    current_commands, message_history = generate_initial_commands_qwen(readme)
    
    if not message_history and not current_commands:
        console.print("无法初始化与大模型的会话或获取初始命令，脚本终止。")
        return
    if not current_commands:
        console.print("大模型未能生成初始命令，脚本终止。")
        return

    command_index = 0
    while True:
        if current_commands and current_commands[0].upper() == "DONE_SETUP_COMMANDS":
            console.print("\n[INFO] 大模型认为设置已完成。")
            break
        if not current_commands:
            console.print("\n[INFO] 大模型未提供更多命令，或认为设置已完成。")
            break
        if command_index >= len(current_commands):
            console.print("\n[INFO] 当前批次命令已处理完毕。")
            break 

        command = current_commands[command_index]

        # Handle placeholders
        if "<YOUR_" in command and "_HERE>" in command:
            try:
                placeholder_start = command.find("<YOUR_")
                placeholder_end = command.find("_HERE>", placeholder_start) + len("_HERE>")
                placeholder = command[placeholder_start:placeholder_end]
                user_value = input(f"\n[INPUT] 命令 '{command}' 包含占位符。\n  请输入占位符 '{placeholder}' 的值: ")
                command = command.replace(placeholder, user_value)
            except Exception as e:
                console.print(f"[WARN] 处理占位符时出错: {e}。将按原样使用命令。")

        stdout, stderr, success, quit_script = execute_command_interactive(command)

        if quit_script:
            break
        
        last_executed_command_for_ai = current_commands[command_index]

        if success:
            command_index += 1
            if command_index >= len(current_commands):
                console.print("\n[INFO] 当前批次命令已成功处理，询问大模型是否有后续步骤...")
                new_commands, message_history = generate_next_commands_qwen(message_history, last_executed_command_for_ai, stdout, stderr)
                current_commands = new_commands
                command_index = 0
        else:
            console.print("\n[INFO] 命令执行失败，将输出反馈给大模型请求修正...")
            new_commands, message_history = generate_next_commands_qwen(message_history, last_executed_command_for_ai, stdout, stderr)
            current_commands = new_commands
            command_index = 0

    console.print("\n[INFO] 脚本执行完毕。")

if __name__ == "__main__":
    main()