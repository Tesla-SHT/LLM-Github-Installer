import os
import re
import requests
import subprocess
import google.generativeai as genai
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 配置 ---
# 从环境变量中获取 API 密钥
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("错误：请设置 GOOGLE_API_KEY 环境变量。")
    print("你可以从 https://aistudio.google.com/ 获取。")
    exit()

genai.configure(api_key=GOOGLE_API_KEY)

# 选择一个 Gemini 模型。gemini-1.5-flash 通常速度快且免费额度较高
MODEL_NAME = "gemini-2.0-flash" # 或者 'gemini-1.0-pro'

# --- 函数定义 ---

def get_github_readme_content(github_url):
    """
    从 GitHub 项目链接中提取 README.md 的原始内容。
    支持常见的 GitHub URL 格式。
    """
    # 尝试从 URL 中提取 owner/repo
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
    if not match:
        print(f"错误：无法从 '{github_url}' 中解析 owner/repo。")
        return None

    owner, repo = match.groups()
    # 尝试常见的 README 文件名
    readme_filenames = ["README.md", "README.rst", "README.txt", "readme.md"]
    
    content = None
    readme_url_used = None

    for filename in readme_filenames:
        # 构建原始文件内容的 URL
        # 注意：GitHub 仓库名可能包含 ".git"，需要移除
        repo_cleaned = repo.replace(".git", "")
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_cleaned}/master/{filename}" # 假设主分支是 master, 可以改为 main
        
        try:
            response = requests.get(raw_url)
            response.raise_for_status() # 如果请求失败 (如 404), 会抛出 HTTPError
            content = response.text
            readme_url_used = raw_url
            print(f"成功获取 README 内容从: {readme_url_used}")
            break # 找到一个就停止
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"未找到 {filename} at {raw_url}, 尝试下一个...")
            else:
                print(f"请求 README 时发生 HTTP 错误: {e} for URL: {raw_url}")
                return None # 其他 HTTP 错误则直接返回 None
        except requests.exceptions.RequestException as e:
            print(f"请求 README 时发生错误: {e} for URL: {raw_url}")
            return None

    if not content:
        print(f"错误：在 {github_url} 中找不到任何常见的 README 文件。")
        print("请检查链接或项目结构，确保主分支名正确（master/main）。")
        
    return content

def generate_initial_commands(readme_content):
    """
    将 README 内容发送给大模型，获取初始设置命令。
    """
    if not readme_content:
        return []

    model = genai.GenerativeModel(MODEL_NAME)
    # 初始化聊天，后续可以发送更多消息
    chat = model.start_chat(history=[])

    prompt = f"""
    你是一个专业的系统管理员和软件工程师。
    这是 GitHub 项目的 README 文件内容：
    --- README START ---
    {readme_content}
    --- README END ---

    请仔细阅读以上内容，并提供一系列清晰、简洁的命令行指令，用于在典型的 Linux 或 macOS 环境中安装、设置和（如果适用）运行此项目。
    请只输出命令，每个命令占一行。
    如果项目有多种设置方法，请选择最常见或推荐的一种。
    如果需要用户输入占位符（例如 API 密钥），请使用 <YOUR_VALUE_HERE> 这样的标记。
    如果设置完成，最后一行输出 "DONE_SETUP_COMMANDS"。
    """
    print("\n[AI] 正在向大模型请求初始命令...")
    try:
        response = chat.send_message(prompt)
        # print(f"[AI DEBUG] Raw response: {response.text}") # 用于调试
        commands = [cmd.strip() for cmd in response.text.split('\n') if cmd.strip() and not cmd.strip().startswith(("```", "DONE_SETUP_COMMANDS"))]
        return commands, chat # 返回命令列表和聊天会话
    except Exception as e:
        print(f"[AI] 调用大模型 API 时出错: {e}")
        return [], None


def generate_next_commands(chat_session, last_command, command_output, error_output):
    """
    将上一条命令的执行结果反馈给大模型，获取修正或下一步命令。
    """
    if not chat_session:
        print("[AI] 聊天会话未初始化。")
        return []

    model = genai.GenerativeModel(MODEL_NAME) # chat_session 已经关联了模型

    prompt = f"""
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
    4. 请只输出命令，每个命令占一行。不要包含其他解释性文字，除非是必要的提示。
    """
    print("\n[AI] 正在向大模型请求下一步命令...")
    try:
        response = chat_session.send_message(prompt)
        # print(f"[AI DEBUG] Raw response: {response.text}") # 用于调试
        commands = [cmd.strip() for cmd in response.text.split('\n') if cmd.strip() and not cmd.strip().startswith("```")]
        if "DONE_SETUP_COMMANDS" in commands:
            return ["DONE_SETUP_COMMANDS"]
        return commands
    except Exception as e:
        print(f"[AI] 调用大模型 API 时出错: {e}")
        return []

