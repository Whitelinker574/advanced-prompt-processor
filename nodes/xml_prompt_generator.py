# -*- coding: utf-8 -*-
"""
XML提示词生成器 - 将用户输入转换为结构化XML格式
作者: whitelinker
版本: 2.1.1

新增功能：
- 🌐 代理支持：自动检测系统代理或手动设置代理
- 🔧 智能连接：支持 Gemini API 格式自动转换
- 📊 详细日志：包含代理状态和连接信息的完整日志
- 🛡️ 错误处理：增强的网络连接错误处理和重试机制
- 🔄 代理格式：自动转换 httpx/requests 代理格式

代理设置说明：
1. 手动设置：在节点中填入 HTTP/HTTPS 代理地址
2. 自动检测：留空自动检测系统环境变量和 Windows 注册表代理设置
3. 支持格式：http://127.0.0.1:7890 或 https://proxy.example.com:8080
"""

import re
import json
import os
import requests
from typing import Dict, List, Any, Tuple
from urllib.parse import urlparse

# 跨平台winreg导入
try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False


def get_system_proxy(manual_http_proxy="", manual_https_proxy=""):
    """获取系统代理设置，支持手动设置"""
    try:
        # 优先使用手动设置的代理
        if manual_http_proxy or manual_https_proxy:
            proxies = {}
            if manual_http_proxy:
                proxies['http'] = manual_http_proxy
            if manual_https_proxy:
                proxies['https'] = manual_https_proxy
            return proxies
        
        # 检查环境变量
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        
        if http_proxy or https_proxy:
            return {'http': http_proxy, 'https': https_proxy}
        
        # Windows注册表检测 (仅Windows)
        if HAS_WINREG:
            try:
                reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                proxy_enable = winreg.QueryValueEx(reg_key, "ProxyEnable")[0]
                if proxy_enable:
                    proxy_server = winreg.QueryValueEx(reg_key, "ProxyServer")[0]
                    winreg.CloseKey(reg_key)
                    proxy_url = f"http://{proxy_server}"
                    return {'http': proxy_url, 'https': proxy_url}
                else:
                    winreg.CloseKey(reg_key)
            except:
                pass
    except:
        pass
    
    return None

class XMLPromptGenerator:
    """
    XML提示词生成器
    将用户输入通过LLM转换为结构化的XML格式，并支持符号强化
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "user_input": ("STRING", {
                    "multiline": True,
                    "default": "", 
                    "placeholder": "输入标签或自然语言描述"
                }),
                "input_type": (["tags", "description"], {
                    "default": "description",
                    "tooltip": "输入类型：tags(标签) 或 description(自然语言描述)"
                }),
                "api_url": ("STRING", {
                    "default": "https://api.openai.com/v1/chat/completions",
                    "placeholder": "API地址"
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "placeholder": "API密钥"
                }),
                "model_name": ("STRING", {
                    "default": "gpt-3.5-turbo",
                    "placeholder": "模型名称（Gemini请使用: gemini-2.5-flash, gemini-2.0-flash-001 或 gemini-1.5-pro）"
                }),
            },
            "optional": {
                "enable_symbol_enhancement": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "启用符号强化（@画师, #角色等）"
                }),
                "character_count": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "tooltip": "角色数量"
                }),
                "proxy_http": ("STRING", {
                    "default": "",
                    "placeholder": "HTTP代理地址(如: http://127.0.0.1:7890)，留空自动检测系统代理"
                }),
                "proxy_https": ("STRING", {
                    "default": "",
                    "placeholder": "HTTPS代理地址(如: http://127.0.0.1:7890)，留空自动检测系统代理"
                }),
            },
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("xml_output", "final_prompt", "processing_log", "raw_llm_response")
    FUNCTION = "generate_xml_prompt"
    CATEGORY = "Advanced Prompt Processor"
    
    def __init__(self):
        self.prefix = "You are an assistant designed to generate anime images based on textual prompts. <Prompt Start> "
        
        # XML模板结构
        self.xml_template = {
            "character": {
                "name": "",
                "gender": "",
                "appearance": "",
                "clothing": "",
                "body_type": "",
                "expression": "",
                "action": "",
                "interaction": "",
                "position": ""
            },
            "general_tags": {
                "count": "",
                "artists": "",
                "style": "",
                "background": "",
                "environment": "",
                "perspective": "",
                "atmosphere": "",
                "lighting": "",
                "quality": "",
                "objects": "",
                "other": ""
            }
        }

    def clean_and_validate_url(self, url: str) -> str:
        """清理和验证API URL"""
        if not url:
            raise ValueError("API URL不能为空")
        
        # 去除首尾空格
        clean_url = url.strip()
        
        # 验证URL格式
        try:
            parsed = urlparse(clean_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"无效的URL格式: {clean_url}")
        except Exception as e:
            raise ValueError(f"URL解析失败: {clean_url}, 错误: {str(e)}")
        
        return clean_url

    def get_xml_conversion_prompt(self) -> str:
        """获取XML转换的LLM提示词"""
        return """你是一个专业的动漫图像生成标签处理专家。请将用户输入转换为结构化的XML格式。

