import os
import platform
import re
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    import subprocess
    subprocess.check_call(["python", "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

console = Console()

class LLMProvider(ABC):
    """抽象基类，定义LLM提供商的通用接口"""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.system_info = self._get_system_info()
    
    def _get_system_info(self) -> Dict[str, str]:
        """获取系统信息"""
        return {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version()
        }
    
    def _get_initial_prompt(self, readme_content: str) -> str:
        """获取初始安装命令的提示词"""
        return f"""你是一个专业的开发环境配置助手。请根据GitHub项目的README文件，为用户生成详细的安装和配置命令序列。

                    当前系统信息：
                    - 操作系统: {self.system_info['os']}
                    - 架构: {self.system_info['architecture']}
                    - Python版本: {self.system_info['python_version']}

                    请遵循以下规则：
                    1. 优先推荐使用conda创建虚拟环境
                    2. 如果项目有requirements.txt，使用pip安装依赖
                    3. 如果项目需要特殊配置，请明确指出
                    4. 命令应该适用于{self.system_info['os']}系统
                    5. 每行只包含一个命令

                    6. 如果需要用户提供信息（如API密钥等），使用<YOUR_XXX_HERE>格式占位符
                    7. 如果设置完成，最后一行返回 "DONE_SETUP_COMMANDS"
                    8. ***请检查所有生成的命令：每一个命令都需要重新进入项目所在的文件夹，然后，每当生成pip install 或者 conda install 命令时，请先激活环境，并用&&把所有的命令连接起来，例如：-cd vggt && conda activate myenv && pip install -r requirements.txt，其中requirements.txt是项目的依赖文件。

                    项目README内容：
                    {readme_content}

                    请分析该项目并生成安装配置命令序列，直接返回命令列表，每行一个命令，不要添加额外的解释文本："""

    def _get_continue_prompt(self, last_command: str, stdout: str, stderr: str,prompt_form_user:str) -> str:
        """获取继续执行的提示词"""
        if prompt_form_user is None:
            return f"""上一个命令: {last_command}
                    执行结果:
                    stdout: {stdout}
                    stderr: {stderr}
                    
                    请基于执行结果决定下一步操作：
                    1. 如果执行成功且还需要更多步骤，请提供下一批命令
                    2. 如果执行失败，请提供修复命令,如果返回的错误是找不到文件，请注意，每一次运行命令时，都会相当于新建一个终端，因此命令需要重新进入项目所在的文件夹，而且每当生成pip install 或者 conda install 命令时，请先激活环境。所以，在原来的命令上，用&&把所有的命令连接起来，例如：-cd vggt && conda activate myenv && pip install -r requirements.txt
                    3. 如果所有步骤都已完成，请返回 "DONE_SETUP_COMMANDS"
                    请直接返回命令列表，每行一个命令，不要添加额外的解释文本："""
        return f"""上一个命令: {last_command}
                    执行结果:
                    stdout: {stdout}
                    stderr: {stderr}
                    
                    请基于执行结果决定下一步操作：
                    1. 如果执行成功且还需要更多步骤，请提供下一批命令
                    2. 如果执行失败，请提供修复命令,如果返回的错误是找不到文件，请注意，每一次运行命令时，都会相当于新建一个终端，因此命令需要重新进入项目所在的文件夹，而且每当生成pip install 或者 conda install 命令时，请先激活环境。所以，在原来的命令上，用&&把所有的命令连接起来，例如：-cd vggt && conda activate myenv && pip install -r requirements.txt
                    3. 如果所有步骤都已完成，请返回 "DONE_SETUP_COMMANDS"
                    同时请注意：{prompt_form_user}
                    请直接返回命令列表，每行一个命令，不要添加额外的解释文本："""
    
    def _parse_commands(self, response_text: str) -> List[str]:
        """解析响应文本，提取命令列表"""
        lines = response_text.strip().split('\n')
        commands = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是完成标记
            if line.upper() == "DONE_SETUP_COMMANDS":
                commands.append(line.upper())  # 保持原样，让调用方处理
                break  # 这是最后一个标记，不需要继续解析
            
            # 移除可能的序号前缀
            line = re.sub(r'^\d+\.\s*', '', line)
            line = re.sub(r'^\d+\)\s*', '', line)
            line = re.sub(r'^\-\s*', '', line)
            line = re.sub(r'^\*\s*', '', line)
            
            # 移除代码块标记
            if line.startswith('```') or line.startswith('`'):
                continue
                
            # 跳过明显的解释文本
            if any(keyword in line.lower() for keyword in ['注意', '说明', '提示', 'note:', 'tip:']):
                continue
                
            commands.append(line)
        
        return commands
    
    def _display_commands(self, commands: List[str]):
        """显示命令列表"""
        if not commands:
            return
            
        table = Table(title="大模型推荐的初始命令", style="cyan")
        table.add_column("序号", justify="right", style="cyan", no_wrap=True)
        table.add_column("命令", style="magenta")
        
        for i, command in enumerate(commands, 1):
            table.add_row(str(i), command)
        
        console.print(table)
    
    @abstractmethod
    def _call_api(self, prompt: str, message_history: List[Dict] = None) -> str:
        """调用API的抽象方法，由子类实现"""
        pass
    
    def generate_initial_commands(self, readme_content: str) -> Tuple[List[str], List[Dict]]:
        """生成初始命令序列"""
        console.print(f"[AI] 正在向{self.model_name}请求初始命令...")
        
        prompt = self._get_initial_prompt(readme_content)
        response_text = self._call_api(prompt)
        
        if not response_text:
            return [], []
        
        commands = self._parse_commands(response_text)
        
        # 显示命令
        self._display_commands(commands)
        
        # 初始化消息历史
        initial_message = {"role": "user", "content": prompt}
        assistant_message = {"role": "assistant", "content": response_text}
        message_history = [initial_message, assistant_message]
        
        return commands, message_history
    
    def generate_next_commands(self, message_history: List[Dict], last_command: str, stdout: str, stderr: str,prompt_form_user=None) -> Tuple[List[str], List[Dict]]:
        """基于执行结果生成下一批命令"""
        prompt = self._get_continue_prompt(last_command, stdout, stderr,prompt_form_user)
        response_text = self._call_api(prompt, message_history)
        
        if not response_text:
            return [], message_history
        
        commands = self._parse_commands(response_text)
        
        # 更新消息历史
        user_message = {"role": "user", "content": prompt}
        assistant_message = {"role": "assistant", "content": response_text}
        message_history.extend([user_message, assistant_message])
        
        if commands:
            self._display_commands(commands)
        
        return commands, message_history
    



class DashScopeProvider(LLMProvider):
    """通义千问API提供商"""
    
    def __init__(self, api_key: str, model_name: str = "qwen-turbo"):
        super().__init__(api_key, model_name)
        try:
            import dashscope
            self.dashscope = dashscope
            dashscope.api_key = api_key
        except ImportError:
            console.print("[ERROR] 未安装 dashscope 库，请运行: pip install dashscope")
            raise
    
    def _call_api(self, prompt: str, message_history: List[Dict] = None) -> str:
        """调用通义千问API"""
        try:
            if message_history:
                # 使用对话历史
                messages = message_history.copy()
                messages.append({"role": "user", "content": prompt})
                
                response = self.dashscope.Generation.call(
                    model=self.model_name,
                    messages=messages,
                    result_format='message'
                )
            else:
                # 单次请求
                response = self.dashscope.Generation.call(
                    model=self.model_name,
                    prompt=prompt,
                    result_format='message'
                )
            
            if response.status_code == 200:
                return response.output.choices[0]['message']['content']
            else:
                console.print(f"[ERROR] API调用失败: {response.code} - {response.message}")
                return ""
                
        except Exception as e:
            console.print(f"[ERROR] 调用通义千问API时出错: {e}")
            return ""


class GeminiProvider(LLMProvider):
    """Google Gemini API提供商"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model_name)
        try:
            from google import genai
            self.genai = genai
            # 使用 Client 而不是 GenerativeModel
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            console.print("[ERROR] 未安装 google-genai 库，请运行: pip install google-genai")
            raise
    
    def _call_api(self, prompt: str, message_history: List[Dict] = None) -> str:
        """调用Gemini API"""
        try:
            # 构建消息格式，参考 installer-gemini.py 的格式
            user_message_content = {"role": "user", "parts": [{'text': prompt}]}
            
            if message_history:
                # 转换消息历史为正确的格式
                converted_history = []
                for msg in message_history:
                    if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                        # 转换为 Gemini 格式
                        converted_msg = {
                            "role": msg['role'],
                            "parts": [{'text': msg['content']}]
                        }
                        converted_history.append(converted_msg)
                    elif isinstance(msg, dict) and 'role' in msg and 'parts' in msg:
                        # 已经是正确格式
                        converted_history.append(msg)
                
                request_contents = converted_history + [user_message_content]
            else:
                request_contents = [user_message_content]
            
            # 使用 client.models.generate_content 方法
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=request_contents
            )
            
            if response.text:
                # 处理响应文本，移除代码块标记
                processed_text = response.text.strip()
                for marker_list in [
                    ["```bash\n", "```sh\n", "```powershell\n", "```cmd\n", "```\n"], 
                    ["```bash", "```sh", "```powershell", "```cmd", "```"]
                ]:
                    for marker in marker_list:
                        processed_text = processed_text.replace(marker, "")
                processed_text = processed_text.strip()
                
                return processed_text
            else:
                console.print("[ERROR] Gemini API返回空内容")
                return ""
                
        except Exception as e:
            console.print(f"[ERROR] 调用Gemini API时出错: {e}")
            return ""


def create_llm_provider(provider_name: str, config: Dict[str, Any]) -> Optional[LLMProvider]:
    """创建LLM提供商实例"""
    try:
        if provider_name == "qwen":  # 修改：从 "dashscope" 改为 "qwen"
            return DashScopeProvider(
                api_key=os.getenv("DASHSCOPE_API_KEY"),  # 直接从环境变量获取
                model_name=config["model"]
            )
        elif provider_name == "gemini":
            return GeminiProvider(
                api_key=os.getenv("GOOGLE_API_KEY"),  # 直接从环境变量获取
                model_name=config["model"]
            )
        else:
            console.print(f"[ERROR] 不支持的提供商: {provider_name}")
            return None
    except Exception as e:
        console.print(f"[ERROR] 创建{provider_name}提供商时出错: {e}")
        return None