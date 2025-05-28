import os
import re
import requests
import subprocess
from google import genai 
from dotenv import load_dotenv
import json # For debugging output if needed

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 配置 ---
# API密钥和模型名称按您的测试用例保留
# WARNING: For production, always load API keys securely, e.g., from environment variables.
# client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) # Recommended
client = genai.Client(api_key="AIzaSyB9pzbfTvYdFXcqoKEqi-Hx5QhHe6cCg6w") # Your hardcoded key
MODEL_NAME = "gemini-1.5-flash-latest" # Using a more common model; change if "gemini-2.0-flash" is intended and accessible
# MODEL_NAME = "gemini-2.0-flash" # Your original model name
print(f"[信息] 使用模型: {MODEL_NAME}")


# --- 用于命令执行的全局当前工作目录 ---
COMMAND_CWD = os.getcwd() # Initialized, will be updated by 'cd'

# --- 函数定义 ---

def get_github_repo_details(github_url):
    """
    从 GitHub 项目链接中提取 owner, repo_name, 和 README 的原始内容。
    """
    # Regex to capture owner and repo name, allowing for .git at the end
    match = re.match(r"https://github\.com/([^/]+)/([^/.]+?)(\.git)?/?$", github_url)
    if not match:
        print(f"错误：无法从 '{github_url}' 中解析 owner/repo。")
        return None, None, None

    owner, repo_name = match.group(1), match.group(2)
    
    readme_content = None
    readme_filenames = ["README.md", "README.rst", "README.txt", "readme.md"]
    default_branches = ["main", "master"]
    
    for branch in default_branches:
        for filename in readme_filenames:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{filename}"
            try:
                print(f"正在尝试从以下链接获取 README：{raw_url}")
                response = requests.get(raw_url, timeout=10)
                response.raise_for_status() 
                readme_content = response.text
                readme_url_used = raw_url 
                print(f"成功从以下链接获取 README 内容：{readme_url_used}")
                # Return all three upon success
                return owner, repo_name, readme_content
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"在 {raw_url} (分支: {branch}) 未找到 {filename}。")
                else:
                    print(f"请求 README '{raw_url}' 时发生 HTTP 错误: {e.response.status_code} {e.response.reason}")
            except requests.exceptions.Timeout:
                print(f"请求 README '{raw_url}' 超时。")
            except requests.exceptions.RequestException as e:
                print(f"请求 README '{raw_url}' 时发生错误: {e}")
        if readme_content: # Should have returned if content was found
            break 
            
    if not readme_content:
        print(f"警告：在 {github_url} 中找不到任何常见的 README 文件 (已尝试分支: {', '.join(default_branches)})。")
    # Still return owner and repo_name even if README is not found
    return owner, repo_name, readme_content


