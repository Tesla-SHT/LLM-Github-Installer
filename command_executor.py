import subprocess
from rich.console import Console
from rich.syntax import Syntax

console = Console()

def execute_command_interactive(command_str):
    """
    显示命令给用户，请求确认后执行，并返回输出。
    """
    console.rule("[bold yellow]即将执行的命令")
    command_str1= command_str.strip()
    syntax = Syntax(command_str, "bash", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.rule()

    if "sudo" in command_str.lower():
        console.print("[bold red][警告][/bold red] 此命令包含 'sudo'，将以管理员权限运行。请务必小心！")

    console.print("[bold green]请选择操作：[/bold green][yellow](y)[/yellow] 执行  [yellow](n)[/yellow] 跳过  [yellow](m)[/yellow] 手动编辑  [yellow](q)[/yellow] 退出脚本")
    user_input = input("你的选择 (y/n/m/q): ").strip().lower()

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
    elif user_input == 'm':
        console.print("[bold yellow][INFO] 用户选择手动执行命令。[/bold yellow]")
        console.rule()
        #复制原来的命令，右键粘贴
        command_str = input("请输入手动执行的命令: ").strip()
        while not command_str:
            console.print("[bold red][ERROR] 未输入命令，无法执行，请重新输入。[/bold red]")
            command_str = input("请输入手动执行的命令: ").strip()
            
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


    else:
        console.print("[bold yellow][INFO] 跳过命令。[/bold yellow]")
        console.rule()
        return "", "", True, False