def execute_command_interactive(command_str):
    """
    显示命令给用户，请求确认后执行，并返回输出。
    """
    print(f"\n[CMD] 即将执行以下命令:")
    print(f"  {command_str}")
    
    # 安全检查：对于包含 sudo 的命令，特别提醒用户
    if "sudo" in command_str.lower():
        print("\n[警告] 此命令包含 'sudo'，将以管理员权限运行。请务必小心！")

    user_input = input("是否执行此命令? (y/n/q 执行/跳过/退出脚本): ").strip().lower()

    if user_input == 'y':
        print(f"[CMD] 正在执行: {command_str}")
        try:
            # shell=True 允许使用 shell特性如管道、通配符，但有安全风险，确保命令是可信的
            # 对于 AI 生成的命令，这一点尤其重要
            # 更安全的方式是解析命令并使用列表形式传递给 Popen/run，但更复杂
            process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=300) # 5分钟超时
            
            print("[CMD] 标准输出:")
            print(stdout if stdout else "<无输出>")
            if stderr:
                print("[CMD] 标准错误:")
                print(stderr)
            
            if process.returncode != 0:
                print(f"[CMD] 命令执行失败，返回码: {process.returncode}")
            else:
                print(f"[CMD] 命令执行成功。")
            return stdout, stderr, process.returncode == 0, False # stdout, stderr, success, quit_flag
        except subprocess.TimeoutExpired:
            print("[CMD] 命令执行超时。")
            process.kill()
            stdout, stderr = process.communicate()
            return stdout, stderr, False, False
        except Exception as e:
            print(f"[CMD] 执行命令时发生错误: {e}")
            return "", str(e), False, False
    elif user_input == 'q':
        print("[INFO] 用户选择退出脚本。")
        return "", "", False, True # stdout, stderr, success, quit_flag
    else:
        print("[INFO] 跳过命令。")
        return "", "", False, False # stdout, stderr, success, quit_flag

# --- 主逻辑 ---
if __name__ == "__main__":
    github_project_url = input("请输入 GitHub 项目链接: ")
    
    readme = get_github_readme_content(github_project_url)
    
    if not readme:
        print("无法获取 README，脚本终止。")
        exit()

    current_commands, chat_session = generate_initial_commands(readme)
    if not chat_session:
        print("无法初始化与大模型的聊天会话，脚本终止。")
        exit()

    if not current_commands:
        print("大模型未能生成初始命令，脚本终止。")
        exit()

    command_index = 0
    while command_index < len(current_commands):
        command = current_commands[command_index]

        if command.upper() == "DONE_SETUP_COMMANDS":
            print("\n[INFO] 大模型认为设置已完成。")
            break
        
        # 替换占位符的简单逻辑 (实际应用中可能需要更复杂的处理)
        if "<YOUR_" in command:
            print(f"\n[INFO] 命令 '{command}' 包含占位符。")
            user_value = input(f"  请输入占位符 '{command[command.find('<'):command.find('>')+1]}' 的值: ")
            command = command.replace(command[command.find('<'):command.find('>')+1], user_value)

        stdout, stderr, success, quit_script = execute_command_interactive(command)

        if quit_script:
            break
        
        # 如果命令成功，或者用户选择跳过，则继续执行当前列表中的下一条命令
        if success or (not stdout and not stderr and not success): #  (not stdout and not stderr and not success) 表示用户跳过
            command_index += 1
            if command_index >= len(current_commands): # 如果当前列表的命令都执行完了
                # 请求AI基于最后一次的执行结果给出下一步
                print("\n[INFO] 当前批次命令已处理完毕，询问大模型是否有后续步骤...")
                # 即便成功，也把最后的结果发给AI，让它判断是否真的完成了
                new_commands = generate_next_commands(chat_session, command, stdout, stderr)
                if new_commands and new_commands[0].upper() != "DONE_SETUP_COMMANDS":
                    print("[INFO] 大模型提供了新的命令。")
                    current_commands = new_commands
                    command_index = 0 # 重置索引以执行新命令
                elif new_commands and new_commands[0].upper() == "DONE_SETUP_COMMANDS":
                    print("\n[INFO] 大模型确认设置已完成。")
                    break
                else:
                    print("\n[INFO] 大模型未提供更多命令或指示完成。")
                    break
        else: # 命令执行失败
            print("\n[INFO] 命令执行失败，将输出反馈给大模型请求修正...")
            new_commands = generate_next_commands(chat_session, command, stdout, stderr)
            if new_commands and new_commands[0].upper() != "DONE_SETUP_COMMANDS":
                print("[INFO] 大模型提供了修正后的命令或新的步骤。")
                current_commands = new_commands
                command_index = 0 # 从新指令列表的第一个开始
            elif new_commands and new_commands[0].upper() == "DONE_SETUP_COMMANDS":
                 print("\n[INFO] 大模型在尝试修正后认为设置已完成。")
                 break
            else:
                print("[INFO] 大模型未能提供修正命令，或遇到了无法解决的问题。脚本终止。")
                break
    
    print("\n[INFO] 脚本执行完毕。")