def generate_initial_commands(readme_content, owner, repo_name, user_projects_dir, repo_exists_locally, genai_client, current_history):
    """
    根据 README（和本地仓库状态）向大模型请求初始设置命令。
    """
    if not owner or not repo_name: # Needed for prompt
        print("[错误] generate_initial_commands 需要 owner 和 repo_name。")
        return [], current_history

    clone_url = f"https://github.com/{owner}/{repo_name}.git"
    # Windows-style paths for the prompt
    target_repo_path_for_prompt = os.path.join(user_projects_dir, repo_name).replace("/", "\\")
    user_projects_dir_for_prompt = user_projects_dir.replace("/", "\\")

    if repo_exists_locally:
        initial_steps_prompt = f"""
        用户的仓库已存在于 "{target_repo_path_for_prompt}"。
        你的第一个命令必须是将当前目录更改到这个已存在的仓库中。
        该命令应为：cd "{target_repo_path_for_prompt}"
        之后，请提供安装和设置项目的其余说明。
        """
    else:
        initial_steps_prompt = f"""
        你的第一个命令必须是将仓库 {clone_url} 克隆到 "{user_projects_dir_for_prompt}" 内名为 '{repo_name}' 的子目录中。
        该命令应为：git clone {clone_url} "{target_repo_path_for_prompt}"

        你的第二个命令必须是将当前目录更改到这个新克隆的仓库中。
        该命令应为：cd "{target_repo_path_for_prompt}"
        之后，请提供安装和设置项目的其余说明。
        """

    prompt = f"""
    你是一位专业的系统管理员和软件工程师，正在协助一位 Windows 系统用户。
    用户希望设置 GitHub 项目：{clone_url}。
    用户的项目基础目录是 "{user_projects_dir_for_prompt}"。

    {initial_steps_prompt}

    所有后续命令都必须按照它们是在 "{target_repo_path_for_prompt}" 目录内执行的方式编写。
    假设工具如 conda、pip、python 可用。优先使用 PowerShell 或 CMD 兼容命令，但如果项目生态系统中常用，也可使用类似 Linux 的命令 (例如用于 Git Bash、WSL)。

    这是 GitHub 项目的 README 文件内容 (如果可用)：
    --- README 开始 ---
    {readme_content if readme_content else "没有可用的 README 内容。请根据通用实践提供设置步骤。"}
    --- README 结束 ---

    请仔细阅读 README (如果提供)，并为 Windows 环境提供一系列清晰、简洁的命令行指令。
    这些命令应涵盖上述初始步骤 (克隆/检查存在性然后更改目录)，接着是安装、设置，以及（如果适用）运行此项目。

    仅输出命令，每个命令占一行。
    如果需要占位符（例如 API 密钥），请使用 <YOUR_VALUE_HERE>。
    如果根据 README 或通用实践设置完成，你输出的最后一行应为 "DONE_SETUP_COMMANDS"。
    """
    print("\n[AI] 正在向大模型请求初始命令...")

    user_message_content = {"role": "user", "parts": [{'text': prompt}]}
    # Ensure current_history elements are also in the correct dict/glm.Content format
    request_contents = list(current_history) + [user_message_content]
    
    try:
        response = genai_client.models.generate_content(
            model=MODEL_NAME, 
            contents=request_contents # type: ignore
        )
        
        # **CRUCIAL FIX**: Use the structured content from the response for history
        model_message_to_add = response.candidates[0].content 
        
        processed_text = response.text.strip() # .text for parsing commands is fine
        for marker_list in [["```bash\n", "```sh\n", "```powershell\n", "```cmd\n", "```\n"], ["```bash", "```sh", "```powershell", "```cmd", "```"]]:
            for marker in marker_list:
                processed_text = processed_text.replace(marker, "")
        processed_text = processed_text.strip()

        commands = [cmd.strip() for cmd in processed_text.split('\n') if cmd.strip()]
        print(f"AI 的回应 (初始命令): {commands}")
        
        updated_history = request_contents + [model_message_to_add]
        return commands, updated_history
    except Exception as e:
        print(f"[AI] 调用大模型 API 时出错 (generate_initial_commands): {e}")
        # For detailed debugging of the payload:
        # def content_to_dict(content):
        # if isinstance(content, dict):
        # return content
        # return {'role': content.role, 'parts': [{'text': p.text if hasattr(p, 'text') else str(p)} for p in content.parts]}
        # print(f"[AI 调试] Problematic request_contents: {json.dumps([content_to_dict(c) for c in request_contents], indent=2, ensure_ascii=False)}")
        return [], current_history 

def generate_next_commands(genai_client, current_history, last_command, command_output, error_output, repo_local_path):
    """
    将上一条命令的执行结果反馈给大模型，获取修正或下一步命令，并管理历史。
    """
    # Windows-style path for the prompt
    repo_local_path_for_prompt = repo_local_path.replace("/", "\\")

    prompt = f"""
    我们正在 Windows 系统上继续设置位于 "{repo_local_path_for_prompt}" 的项目。
    最后执行的命令是:
    `{last_command}`

    其标准输出为:
    --- STDOUT START ---
    {command_output}
    --- STDOUT END ---

    其标准错误输出为:
    --- STDERR START ---
    {error_output}
    --- STDERR END ---

    根据这些信息和我们之前的对话（包括 README 内容）：
    1. 如果上一条命令失败，请提供修正后的命令或故障排除步骤。假设我们仍在目录 "{repo_local_path_for_prompt}" 中。
    2. 如果上一条命令成功并且需要更多步骤，请提供下一条命令。
    3. 如果你认为设置已完成，请仅回复 "DONE_SETUP_COMMANDS"。

    仅输出命令或 "DONE_SETUP_COMMANDS"，每个占一行。不要包含其他解释性文字。
    """
    print("\n[AI] 正在向大模型请求下一步命令...")

    user_message_content = {"role": "user", "parts": [{'text': prompt}]}
    request_contents = list(current_history) + [user_message_content]

    try:
        response = genai_client.models.generate_content(
            model=MODEL_NAME,
            contents=request_contents # type: ignore
        )
        
        # **CRUCIAL FIX**: Use the structured content from the response for history
        model_message_to_add = response.candidates[0].content
        
        processed_text = response.text.strip() # .text for parsing commands is fine
        for marker_list in [["```bash\n", "```sh\n", "```powershell\n", "```cmd\n", "```\n"], ["```bash", "```sh", "```powershell", "```cmd", "```"]]:
            for marker in marker_list:
                processed_text = processed_text.replace(marker, "")
        processed_text = processed_text.strip()
                
        commands = [cmd.strip() for cmd in processed_text.split('\n') if cmd.strip()]
        print(f"AI 的回应 (后续命令): {commands}")

        updated_history = request_contents + [model_message_to_add]
        return commands, updated_history
    except Exception as e:
        print(f"[AI] 调用大模型 API 时出错 (generate_next_commands): {e}")
        # def content_to_dict(content):
        # if isinstance(content, dict):
        # return content
        # return {'role': content.role, 'parts': [{'text': p.text if hasattr(p, 'text') else str(p)} for p in content.parts]}
        # print(f"[AI 调试] Problematic request_contents: {json.dumps([content_to_dict(c) for c in request_contents], indent=2, ensure_ascii=False)}")
        return [], current_history