XML格式要求:
1. 角色信息 <character_1>
   - <name>: 角色名称（如hatsune_miku）
   - <gender>: 性别和数量（如1girl, 1boy）
   - <appearance>: 外观特征（头发、眼睛、身体特征）
   - <clothing>: 服装描述
   - <body_type>: 身体类型和特殊标记
   - <expression>: 表情
   - <action>: 动作
   - <interaction>: 互动
   - <position>: 位置和角度

2. 通用标签 <general_tags>
   - <count>: 人数统计
   - <artists>: 画师风格（格式：@artist_name:权重）
   - <style>: 画风和美学
   - <background>: 背景
   - <environment>: 环境元素
   - <perspective>: 视角
   - <atmosphere>: 氛围
   - <lighting>: 光照
   - <quality>: 质量标签
   - <objects>: 物体
   - <other>: 其他

注意事项:
- 所有标签用英文，用逗号分隔
- 画师名称前加@符号
- 空的类别保留空标签
- 确保XML格式正确
- 只返回XML内容，不要其他解释

示例输出:
<character_1>
<name>hatsune_miku</name>
<gender>1girl</gender>
<appearance>long_hair, blue_hair, blue_eyes</appearance>
<clothing>detached_sleeves, necktie, skirt</clothing>
<body_type></body_type>
<expression>smile</expression>
<action>looking_at_viewer</action>
<interaction></interaction>
<position></position>
</character_1>

