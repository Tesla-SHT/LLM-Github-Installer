import re
import requests
from rich.console import Console

console = Console()

def get_github_readme_content(github_url):
    """
    从 GitHub 项目链接中提取 README.md 的原始内容。
    支持常见的 GitHub URL 格式。
    """
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
    if not match:
        console.print(f"错误：无法从 '{github_url}' 中解析 owner/repo。")
        return None, None, None

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
                response = requests.get(raw_url, timeout=10)
                response.raise_for_status()
                content = response.text
                readme_url_used = raw_url
                console.print(f"成功获取 README 内容从: {readme_url_used}")
                return owner, repo_cleaned, content # Found, return immediately
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
        
    return owner, repo_cleaned, content