def execute_command_interactive(command_str):
    """
    显示命令给用户，请求确认后执行，并返回输出。
    处理 'cd' 命令以更改脚本的 CWD 概念。
    """
    global COMMAND_CWD 

    print(f"\n[命令] 当前目录 '{COMMAND_CWD}'")
    print(f"[命令] 即将执行以下命令:")
    print(f"  {command_str}", flush=True) 
    
    if "sudo" in command_str.lower():
        print("\n[警告] 此命令包含 'sudo'。在Windows上通常不适用，但请仔细检查命令意图。", flush=True)

    # Store user_input to differentiate skip from failure later
    current_user_input = input("是否执行此命令? (y/n/q 执行/跳过/退出脚本): ").strip().lower()

    if current_user_input == 'y':
        stripped_command = command_str.strip()
        if stripped_command.startswith("cd ") or stripped_command.startswith("chdir "):
            parts = stripped_command.split(None, 1)
            if len(parts) > 1:
                target_dir = parts[1].strip('"').strip("'") # Remove common quotes
                
                if not os.path.isabs(target_dir):
                    prospective_dir = os.path.join(COMMAND_CWD, target_dir)
                else:
                    prospective_dir = target_dir
                prospective_dir = os.path.normpath(prospective_dir)

                try:
                    os.chdir(prospective_dir) # This changes Python's actual CWD for Popen
                    COMMAND_CWD = os.getcwd() # Update our tracked CWD
                    msg = f"成功将目录更改为 {COMMAND_CWD}"
                    print(f"[信息] {msg}", flush=True)
                    return msg, "", True, False
                except FileNotFoundError:
                    errmsg = f"目录未找到: {prospective_dir}"
                    print(f"[命令错误] {errmsg}", flush=True)
                    return "", errmsg, False, False
                except Exception as e:
                    errmsg = f"更改目录至 {prospective_dir} 时出错: {e}"
                    print(f"[命令错误] {errmsg}", flush=True)
                    return "", errmsg, False, False
            else:
                msg = "命令 'cd' 不带参数，未执行目录更改。"
                print(f"[命令信息] {msg}", flush=True)
                return msg, "", True, False # No actual error, but no change useful to report

        print(f"[命令] 正在执行: {command_str}", flush=True)
        try:
            process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE, text=True, bufsize=1, 
                                       universal_newlines=True, cwd=COMMAND_CWD) # Use tracked CWD
            
            stdout_lines, stderr_lines = [], []
            print("[命令] 标准输出:", flush=True)
            if process.stdout:
                for line in iter(process.stdout.readline, ''): print(line, end='', flush=True); stdout_lines.append(line)
                process.stdout.close()
            stdout = "".join(stdout_lines) or "<无输出>"
            
            print("[命令] 标准错误 (如果有):", flush=True)
            if process.stderr:
                for line in iter(process.stderr.readline, ''): print(line, end='', flush=True); stderr_lines.append(line)
                process.stderr.close()
            stderr = "".join(stderr_lines)

            process.wait(timeout=600) 
            
            if process.returncode != 0: print(f"\n[命令] 命令执行失败，返回码: {process.returncode}", flush=True)
            else: print(f"\n[命令] 命令执行成功。", flush=True)
            return stdout, stderr, process.returncode == 0, False
        except subprocess.TimeoutExpired:
            print("[命令] 命令执行超时。", flush=True)
            if process: process.kill(); out, err = process.communicate()
            else: out, err = "", ""
            return out or "<超时后无输出>", err or "<超时后无错误输出>", False, False
        except Exception as e:
            print(f"[命令] 执行命令时发生错误: {e}", flush=True)
            return "", str(e), False, False
    elif current_user_input == 'q':
        print("[信息] 用户选择退出脚本。", flush=True)
        return "", "", False, True # success = False, quit_script = True
    else: # 'n' or any other input for skip
        print("[信息] 跳过命令。", flush=True)
        return "<命令跳过>", "", False, False # success = False, quit_script = False

