import os
import dashscope
import google.generativeai as genai  
from dotenv import load_dotenv
from rich.console import Console

console = Console()

def load_environment_variables():
    """Loads environment variables from .env file."""
    load_dotenv()

def get_available_apis():
    """检查可用的API并返回配置信息"""
    available_apis = {}
    
    # 检查通义千问API
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    if dashscope_key:
        try:
            dashscope.api_key = dashscope_key
            available_apis['qwen'] = {
                'name': '通义千问',
                'model': os.getenv("QWEN_MODEL_NAME", "qwen-plus"),
                'client': None  # dashscope使用全局配置
            }
            console.print("[INFO] 通义千问 API 配置成功。")
        except Exception as e:
            console.print(f"[WARN] 通义千问 API 配置失败: {e}")
    
    # 检查Gemini API
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
     try:
        # 新版API初始化步骤
        genai.configure(api_key=google_key)  # 全局配置密钥
        
        # 创建模型实例（需替换模型名，如 'gemini-1.5-pro-latest'）
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")
        model = genai.GenerativeModel(model_name)  # ✅ 初始化模型
        
        # 将模型对象存入配置字典（建议语义化修改key为 'model'）
        available_apis['gemini'] = {
            'name': 'Google Gemini',
            'model': model_name,
            'instance': model  # 更清晰的命名，避免歧义
        }
        console.print("[INFO] Google Gemini API 配置成功。")
     except Exception as e:
        console.print(f"[WARN] Google Gemini API 配置失败: {e}")
    
    return available_apis

def select_api_provider(available_apis):
    """让用户选择API提供商"""
    if not available_apis:
        console.print("[ERROR] 没有可用的API配置。请检查环境变量。")
        return None
    
    if len(available_apis) == 1:
        provider = list(available_apis.keys())[0]
        console.print(f"[INFO] 自动选择唯一可用的API: {available_apis[provider]['name']}")
        return provider
    
    console.print("\n[INFO] 检测到多个可用的API，请选择:")
    for i, (key, value) in enumerate(available_apis.items(), 1):
        console.print(f"  {i}. {value['name']} (模型: {value['model']})")
    
    while True:
        try:
            choice = int(input("请输入选择 (数字): ")) - 1
            providers = list(available_apis.keys())
            if 0 <= choice < len(providers):
                selected = providers[choice]
                console.print(f"[INFO] 已选择: {available_apis[selected]['name']}")
                return selected
            else:
                console.print("[ERROR] 无效选择，请重新输入。")
        except ValueError:
            console.print("[ERROR] 请输入有效数字。")