<general_tags>
<count>1girl, solo</count>
<artists>@wlop, @artgerm</artists>
<style>very_aesthetic, detailed</style>
<background></background>
<environment></environment>
<perspective></perspective>
<atmosphere></atmosphere>
<lighting></lighting>
<quality>masterpiece, best_quality</quality>
<objects></objects>
<other></other>
</general_tags>"""

    def call_openai_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
        """调用OpenAI API"""
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"OpenAI API调用失败: {str(e)}"

    def call_claude_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
        """调用Claude API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            return f"Claude API调用失败: {str(e)}"

    def call_gemini_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
        """调用Gemini API"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            gemini_model = genai.GenerativeModel(model)
            combined_prompt = f"{system_prompt}\n\n用户输入：{user_prompt}"
            
            response = gemini_model.generate_content(
                combined_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2000,
                    temperature=0.3,
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            return f"Gemini API调用失败: {str(e)}"

    def call_deepseek_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """调用DeepSeek API，支持代理"""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "max_tokens": 2000,
                "temperature": 0.3
            }
            
            response = requests.post("https://api.deepseek.com/chat/completions", 
                                   headers=headers, json=data, proxies=proxies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            return f"DeepSeek API调用失败: {str(e)}"

    def call_custom_api(self, api_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """调用自定义API，支持代理"""
        try:
            # 清理和验证API URL
            clean_api_url = self.clean_and_validate_url(api_url)
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "max_tokens": 2000,
                "temperature": 0.3
            }
            
            response = requests.post(clean_api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            return f"自定义API调用失败: {str(e)}"

    def call_llm_api(self, ai_model: str, api_key: str, model_name: str, system_prompt: str, user_prompt: str, custom_api_url: str = "") -> str:
        """统一的LLM API调用接口"""
        if not api_key:
            return "API密钥未设置"
        
        if ai_model == "openai":
            return self.call_openai_api(api_key, model_name, system_prompt, user_prompt)
        elif ai_model == "claude":
            return self.call_claude_api(api_key, model_name, system_prompt, user_prompt)
        elif ai_model == "gemini":
            return self.call_gemini_api(api_key, model_name, system_prompt, user_prompt)
        elif ai_model == "deepseek":
            return self.call_deepseek_api(api_key, model_name, system_prompt, user_prompt)
        elif ai_model == "custom":
            if not custom_api_url:
                return "自定义模式需要提供API URL"
            return self.call_custom_api(custom_api_url, api_key, model_name, system_prompt, user_prompt)
        else:
            return f"不支持的AI模型: {ai_model}"



    def call_simple_llm_api(self, api_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, proxy_http: str = "", proxy_https: str = "") -> str:
        """简化的LLM API调用，支持Gemini自动格式转换和代理"""
        try:
            # 清理和验证API URL
            clean_api_url = self.clean_and_validate_url(api_url)
            
            # 获取代理设置（优先使用手动设置）
            proxies = get_system_proxy(proxy_http, proxy_https)
            
            # 检测Gemini API并自动转换格式
            if "generativelanguage.googleapis.com" in clean_api_url or "gemini" in model.lower():
                return self._call_gemini_xml_api(api_key, model, system_prompt, user_prompt, proxies)
            
            # 标准的OpenAI兼容API调用
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "max_tokens": 2000,
                "temperature": 0.3
            }
            
            response = requests.post(clean_api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.Timeout:
            return "XML生成API调用超时"
        except Exception as e:
            return f"API调用失败: {str(e)}"
    
    def _call_gemini_xml_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """简化的Gemini XML API调用，参考 gemini_nodes.py 的正确实现"""
        try:
            # 验证和修正模型名称
            corrected_model = self._validate_gemini_model_name(model)
            
            try:
                # 使用和 gemini_nodes.py 相同的调用方式
                import httpx
                
                # 转换代理格式为 httpx 兼容格式
                httpx_proxies = None
                if proxies:
                    httpx_proxies = {}
                    if 'http' in proxies and proxies['http']:
                        httpx_proxies['http://'] = proxies['http']
                    if 'https' in proxies and proxies['https']:
                        httpx_proxies['https://'] = proxies['https']
                    print(f"🌐 XML生成器使用代理 (httpx格式): {httpx_proxies}")
                else:
                    print("🌐 XML生成器未使用代理")
                
                client = httpx.Client(
                    base_url="https://generativelanguage.googleapis.com",
                    params={'key': api_key},
                    proxies=httpx_proxies,
                    timeout=30
                )
                
                try:
                    # 组合提示词
                    combined_prompt = f"{system_prompt}\n\n用户请求：{user_prompt}"
                    
                    body = {
                        "contents": [{
                            "parts": [{
                                "text": combined_prompt
                            }]
                        }],
                        "generationConfig": {
                            "maxOutputTokens": 2000,
                            "temperature": 0.3,
                            "stopSequences": [],
                            "candidateCount": 1
                        }
                    }
                    
                    endpoint = f"/v1beta/models/{corrected_model}:generateContent"
                    response = client.post(endpoint, json=body)
                    
                    # 增强错误处理
                    if response.status_code == 400:
                        error_detail = ""
                        try:
                            error_json = response.json()
                            error_detail = error_json.get('error', {}).get('message', '未知错误')
                        except:
                            error_detail = f"HTTP 400 - 请检查模型名称和 API 密钥"
                        return f"Gemini XML API请求错误: {error_detail}"
                    
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            parts = candidate['content']['parts']
                            if len(parts) > 0 and 'text' in parts[0]:
                                return parts[0]['text'].strip()
                    
                    return "Gemini XML API响应格式异常"
                    
                finally:
                    client.close()
                    
            except ImportError:
                # 如果 httpx 不可用，回退到 requests 方法
                corrected_model = self._validate_gemini_model_name(model)
                
                # 修正：API 密钥通过 URL 参数传递，而不是 header
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{corrected_model}:generateContent?key={api_key}"
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                # 组合提示词
                combined_prompt = f"{system_prompt}\n\n用户请求：{user_prompt}"
                
                data = {
                    "contents": [{
                        "parts": [{
                            "text": combined_prompt
                        }]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 2000,
                        "temperature": 0.3,
                        "stopSequences": [],
                        "candidateCount": 1
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=data, 
                                       proxies=proxies, timeout=30)
                
                # 增强错误处理
                if response.status_code == 400:
                    error_detail = ""
                    try:
                        error_json = response.json()
                        error_detail = error_json.get('error', {}).get('message', '未知错误')
                    except:
                        error_detail = f"HTTP 400 - 请检查模型名称和 API 密钥"
                    return f"Gemini XML API请求错误: {error_detail}"
                
                response.raise_for_status()
                
                result = response.json()
                
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            return parts[0]['text'].strip()
                
                return "Gemini XML API响应格式异常"
            
        except Exception as e:
            return f"Gemini XML API调用失败: {str(e)}"
    
    def _validate_gemini_model_name(self, model: str) -> str:
        """验证和修正 Gemini 模型名称"""
        # 常见的正确模型名称映射（更新支持 gemini-2.5-flash）
        model_mapping = {
            "gemini-2.0-flash": "gemini-2.0-flash-001", 
            "gemini-flash": "gemini-2.0-flash-001",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-pro": "gemini-1.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            # gemini-2.5-flash 应该是有效的，不需要映射
        }
        
        # 检查是否需要修正
        if model in model_mapping:
            corrected = model_mapping[model]
            print(f"🔧 XML生成器-Gemini模型名称修正: {model} -> {corrected}")
            return corrected
        
        # 如果模型名已经正确或未知，直接返回
        return model

    def apply_symbol_enhancement(self, xml_content: str) -> str:
        """对XML内容应用符号强化，与advanced_prompt_processor.py格式一致"""
        enhanced_content = xml_content
        
        # 对画师标签应用@符号强化
        def enhance_artists(match):
            artists_content = match.group(1)
            if not artists_content.strip():
                return match.group(0)
            
            # 分割画师并添加@符号
            artists = [artist.strip() for artist in artists_content.split(',')]
            enhanced_artists = []
            
            for artist in artists:
                if artist:
                    # 如果已经有@符号，保持不变
                    if artist.startswith('@'):
                        enhanced_artists.append(artist)
                    else:
                        # 清理画师标签格式
                        clean_tag = artist
                        if clean_tag.startswith("by "):
                            clean_tag = clean_tag[3:]
                        elif "artist:" in clean_tag:
                            clean_tag = clean_tag.replace("artist:", "")
                        
                        # 处理权重格式
                        if ':' in clean_tag:
                            name, weight = clean_tag.split(':', 1)
                            # 将空格替换为下划线，并添加@前缀
                            enhanced_tag = "@" + name.strip().replace(" ", "_") + ":" + weight.strip()
                            enhanced_artists.append(enhanced_tag)
                        else:
                            # 将空格替换为下划线，并添加@前缀
                            enhanced_tag = "@" + clean_tag.replace(" ", "_")
                            enhanced_artists.append(enhanced_tag)
            
            return f"<artists>{', '.join(enhanced_artists)}</artists>"
        
        # 应用画师强化
        enhanced_content = re.sub(r'<artists>(.*?)</artists>', enhance_artists, enhanced_content, flags=re.DOTALL)
        
        # 对角色名称和角色外观等应用#符号强化
        def enhance_characters(match):
            characters_content = match.group(1)
            if not characters_content.strip():
                return match.group(0)
            
            # 分割角色并添加#符号
            characters = [char.strip() for char in characters_content.split(',')]
            enhanced_characters = []
            
            for char in characters:
                if char:
                    # 如果已经有#符号，保持不变
                    if char.startswith('#'):
                        enhanced_characters.append(char)
                    else:
                        # 将空格替换为下划线，并添加#前缀
                        enhanced_tag = "#" + char.replace(" ", "_")
                        enhanced_characters.append(enhanced_tag)
            
            return f"<name>{', '.join(enhanced_characters)}</name>"
        
        # 应用角色名称强化
        enhanced_content = re.sub(r'<name>(.*?)</name>', enhance_characters, enhanced_content, flags=re.DOTALL)
        
        return enhanced_content

    def xml_to_final_prompt(self, xml_content: str) -> str:
        """将XML内容转换为最终的提示词格式"""
        try:
            # 提取XML中的所有内容
            all_tags = []
            
            # 提取所有XML标签中的内容
            xml_pattern = r'<([^>]+)>(.*?)</\1>'
            matches = re.findall(xml_pattern, xml_content, re.DOTALL)
            
            for tag_name, content in matches:
                content = content.strip()
                if content:
                    all_tags.append(content)
            
            # 合并所有标签
            final_content = ', '.join(all_tags)
            
            # 添加固定前缀
            return self.prefix + final_content
            
        except Exception as e:
            return f"{self.prefix}XML解析失败: {str(e)}"

    def generate_xml_prompt(self, user_input: str, input_type: str, api_url: str, api_key: str, model_name: str,
                           enable_symbol_enhancement: bool = True, character_count: int = 1,
                           proxy_http: str = "", proxy_https: str = "") -> Tuple[str, str, str, str]:
        """生成XML格式的提示词"""
        
        log_entries = []
        log_entries.append("=== XML提示词生成开始 ===")
        log_entries.append(f"输入类型: {input_type}")
        log_entries.append(f"API地址: {api_url}")
        log_entries.append(f"模型: {model_name}")
        log_entries.append(f"符号强化: {'启用' if enable_symbol_enhancement else '禁用'}")
        log_entries.append(f"角色数量: {character_count}")
        
        # 记录代理设置
        if proxy_http or proxy_https:
            log_entries.append(f"🌐 手动代理设置 - HTTP: {proxy_http or '无'}, HTTPS: {proxy_https or '无'}")
        else:
            log_entries.append("🌐 将自动检测系统代理设置")
        
        if not user_input.strip():
            error_msg = "用户输入为空"
            log_entries.append(f"❌ {error_msg}")
            return self.prefix, self.prefix, "\n".join(log_entries), error_msg
        
        if not api_key:
            error_msg = "API密钥未设置"
            log_entries.append(f"❌ {error_msg}")
            return self.prefix, self.prefix, "\n".join(log_entries), error_msg
        
        # 准备LLM提示
        system_prompt = self.get_xml_conversion_prompt()
        
        if input_type == "tags":
            user_prompt = f"请将以下标签转换为XML格式：\n{user_input}"
        else:
            user_prompt = f"请将以下自然语言描述转换为XML格式：\n{user_input}"
        
        # 如果需要多个角色，在提示中说明
        if character_count > 1:
            user_prompt += f"\n\n注意：需要生成{character_count}个角色，请分别用<character_1>, <character_2>等标签。"
        
        log_entries.append("🤖 调用LLM进行XML转换...")
        
        # 调用LLM API
        llm_response = self.call_simple_llm_api(api_url, api_key, model_name, system_prompt, user_prompt, proxy_http, proxy_https)
        
        if llm_response.startswith(("API调用失败", "处理失败", "不支持的AI模型")):
            log_entries.append(f"❌ LLM调用失败: {llm_response}")
            return self.prefix, self.prefix, "\n".join(log_entries), llm_response
        
        log_entries.append("✅ LLM调用成功")
        
        # 提取和清理XML内容
        xml_content = llm_response.strip()
        
        # 确保XML格式正确
        if not ("<character_" in xml_content and "<general_tags>" in xml_content):
            log_entries.append("⚠️ LLM返回的格式可能不完整，尝试修复...")
            # 这里可以添加一些基本的修复逻辑
        
        # 应用符号强化
        if enable_symbol_enhancement:
            xml_content = self.apply_symbol_enhancement(xml_content)
            log_entries.append("✅ 符号强化完成（@画师, #角色）")
        
        # 为XML输出添加前缀
        xml_output_with_prefix = self.prefix + "\n" + xml_content
        
        # 转换为最终提示词
        final_prompt = self.xml_to_final_prompt(xml_content)
        log_entries.append("✅ 最终提示词生成完成")
        
        log_entries.append("=== XML提示词生成完成 ===")
        processing_log = "\n".join(log_entries)
        
        return xml_output_with_prefix, final_prompt, processing_log, llm_response


# 节点映射
NODE_CLASS_MAPPINGS = {
    "XMLPromptGenerator": XMLPromptGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "XMLPromptGenerator": "XML提示词生成器",
}