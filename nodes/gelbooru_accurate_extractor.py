"""
Gelbooru准确标签提取器 - 使用Gelbooru Tag API获取准确的标签分类
"""
import os
import re
import json
import requests
import random
import numpy as np
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time

# 跨平台winreg导入
try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False


def get_system_proxy():
    """获取系统代理设置"""
    try:
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


def make_robust_request(url, timeout=30, max_retries=3):
    """创建具有代理支持和重试机制的网络请求"""
    session = requests.Session()
    
    # 获取并应用系统代理
    system_proxies = get_system_proxy()
    if system_proxies:
        session.proxies.update(system_proxies)
        print(f"🌐 Gelbooru使用代理: {system_proxies}")
    
    # 配置重试策略
    try:
        # 新版本urllib3使用allowed_methods
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
    except TypeError:
        # 旧版本urllib3使用method_whitelist
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # 尝试多种连接方式
    attempts = [
        {'verify': False, 'timeout': timeout},          # 先尝试无SSL验证（通常更稳定）
        {'verify': True, 'timeout': timeout},           # 再尝试SSL验证
        {'verify': False, 'timeout': timeout * 2},      # 增加超时时间再试
    ]
    
    last_error = None
    
    for i, attempt in enumerate(attempts, 1):
        try:
            print(f"🌐 Gelbooru尝试 {i}/{len(attempts)}: 连接 {url[:50]}...")
            response = session.get(url, **attempt)
            
            if response.status_code == 200:
                print(f"✅ Gelbooru连接成功 (尝试 {i})")
                return response
            else:
                print(f"⚠️  HTTP {response.status_code}, 继续尝试...")
                
        except requests.exceptions.ProxyError as e:
            print(f"🔧 代理错误 (尝试 {i}): {e}")
            # 代理错误时，清除代理设置尝试直连
            session.proxies.clear()
            last_error = e
            continue
            
        except requests.exceptions.ConnectTimeout as e:
            print(f"⏰ 连接超时 (尝试 {i}): {e}")
            last_error = e
            continue
            
        except Exception as e:
            print(f"❌ 连接失败 (尝试 {i}): {e}")
            last_error = e
            continue
    
    # 所有尝试都失败
    print(f"❌ Gelbooru所有连接尝试都失败: {last_error}")
    raise requests.exceptions.ConnectTimeout(f"无法连接到 {url}")