# --- 主逻辑 ---
if __name__ == "__main__":
    # Hardcoded test values as per your request
    github_project_url = "https://github.com/Mercerai/EvGGS"
    USER_PROJECTS_BASE_DIR = "D:\\Projects" # Your hardcoded base directory

    print(f"[信息] GitHub 项目链接: {github_project_url}")
    print(f"[信息] 项目将尝试克隆到或使用基础目录: {USER_PROJECTS_BASE_DIR}")

    try:
        os.makedirs(USER_PROJECTS_BASE_DIR, exist_ok=True)
    except OSError as e:
        print(f"错误：无法创建项目基础目录 '{USER_PROJECTS_BASE_DIR}': {e}")
        exit()

    # COMMAND_CWD is initialized globally, execute_command_interactive will use and update it.
    # For the first 'git clone' command, if it uses an absolute path, its own CWD for Popen doesn't matter much.
    # If it uses a relative path, it would be relative to COMMAND_CWD (initially script's dir or USER_PROJECTS_BASE_DIR if we os.chdir there first).
    # The prompt now tells AI to use absolute path for clone target, and absolute path for the first 'cd'.

    owner, repo_name, readme_text = get_github_repo_details(github_project_url)
    
    if not owner or not repo_name:
        print("错误：无法从 GitHub URL 解析 owner 或 repository 名称。脚本终止。")
        exit()

    # Define the target path for the repository
    repo_local_clone_path = os.path.join(USER_PROJECTS_BASE_DIR, repo_name)
    repo_exists_locally = os.path.isdir(repo_local_clone_path)

    if repo_exists_locally:
        print(f"[信息] 仓库 '{repo_local_clone_path}' 已存在本地。将跳过克隆步骤并直接尝试 'cd'。")
    else:
        print(f"[信息] 仓库 '{repo_local_clone_path}' 不存在本地。AI 应提供克隆命令。")

    conversation_history = []

    current_commands, conversation_history = generate_initial_commands(
        readme_text if readme_text else "没有可用的 README 内容。",
        owner, 
        repo_name, 
        USER_PROJECTS_BASE_DIR, 
        repo_exists_locally,
        client, 
        conversation_history
    )
    
    if not current_commands:
        print("大模型未能生成初始命令或初始化对话失败，脚本终止。")
        exit()

    command_index = 0
    while command_index < len(current_commands):
        command_to_execute = current_commands[command_index]

        if command_to_execute.upper() == "DONE_SETUP_COMMANDS":
            print("\n[信息] 大模型认为设置已完成。")
            break
        
        if "<YOUR_" in command_to_execute and "_HERE>" in command_to_execute: 
            placeholder_match = re.search(r"(<YOUR_.*?_HERE>)", command_to_execute)
            if placeholder_match:
                placeholder = placeholder_match.group(1)
                print(f"\n[信息] 命令 '{command_to_execute}' 包含占位符: {placeholder}")
                user_value = input(f"  请输入 {placeholder} 的值: ")
                command_to_execute = command_to_execute.replace(placeholder, user_value)

        stdout, stderr, success, quit_script = execute_command_interactive(command_to_execute)

        if quit_script:
            break
        
        last_executed_command_str = command_to_execute
        
        # User skipped if success is False AND the output indicates skip (or more reliably, if input was 'n')
        # The current execute_command_interactive returns success=False for skips.
        user_skipped = (stdout == "<命令跳过>") 

        if success or user_skipped: 
            command_index += 1
            if command_index >= len(current_commands): 
                print("\n[信息] 当前批次命令已处理完毕，询问大模型是否有后续步骤...")
                new_commands, conversation_history = generate_next_commands(
                    client, 
                    conversation_history, 
                    last_executed_command_str, 
                    stdout, 
                    stderr,
                    repo_local_clone_path 
                )
                if new_commands:
                    if new_commands[0].upper() == "DONE_SETUP_COMMANDS":
                        print("\n[信息] 大模型确认设置已完成。")
                        break
                    print("[信息] 大模型提供了新的命令。")
                    current_commands = new_commands
                    command_index = 0 
                else:
                    print("\n[信息] 大模型未提供更多命令或指示完成。可能已完成或遇到问题。")
                    break
        else: # 命令执行失败 (and not a user skip)
            print("\n[信息] 命令执行失败，将输出反馈给大模型请求修正...")
            new_commands, conversation_history = generate_next_commands(
                client, 
                conversation_history, 
                last_executed_command_str, 
                stdout, 
                stderr,
                repo_local_clone_path
            )
            if new_commands:
                if new_commands[0].upper() == "DONE_SETUP_COMMANDS":
                    print("\n[信息] 大模型在尝试修正后认为设置已完成。")
                    break
                print("[信息] 大模型提供了修正后的命令或新的步骤。")
                current_commands = new_commands
                command_index = 0
            else:
                print("[信息] 大模型未能提供修正命令，或遇到了无法解决的问题。脚本终止。")
                break
    
    print("\n[信息] 脚本执行完毕。")