class GelbooruAccurateExtractor:
    """使用Gelbooru Tag API获取准确标签分类的提取器"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enable_gelbooru": ("BOOLEAN", {"default": True, "tooltip": "是否启用Gelbooru标签获取"}),
                "site": (["Gelbooru", "Rule34"], {"default": "Gelbooru"}),
                "OR_tags": ("STRING", {"default": "", "multiline": True}),
                "AND_tags": ("STRING", {"default": "", "multiline": True}),
                "exclude_tag": ("STRING", {"default": "animated,", "multiline": True}),
                "Safe": ("BOOLEAN", {"default": True}),
                "Questionable": ("BOOLEAN", {"default": True}),
                "Explicit": ("BOOLEAN", {"default": False}),
                "score": ("INT", {"default": 10, "min": 0, "max": 1000}),
                "count": ("INT", {"default": 1, "min": 1, "max": 10}),
                "random_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "auto_random_seed": ("BOOLEAN", {"default": True, "tooltip": "自动生成9位数随机种子"}),
                
                # 标签分类选择（按正确顺序）
                "include_artists": ("BOOLEAN", {"default": True}),
                "include_characters": ("BOOLEAN", {"default": True}),
                "include_copyrights": ("BOOLEAN", {"default": True}),
                "include_general": ("BOOLEAN", {"default": True}),
                "include_metadata": ("BOOLEAN", {"default": False}),
                
                # 输出格式选择（按正确顺序）
                "artist_format": (["original", "by_prefix", "parentheses", "brackets", "underscores"], {"default": "by_prefix"}),
                "character_format": (["original", "parentheses", "brackets", "underscores"], {"default": "original"}),
                "copyright_format": (["original", "parentheses", "brackets", "from_prefix"], {"default": "original"}),
                "general_format": (["original", "parentheses", "brackets", "underscores"], {"default": "original"}),
                "metadata_format": (["original", "hidden", "parentheses"], {"default": "hidden"}),
                
                # 数量限制（按正确顺序）
                "max_artists": ("INT", {"default": 5, "min": 0, "max": 20}),
                "max_characters": ("INT", {"default": 5, "min": 0, "max": 20}),
                "max_copyrights": ("INT", {"default": 3, "min": 0, "max": 10}),
                "max_general": ("INT", {"default": 30, "min": 0, "max": 100}),
                "max_metadata": ("INT", {"default": 10, "min": 0, "max": 50}),
                
                # 组合选项
                "separator": (["comma", "space", "newline"], {"default": "comma"}),
                "use_tag_api": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "user_id": ("STRING", {"default": ""}),
                "api_key": ("STRING", {"default": ""}),
            }
        }
    
    # 按正确顺序返回：Artist-Character-Copyright-General-Metadata
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("combined_tags", "artists", "characters", "copyrights", "general_tags", "metadata", "image_urls", "tag_info")
    FUNCTION = "extract_accurate_tags"
    CATEGORY = "Advanced Prompt Processor/Gelbooru"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """强制节点每次都重新执行，避免ComfyUI缓存"""
        import time
        return time.time()
    
    def __init__(self):
        # Gelbooru标签类型映射（数字对应类型）
        self.gelbooru_tag_types = {
            0: 'general',     # 一般标签
            1: 'artists',     # 画师
            3: 'copyrights',  # 版权
            4: 'characters',  # 角色
            5: 'metadata'     # 元数据
        }
        
        # 备用分类模式的指示器（当API不可用时）
        self.fallback_artist_patterns = [
            'artist:', 'by_', 'drawn_by_', '_artist', 'pixiv_id', 'twitter_username',
            'artstation_username', 'deviantart_username', 'tumblr_username',
            'artist_name', 'art_by'
        ]
        
        self.fallback_character_patterns = [
            'character:', '_character', r'_\(.*\)$', 'girl$', 'boy$', 'chan$', 'kun$'
        ]
        
        self.fallback_copyright_patterns = [
            'copyright:', 'series:', 'from_', '_series$', '_game$', '_anime$',
            'touhou', 'fate/', 'pokemon', 'original'
        ]
        
        self.fallback_metadata_patterns = [
            'rating:', 'score:', 'favcount:', 'id:', 'width:', 'height:', 'filesize:',
            'date:', 'source:', 'pool:', 'parent:', 'has_', 'tagme', 'translation_request',
            'commentary', 'md5:', 'status:', 'approver:', 'uploader:', 'highres',
            'absurdres', 'incredibly_absurdres', 'huge_filesize', 'lowres', 'jpeg_artifacts'
        ]
    
    def extract_accurate_tags(self, enable_gelbooru, site, OR_tags, AND_tags, exclude_tag, Safe, Questionable, Explicit, 
                             score, count, random_seed, auto_random_seed,
                             include_artists, include_characters, include_copyrights, include_general, include_metadata,
                             artist_format, character_format, copyright_format, general_format, metadata_format,
                             max_artists, max_characters, max_copyrights, max_general, max_metadata,
                             separator, use_tag_api,
                             user_id="", api_key=""):
        """使用Gelbooru Tag API获取准确的标签分类"""
        
        # 检查是否启用Gelbooru
        if not enable_gelbooru:
            return self._empty_result("Gelbooru标签获取已禁用")
        
        if auto_random_seed:
            # 生成9位数随机种子 (100000000 - 999999999)
            new_seed = random.randint(100000000, 999999999)
            random.seed(new_seed)
            np.random.seed(new_seed)
            print(f"🎲 自动生成9位数随机种子: {new_seed}")
        elif random_seed != 0:
            random.seed(random_seed)
            np.random.seed(random_seed)
            print(f"使用指定随机种子: {random_seed}")
        else:
            print("使用系统默认随机种子")
        
        try:
            # 1. 获取图片数据
            posts_data = self._get_posts_data(
                site, OR_tags, AND_tags, exclude_tag, Safe, Questionable, Explicit,
                score, count, user_id, api_key
            )
            
            if not posts_data:
                return self._empty_result("未找到匹配的图片")
            
            # 2. 提取所有标签
            all_tags = self._extract_tags_from_posts(posts_data)
            
            if not all_tags:
                return self._empty_result("图片中没有找到标签")
            
            # 3. 使用Tag API获取准确分类
            categorized_tags = self._categorize_tags_with_api(
                all_tags, site, user_id, api_key, use_tag_api
            )
            
            # 4. 按正确顺序格式化标签：Artist-Character-Copyright-General-Metadata
            formatted_artists = self._format_tags(categorized_tags['artists'][:max_artists], artist_format, "artist")
            formatted_characters = self._format_tags(categorized_tags['characters'][:max_characters], character_format, "character")
            formatted_copyrights = self._format_tags(categorized_tags['copyrights'][:max_copyrights], copyright_format, "copyright")
            formatted_general = self._format_tags(categorized_tags['general'][:max_general], general_format, "general")
            formatted_metadata = self._format_tags(categorized_tags['metadata'][:max_metadata], metadata_format, "metadata")
            
            # 5. 按正确顺序组合输出
            combined_tags = self._combine_tags_in_order(
                [
                    (formatted_artists, include_artists),
                    (formatted_characters, include_characters),
                    (formatted_copyrights, include_copyrights),
                    (formatted_general, include_general),
                    (formatted_metadata, include_metadata)
                ],
                separator
            )
            
            # 6. 收集图片URLs
            image_urls = [post.get("file_url", "") for post in posts_data]
            
            # 7. 生成信息
            tag_counts = {
                'artists': len(categorized_tags['artists']),
                'characters': len(categorized_tags['characters']),
                'copyrights': len(categorized_tags['copyrights']),
                'general': len(categorized_tags['general']),
                'metadata': len(categorized_tags['metadata'])
            }
            
            tag_info = f"从{site}获取{len(posts_data)}张图片 | " + " | ".join([f"{k}:{v}" for k, v in tag_counts.items()])
            
            return (
                combined_tags,
                formatted_artists,
                formatted_characters,
                formatted_copyrights,
                formatted_general,
                formatted_metadata,
                "\n".join(image_urls),
                tag_info
            )
            
        except Exception as e:
            error_msg = f"准确标签提取失败: {str(e)}"
            print(f"❌ {error_msg}")
            return self._empty_result(error_msg)
    
    def _get_posts_data(self, site, OR_tags, AND_tags, exclude_tag, Safe, Questionable, Explicit,
                       score, count, user_id, api_key):
        """获取图片数据"""
        # 处理查询参数
        AND_tags_processed = self._process_tags(AND_tags)
        OR_tags_processed = self._process_or_tags(OR_tags, site)
        exclude_tag_processed = self._process_exclude_tags(exclude_tag)
        rate_exclusion = self._build_rating_exclusion(Safe, Questionable, Explicit, site)
        
        # 构建API URL
        base_url = "https://api.rule34.xxx/index.php" if site == "Rule34" else "https://gelbooru.com/index.php"
        
        query_params = (
            f"page=dapi&s=post&q=index&tags=sort%3arandom+"
            f"{exclude_tag_processed}+{OR_tags_processed}+{AND_tags_processed}+{rate_exclusion}"
            f"+score%3a>{score}&api_key={api_key}&user_id={user_id}&limit={count}&json=1"
        )
        url = f"{base_url}?{query_params}".replace("-+", "")
        url = re.sub(r"\++", "+", url)
        
        print(f"🔍 从{site}获取图片数据...")
        
        # 发起请求
        response = make_robust_request(url, timeout=30)
        
        if site == "Rule34":
            posts = response.json()
        else:
            posts = response.json().get('post', [])
        
        return posts
    
    def _extract_tags_from_posts(self, posts):
        """从图片数据中提取所有标签"""
        all_tags = []
        for post in posts:
            tags = post.get("tags", "").strip()
            if tags:
                post_tags = [tag.strip() for tag in tags.split() if tag.strip()]
                all_tags.extend(post_tags)
        
        # 去重并保持顺序
        unique_tags = list(dict.fromkeys(all_tags))
        return unique_tags
    
    def _categorize_tags_with_api(self, tags, site, user_id, api_key, use_tag_api):
        """使用Gelbooru Tag API获取准确的标签分类"""
        categorized = {
            'artists': [],
            'characters': [],
            'copyrights': [],
            'general': [],
            'metadata': []
        }
        
        if site != "Gelbooru" or not use_tag_api or not user_id or not api_key:
            print("⚠️  跳过Tag API，使用备用分类方法")
            return self._fallback_categorize_tags(tags)
        
        print(f"🔍 使用Tag API获取{len(tags)}个标签的准确分类...")
        
        # 分批处理标签，避免URL过长
        batch_size = 20
        for i in range(0, len(tags), batch_size):
            batch_tags = tags[i:i+batch_size]
            try:
                batch_result = self._get_tag_types_batch(batch_tags, user_id, api_key)
                
                for tag, tag_type in batch_result.items():
                    if tag_type in self.gelbooru_tag_types:
                        category = self.gelbooru_tag_types[tag_type]
                        categorized[category].append(tag)
                        print(f"✅ {tag} -> {category} (type {tag_type})")
                    else:
                        # 未知类型，归为general
                        categorized['general'].append(tag)
                        print(f"⚠️  {tag} -> general (unknown type {tag_type})")
                
                # 添加延迟避免API限制
                time.sleep(0.1)
                
            except Exception as e:
                print(f"⚠️  批次{i//batch_size + 1}处理失败: {e}")
                # 对失败的批次使用备用分类
                print(f"⚠️  对批次{i//batch_size + 1}使用备用分类: {batch_tags}")
                fallback_result = self._fallback_categorize_tags(batch_tags)
                for category, tag_list in fallback_result.items():
                    if tag_list:
                        print(f"📋 备用分类 {category}: {tag_list}")
                        categorized[category].extend(tag_list)
        
        return categorized
    
    def _get_tag_types_batch(self, tags, user_id, api_key):
        """批量获取标签类型"""
        # 使用Gelbooru Tag API的names参数，需要进行URL编码
        import urllib.parse
        names_param = " ".join(tags)
        names_encoded = urllib.parse.quote(names_param)
        url = f"https://gelbooru.com/index.php?page=dapi&s=tag&q=index&names={names_encoded}&api_key={api_key}&user_id={user_id}&json=1"
        
        print(f"🔍 Tag API请求: {url[:100]}...")
        response = make_robust_request(url, timeout=15)
        tag_data = response.json()
        
        print(f"📄 Tag API响应类型: {type(tag_data)}")
        if isinstance(tag_data, list):
            print(f"📊 找到 {len(tag_data)} 个标签信息")
        
        # 解析响应，获取标签类型
        tag_types = {}
        
        # Gelbooru API返回的是dict格式，标签数据在'tag'键下
        if isinstance(tag_data, dict) and 'tag' in tag_data:
            tag_list = tag_data['tag']
            if isinstance(tag_list, list):
                print(f"📊 解析到 {len(tag_list)} 个标签")
                for tag_info in tag_list:
                    tag_name = tag_info.get('name', '')
                    tag_type = tag_info.get('type', 0)  # type字段包含标签类型
                    if tag_name:
                        tag_types[tag_name] = tag_type
                        print(f"🏷️  {tag_name}: type={tag_type}")
            else:
                print(f"⚠️  'tag'字段不是列表: {type(tag_list)}")
        elif isinstance(tag_data, list):
            # 备用处理：如果直接是列表
            print(f"📊 直接列表格式，解析 {len(tag_data)} 个标签")
            for tag_info in tag_data:
                tag_name = tag_info.get('name', '')
                tag_type = tag_info.get('type', 0)
                if tag_name:
                    tag_types[tag_name] = tag_type
                    print(f"🏷️  {tag_name}: type={tag_type}")
        else:
            print(f"⚠️  意外的API响应格式: {type(tag_data)}")
            if isinstance(tag_data, dict):
                print(f"📋 响应键: {list(tag_data.keys())}")
        
        print(f"📋 批次结果: {len(tag_types)} 个标签获得类型信息")
        return tag_types
    
    def _fallback_categorize_tags(self, tags):
        """备用的标签分类方法（基于模式匹配）"""
        categorized = {
            'artists': [],
            'characters': [],
            'copyrights': [],
            'general': [],
            'metadata': []
        }
        
        for tag in tags:
            tag_lower = tag.lower()
            
            # 元数据标签
            if any(pattern in tag_lower for pattern in self.fallback_metadata_patterns):
                categorized['metadata'].append(tag)
            # 画师标签
            elif any(pattern in tag_lower for pattern in self.fallback_artist_patterns) or self._is_likely_artist(tag):
                categorized['artists'].append(tag)
            # 角色标签
            elif any(re.search(pattern, tag_lower) for pattern in self.fallback_character_patterns) or self._is_likely_character(tag):
                categorized['characters'].append(tag)
            # 版权标签
            elif any(pattern in tag_lower for pattern in self.fallback_copyright_patterns) or self._is_likely_copyright(tag):
                categorized['copyrights'].append(tag)
            # 其他归为一般标签
            else:
                categorized['general'].append(tag)
        
        return categorized
    
    def _is_likely_artist(self, tag):
        """判断是否可能是画师标签"""
        # 更严格的画师判断，避免误分类
        artist_patterns = [
            r'^[a-z]+_[a-z]+_artist$',  # 明确的画师标签
            r'^\w+_\(artist\)$',        # 带(artist)标记的
        ]
        return any(re.search(pattern, tag.lower()) for pattern in artist_patterns)
    
    def _is_likely_character(self, tag):
        """判断是否可能是角色标签"""
        character_patterns = [
            r'.*_\(.*\)$',       # 带括号的角色名
        ]
        return any(re.search(pattern, tag.lower()) for pattern in character_patterns)
    
    def _is_likely_copyright(self, tag):
        """判断是否可能是版权标签"""
        copyright_patterns = [
            r'.*_series$',       # 系列名
            r'.*_game$',         # 游戏名
            r'.*_anime$',        # 动画名
        ]
        return any(re.search(pattern, tag.lower()) for pattern in copyright_patterns)
    
    def _process_tags(self, tags_str):
        """处理AND标签"""
        if not tags_str:
            return ""
        tags = tags_str.rstrip(',').rstrip(' ').split(',')
        tags = [item.strip().replace(' ', '_').replace('\\', '') for item in tags]
        tags = [item for item in tags if item]
        return '+'.join(tags) if len(tags) > 1 else (tags[0] if tags else '')
    
    def _process_or_tags(self, tags_str, site):
        """处理OR标签"""
        if not tags_str:
            return ""
        tags = tags_str.rstrip(',').rstrip(' ').split(',')
        tags = [item.strip().replace(' ', '_').replace('\\', '') for item in tags]
        tags = [item for item in tags if item]
        if len(tags) > 1:
            if site == "Rule34":
                return '( ' + ' ~ '.join(tags) + ' )'
            else:
                return '{' + ' ~ '.join(tags) + '}'
        return tags[0] if tags else ''
    
    def _process_exclude_tags(self, tags_str):
        """处理排除标签"""
        if not tags_str:
            return ""
        return '+'.join('-' + item.strip().replace(' ', '_') for item in tags_str.split(',') if item.strip())
    
    def _build_rating_exclusion(self, Safe, Questionable, Explicit, site):
        """构建评级排除"""
        rate_exclusion = ""
        if not Safe: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3asafe"
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3ageneral"
        
        if not Questionable: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3aquestionable" 
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3aquestionable+-rating%3aSensitive"
        
        if not Explicit: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3aexplicit" 
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3aexplicit"
        
        return rate_exclusion
    
    def _format_tags(self, tags, format_type, category):
        """格式化标签"""
        if not tags:
            return ""
        
        if format_type == "hidden":
            return ""
        
        formatted_tags = []
        for tag in tags:
            if format_type == "original":
                formatted_tags.append(tag)
            elif format_type == "by_prefix" and category == "artist":
                formatted_tags.append(f"by {tag.replace('_', ' ')}")
            elif format_type == "from_prefix" and category == "copyright":
                formatted_tags.append(f"from {tag.replace('_', ' ')}")
            elif format_type == "parentheses":
                formatted_tags.append(f"({tag})")
            elif format_type == "brackets":
                formatted_tags.append(f"[{tag}]")
            elif format_type == "underscores":
                formatted_tags.append(tag.replace(' ', '_'))
            else:
                formatted_tags.append(tag)
        
        return ", ".join(formatted_tags)
    
    def _combine_tags_in_order(self, tag_list, separator):
        """按正确顺序组合标签：Artist-Character-Copyright-General-Metadata"""
        # 选择分隔符
        sep_map = {"comma": ", ", "space": " ", "newline": "\n"}
        sep = sep_map.get(separator, ", ")
        
        result_parts = []
        for tags, include in tag_list:
            if include and tags:
                result_parts.append(tags)
        
        return sep.join(result_parts)
    
    def _empty_result(self, error_msg):
        """返回空结果"""
        return ("", "", "", "", "", "", "", error_msg)


# 节点映射
NODE_CLASS_MAPPINGS = {
    "GelbooruAccurateExtractor": GelbooruAccurateExtractor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GelbooruAccurateExtractor": "Gelbooru Accurate Extractor",
}