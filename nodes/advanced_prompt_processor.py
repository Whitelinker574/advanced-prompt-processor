# -*- coding: utf-8 -*-
"""
高级提示词处理器 - 综合处理节点
整合分类、LLM增强、格式化等功能

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
from requests.exceptions import RequestException
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


class AdvancedPromptProcessor:
    """
    高级提示词处理器 - 综合处理节点
    整合提示词分类、LLM增强、格式化等全流程功能
    """
    
    # 类变量：将内置标签数据移到类级别，避免每次实例化重复创建
    _TAG_DATABASE = None
    _KNOWLEDGE_CACHE = {}
    _COMPILED_PATTERNS = None
    
    # 常量定义
    KNOWLEDGE_BASE_PATH = "Tag knowledge"
    MAX_LOG_LENGTH = 100
    DEFAULT_TIMEOUT = 30
    SYMBOL_PREFIX_ARTIST = "@"
    SYMBOL_PREFIX_CHARACTER = "#"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "danbooru_tags": ("STRING", {
                    "multiline": True, 
                    "default": "", 
                    "placeholder": "输入Danbooru标签，用逗号分隔"
                }),
                "drawing_theme": ("STRING", {
                    "multiline": True, 
                    "default": "", 
                    "placeholder": "绘图主题提示词（描述你想要的画面内容和风格）"
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
                "classification_mode": (["local_knowledge", "llm_classification"], {
                    "default": "local_knowledge"
                }),
                "custom_characters": ("STRING", {
                    "default": "", 
                    "placeholder": "自定义角色（逗号分隔），会直接添加到输出中"
                }),
                "custom_artists": ("STRING", {
                    "default": "", 
                    "placeholder": "自定义画师（逗号分隔），会直接添加到输出中"
                }),
                "custom_copyrights": ("STRING", {
                    "default": "", 
                    "placeholder": "自定义版权作品（逗号分隔），会直接添加到输出中"
                }),
                "enable_symbol_enhancement": ("BOOLEAN", {"default": True}),
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
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "DICT", "STRING")
    RETURN_NAMES = ("final_prompt", "enhanced_description", "formatted_prompt", "classified_tags", "processing_log")
    FUNCTION = "process_prompt"
    CATEGORY = "AI/Advanced Prompt"
    
    @classmethod 
    def _init_tag_database(cls):
        """初始化标签数据库（只在第一次使用时加载）"""
        if cls._TAG_DATABASE is None:
            cls._TAG_DATABASE = {
            "special": {
                "1girl", "1boy", "1other", "2girls", "2boys", "3girls", "3boys", 
                "4girls", "4boys", "5girls", "5boys", "6+girls", "6+boys",
                "multiple girls", "multiple boys", "solo", "duo", "group"
            },
            "general": {
                # 身体部位和特征
                "long_hair", "short_hair", "medium_hair", "brown_hair", "black_hair", "blonde_hair", 
                "white_hair", "silver_hair", "grey_hair", "red_hair", "pink_hair", "purple_hair",
                "blue_hair", "green_hair", "orange_hair", "twintails", "ponytail", "braid", "braids",
                "blue_eyes", "brown_eyes", "green_eyes", "red_eyes", "yellow_eyes", "purple_eyes",
                "grey_eyes", "heterochromia", "closed_eyes", "one_eye_closed", "wink",
                
                # 表情和动作
                "smile", "open_mouth", "closed_mouth", "fang", "fangs", ":d", ":o", ":3",
                "blush", "sweat", "tears", "crying", "angry", "sad", "happy", "surprised",
                "looking_at_viewer", "looking_away", "looking_back", "looking_down", "looking_up",
                "sitting", "standing", "walking", "running", "lying", "kneeling", "crouching",
                "arms_up", "arms_behind_back", "hands_on_hips", "peace_sign", "v", "thumbs_up",
                
                # 服装和配饰
                "dress", "skirt", "shirt", "blouse", "sweater", "jacket", "coat", "hoodie",
                "pants", "shorts", "jeans", "stockings", "thighhighs", "socks", "pantyhose",
                "shoes", "boots", "sandals", "high_heels", "sneakers", "bare_feet",
                "hat", "cap", "headband", "hair_ornament", "hair_bow", "ribbon", "bow",
                "glasses", "sunglasses", "jewelry", "necklace", "earrings", "bracelet",
                "gloves", "fingerless_gloves", "mittens", "scarf", "tie", "necktie", "bowtie",
                "underwear", "panties", "bra", "bikini", "swimsuit", "lingerie",
                "school_uniform", "sailor_dress", "maid", "nurse", "police", "military",
                "kimono", "yukata", "chinese_clothes", "qipao", "cheongsam",
                "open_clothes", "open_shirt", "open_jacket", "torn_clothes",
                "robe", "cloak", "cape", "apron", "vest", "tank_top", "crop_top",
                
                # 身体特征
                "horns", "tail", "wings", "ears", "animal_ears", "cat_ears", "fox_ears",
                "elf_ears", "pointed_ears", "long_ears", "fin_ears",
                "small_breasts", "medium_breasts", "large_breasts", "huge_breasts",
                "flat_chest", "cleavage", "sideboob", "underboob",
                "thick_thighs", "wide_hips", "slim", "curvy", "muscular",
                "pale_skin", "dark_skin", "tan", "dark_skinned_female",
                "scar", "bandages", "tattoo", "piercing",
                
                # 手和指甲
                "fingernails", "long_fingernails", "sharp_fingernails", "colored_nails",
                "nail_polish", "nail_art", "black_nails", "red_nails", "blue_nails",
                "manicure", "claw_pose", "finger_gun", "pointing",
                
                # 眼睛特征
                "slit_pupils", "heart-shaped_pupils", "star-shaped_pupils", "cross-shaped_pupils",
                "glowing_eyes", "empty_eyes", "spiral_eyes", "x_x", "@_@",
                "eyelashes", "long_eyelashes", "thick_eyelashes", "makeup", "eyeshadow",
                "eyeliner", "mascara", "lipstick", "lip_gloss",
                
                # 场景和背景
                "indoors", "outdoors", "bedroom", "bathroom", "kitchen", "living_room",
                "classroom", "school", "library", "office", "hospital", "park", "garden",
                "beach", "ocean", "forest", "mountain", "city", "street", "rooftop",
                "sky", "clouds", "sunset", "sunrise", "night", "starry_sky", "moon",
                "rain", "snow", "cherry_blossoms", "flowers", "trees", "grass",
                "building", "house", "bridge", "tower", "castle", "temple", "shrine",
                
                # 物品和道具
                "umbrella", "bag", "backpack", "book", "pen", "pencil", "paper",
                "phone", "computer", "laptop", "tablet", "camera", "microphone",
                "sword", "katana", "knife", "dagger", "gun", "rifle", "pistol",
                "shield", "armor", "helmet", "crown", "tiara", "staff", "wand",
                "ball", "balloon", "teddy_bear", "stuffed_animal", "doll",
                "food", "cake", "ice_cream", "coffee", "tea", "water", "bottle",
                "flower", "rose", "sunflower", "bouquet", "gift", "present",
                "mirror", "window", "door", "chair", "table", "bed", "pillow",
                "lamp", "candle", "fire", "flame", "smoke", "steam",
                
                # 姿势和角度
                "full_body", "upper_body", "lower_body", "portrait", "close-up",
                "from_above", "from_below", "from_side", "from_behind", "back_view",
                "profile", "three-quarter_view", "straight-on", "diagonal",
                "cowboy_shot", "dutch_angle", "bird's_eye_view", "worm's_eye_view"
            },
            "quality": {
                "masterpiece", "best quality", "high quality", "normal quality", "low quality",
                "worst quality", "jpeg artifacts", "signature", "watermark", "username",
                "blurry", "artist name", "trademark", "title", "bad anatomy", "bad hands",
                "text", "error", "missing fingers", "extra digit", "fewer digits",
                "cropped", "absurdres", "highres", "lowres"
            },
            "meta": {
                "realistic", "photorealistic", "photo", "cosplay", "real person",
                "official art", "promotional art", "scan", "magazine scan",
                "web", "pixiv", "twitter", "artstation", "deviantart", "tumblr"
            },
            "rating": {
                "rating:safe", "rating:questionable", "rating:explicit", "rating:sensitive",
                "safe", "sensitive", "questionable", "explicit", "nsfw", "sfw"
            }
        }
        
        return cls._TAG_DATABASE
    
    @classmethod
    def _init_patterns(cls):
        """初始化编译后的正则表达式模式"""
        if cls._COMPILED_PATTERNS is None:
            import re
            cls._COMPILED_PATTERNS = {
                'character_patterns': [
                    re.compile(r"^\w+\s+\(\w+\)$"),  # 角色名 (作品名)
                    re.compile(r"^\w+_\w+_\w+$"),    # 三段式角色名
                ],
                'non_character_patterns': [
                    re.compile(r".*_hair$"), re.compile(r".*_eyes$"), re.compile(r".*_clothes$"), 
                    re.compile(r".*_dress$"), re.compile(r".*_shirt$"), re.compile(r".*_mouth$"), 
                    re.compile(r".*_pupils$"), re.compile(r".*_polish$"), re.compile(r".*_art$"), 
                    re.compile(r".*_nails$"), re.compile(r".*_fingernails$"), re.compile(r".*_eyelashes$"), 
                    re.compile(r".*_makeup$"), re.compile(r".*_uniform$")
                ],
                'artist_patterns': [
                    re.compile(r"^by\s+\w+"),        # by 画师名
                    re.compile(r"artist:\w+"),       # artist:画师名
                ]
            }
        return cls._COMPILED_PATTERNS
    
    @property
    def tag_database(self):
        """获取标签数据库（懒加载）"""
        return self._init_tag_database()
    
    @property  
    def copyright_keywords(self):
        """版权作品关键词"""
        return {
            "vocaloid", "touhou", "fate", "pokemon", "naruto", "bleach", "one_piece",
            "dragon_ball", "attack_on_titan", "demon_slayer", "jujutsu_kaisen", 
            "genshin_impact", "honkai_impact", "azur_lane", "kantai_collection",
            "love_live", "idolmaster", "persona", "final_fantasy", "overwatch"
        }
    
    @property
    def character_patterns(self):
        """获取编译后的角色匹配模式"""
        return self._init_patterns()['character_patterns']
    
    @property
    def non_character_patterns(self):
        """获取编译后的非角色匹配模式"""
        return self._init_patterns()['non_character_patterns']
    
    @property
    def artist_patterns(self):
        """获取编译后的画师匹配模式"""
        return self._init_patterns()['artist_patterns']

    def __init__(self):
        # 轻量级初始化
        self.debug_mode = False

    def safe_log(self, message: str, level: str = "info"):
        """安全的日志记录方法（为了兼容性保留，实际不执行操作）"""
        pass

    @staticmethod
    def clean_tag(tag: str) -> str:
        """统一的标签清理函数"""
        return tag.strip().lower().replace(' ', '_')
    
    @staticmethod
    def parse_tags_from_string(text: str) -> list:
        """从文本中解析标签列表"""
        if not text.strip():
            return []
        return [AdvancedPromptProcessor.clean_tag(tag) for tag in text.split(',') if tag.strip()]
    
    def parse_custom_tags(self, custom_text: str) -> list:
        """解析自定义标签文本（逗号分隔）"""
        return self.parse_tags_from_string(custom_text)

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

    def classify_tags(self, tags: str, custom_chars: set, custom_artists: set, custom_copyrights: set) -> Dict[str, List[str]]:
        """分类标签"""
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        classified = {
            "special": [],
            "characters": [],
            "copyrights": [],
            "artists": [],
            "general": [],
            "quality": [],
            "meta": [],
            "rating": []
        }
        
        for tag in tag_list:
            category = self.classify_single_tag(tag, custom_chars, custom_artists, custom_copyrights)
            classified[category].append(tag)
        
        return classified

    def classify_single_tag(self, tag: str, custom_chars: set, custom_artists: set, custom_copyrights: set) -> str:
        """分类单个标签"""
        tag_lower = tag.lower().strip()
        
        # 检查预定义类别
        for category, tags in self.tag_database.items():
            if tag_lower in tags:
                return category
        
        # 检查自定义标签
        if tag in custom_chars:
            return "characters"
        if tag in custom_artists:
            return "artists"
        if tag in custom_copyrights:
            return "copyrights"
        
        # 检查版权关键词
        if tag_lower in self.copyright_keywords:
            return "copyrights"
        
        # 首先检查非角色模式，防止误分类
        for pattern in self.non_character_patterns:
            if pattern.match(tag_lower):
                return "general"
        
        # 基于模式匹配
        for pattern in self.character_patterns:
            if pattern.match(tag):
                return "characters"
        
        for pattern in self.artist_patterns:
            if pattern.match(tag):
                return "artists"
        
        return "general"

    def load_knowledge_base_from_folder(self, folder_path: str) -> Dict[str, Dict]:
        """从文件夹加载知识库（带缓存）"""
        # 检查缓存
        if folder_path in self._KNOWLEDGE_CACHE:
            return self._KNOWLEDGE_CACHE[folder_path]
        
        knowledge_base = self._load_knowledge_base_internal(folder_path)
        
        # 缓存结果
        self._KNOWLEDGE_CACHE[folder_path] = knowledge_base
        return knowledge_base
    
    def _load_knowledge_base_internal(self, folder_path: str) -> Dict[str, Dict]:
        """从文件夹加载知识库（自动读取所有相关文件）"""
        if not folder_path:
            return {}
        
        # 确保路径是相对于插件目录的
        if not os.path.isabs(folder_path):
            plugin_dir = os.path.dirname(os.path.dirname(__file__))
            folder_path = os.path.join(plugin_dir, folder_path)
        
        if not os.path.exists(folder_path):
            self.safe_log(f"知识库文件夹不存在: {folder_path}", "warning")
            return {}
        
        knowledge_base = {
            "special": set(),
            "characters": set(),
            "copyrights": set(),
            "artists": set(),
            "general": set(),
            "quality": set(),
            "meta": set(),
            "rating": set()
        }
        
        try:
            # 预定义的文件名映射
            category_files = {
                "special": ["special.csv", "人数标签.csv"],
                "characters": ["characters.csv", "角色.csv", "character.csv"],
                "copyrights": ["copyrights.csv", "版权.csv", "copyright.csv"],
                "artists": ["artists.csv", "画师.csv", "artist.csv"],
                "general": ["general.csv", "通用.csv"],
                "quality": ["quality.csv", "质量.csv"],
                "meta": ["meta.csv", "元数据.csv", "metadata.csv"],
                "rating": ["rating.csv", "评级.csv"]
            }
            
            loaded_files = []
            
            # 加载每个类别的文件
            for category, possible_names in category_files.items():
                for filename in possible_names:
                    file_path = os.path.join(folder_path, filename)
                    if os.path.exists(file_path):
                        tags = self._load_category_csv_file(file_path)
                        knowledge_base[category].update(tags)
                        loaded_files.append(filename)
                        break  # 找到一个就跳出
            
            # 检查是否有通用的knowledge_base.csv文件
            general_csv = os.path.join(folder_path, "knowledge_base.csv")
            if os.path.exists(general_csv):
                general_knowledge = self._load_csv_knowledge_base(general_csv)
                for category, tags in general_knowledge.items():
                    if category in knowledge_base:
                        knowledge_base[category].update(tags)
                loaded_files.append("knowledge_base.csv")
            
            self.safe_log(f"从知识库文件夹加载了 {len(loaded_files)} 个文件: {', '.join(loaded_files)}")
            
            # 转换为字典格式
            return {category: tags for category, tags in knowledge_base.items()}
            
        except Exception as e:
            self.safe_log(f"加载知识库文件夹失败: {e}", "error")
            return {}
    
    def _load_category_csv_file(self, file_path: str) -> set:
        """加载单个类别的CSV文件"""
        import csv
        tags = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 读取第一行判断格式
                first_line = f.readline().strip()
                f.seek(0)
                
                # 判断是否为CSV格式（包含逗号和可能的标题行）
                if ',' in first_line and ('tag' in first_line.lower() or 'description' in first_line.lower()):
                    # 有标题的CSV格式
                    csv_reader = csv.DictReader(f)
                    tag_column = None
                    
                    # 查找标签列（优先级顺序）
                    possible_columns = ['tag', 'tags', '标签', 'name', '名称']
                    for col in possible_columns:
                        if col in csv_reader.fieldnames:
                            tag_column = col
                            break
                    
                    if tag_column:
                        for row in csv_reader:
                            tag = row[tag_column].strip()
                            if tag and not tag.startswith('#') and tag != tag_column:  # 避免把列名当作标签
                                tags.add(tag.lower())
                        # self.safe_log(f"从CSV文件加载 {len(tags)} 个标签: {os.path.basename(file_path)}")
                        pass  # 静默处理，避免频繁日志
                    else:
                        self.safe_log(f"警告: 在CSV文件中未找到标签列 {file_path}", "warning")
                
                elif ',' in first_line:
                    # 无标题的CSV格式，第一列为标签
                    f.seek(0)
                    csv_reader = csv.reader(f)
                    for row in csv_reader:
                        if row and len(row) > 0:
                            tag = row[0].strip()
                            if tag and not tag.startswith('#'):
                                tags.add(tag.lower())
                    # self.safe_log(f"从无标题CSV文件加载 {len(tags)} 个标签: {os.path.basename(file_path)}")
                    pass  # 静默处理，避免频繁日志
                
                else:
                    # 纯文本格式，每行一个标签
                    f.seek(0)
                    for line in f:
                        tag = line.strip()
                        if tag and not tag.startswith('#') and tag != 'tag':  # 避免把"tag"标题当作标签
                            tags.add(tag.lower())
                    # self.safe_log(f"从文本文件加载 {len(tags)} 个标签: {os.path.basename(file_path)}")
                    pass  # 静默处理，避免频繁日志
                            
        except Exception as e:
            self.safe_log(f"加载文件失败 {file_path}: {e}", "error")
        
        return tags
    
    def _load_csv_knowledge_base(self, file_path: str) -> Dict[str, Dict]:
        """加载CSV格式的知识库"""
        import csv
        knowledge_base = {
            "special": set(),
            "characters": set(),
            "copyrights": set(),
            "artists": set(),
            "general": set(),
            "quality": set(),
            "meta": set(),
            "rating": set()
        }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            
            # 检查必需的列
            if 'tag' not in csv_reader.fieldnames or 'category' not in csv_reader.fieldnames:
                self.safe_log("CSV文件必须包含'tag'和'category'列", "error")
                return {}
            
            for row in csv_reader:
                tag = row['tag'].strip()
                category = row['category'].strip().lower()
                
                if tag and category in knowledge_base:
                    knowledge_base[category].add(tag.lower())
        
        # 转换为字典格式（与原格式兼容）
        return {category: tags for category, tags in knowledge_base.items()}
    
    def _load_json_knowledge_base(self, file_path: str) -> Dict[str, Dict]:
        """加载JSON格式的知识库"""
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_classification_llm_prompt(self) -> str:
        """获取LLM分类的系统提示词"""
        return """你是一个专业的Danbooru标签分类器。请严格按照以下8个类别对标签进行分类：

1. **special**: 人数和基本组合信息
   - 例子: 1girl, 1boy, 2girls, 3boys, solo, multiple girls, multiple boys, duo, group

2. **characters**: 具体的角色名称（动漫、游戏、虚拟角色等）
   - 例子: hatsune miku, reimu hakurei, pikachu, naruto uzumaki, artoria pendragon

3. **copyrights**: 版权作品、系列、品牌名称
   - 例子: vocaloid, touhou, pokemon, naruto, fate/grand order, original

4. **artists**: 画师、作者名称
   - 例子: wlop, artgerm, by xxx, artist:xxx 等画师相关标签

5. **general**: 通用描述标签（外观、服装、动作、表情、场景等）
   - 例子: long hair, blue eyes, school uniform, smile, standing, outdoors

6. **quality**: 图片质量和美术质量相关
   - 例子: masterpiece, best quality, high quality, worst quality, blurry, jpeg artifacts

7. **meta**: 技术元数据、分辨率、来源等
   - 例子: highres, absurdres, official art, scan, pixiv, twitter

8. **rating**: 内容分级和审查相关
   - 例子: safe, questionable, explicit, nsfw, sfw, rating:safe

分类规则：
- 如果不确定，优先分类到general
- 保持原始标签格式，不要修改
- 每个标签只能属于一个类别
- 确保所有输入标签都被分类

请以严格的JSON格式返回，不要添加任何解释：
{
  "special": [],
  "characters": [],
  "copyrights": [],
  "artists": [],
  "general": [],
  "quality": [],
  "meta": [],
  "rating": []
}"""

    def classify_tags_with_llm(self, tags: str, api_url: str, api_key: str, model_name: str, proxy_http: str = "", proxy_https: str = "") -> Dict[str, List[str]]:
        """使用LLM进行标签分类"""
        if not api_key:
            return self.classify_tags(tags, set(), set(), set())
        
        system_prompt = self.get_classification_llm_prompt()
        user_prompt = f"请对以下标签进行分类：{tags}"
        
        try:
            response = self.call_classification_llm_api(api_url, api_key, model_name, system_prompt, user_prompt, proxy_http, proxy_https)
            
            if response.startswith("API调用失败"):
                self.safe_log(f"LLM分类API调用失败，回退到本地分类: {response}", "warning")
                return self.classify_tags(tags, set(), set(), set())
            
            # 尝试解析JSON响应
            import json
            # 清理响应内容
            clean_response = response.strip()
            
            # 提取JSON部分
            json_start = clean_response.find('{')
            json_end = clean_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = clean_response[json_start:json_end]
                try:
                    classified = json.loads(json_str)
                    
                    # 验证分类结果格式
                    expected_keys = ["special", "characters", "copyrights", "artists", "general", "quality", "meta", "rating"]
                    for key in expected_keys:
                        if key not in classified:
                            classified[key] = []
                        # 确保每个值都是列表
                        if not isinstance(classified[key], list):
                            classified[key] = []
                    
                    # 验证分类结果不为空
                    total_tags = sum(len(v) for v in classified.values())
                    input_tags = len([tag.strip() for tag in tags.split(',') if tag.strip()])
                    
                    self.safe_log(f"LLM分类结果: 输入{input_tags}个标签，分类了{total_tags}个标签")
                    
                    if total_tags > 0:
                        return classified
                    else:
                        self.safe_log("LLM分类结果为空，回退到本地分类", "warning")
                        return self.classify_tags(tags, set(), set(), set())
                        
                except json.JSONDecodeError as e:
                    self.safe_log(f"JSON解析失败: {e}, 响应内容: {json_str[:200]}...", "error")
                    return self.classify_tags(tags, set(), set(), set())
            else:
                self.safe_log(f"无法从响应中提取JSON，响应内容: {clean_response[:200]}...", "error")
                return self.classify_tags(tags, set(), set(), set())
                
        except Exception as e:
            self.safe_log(f"LLM分类异常，回退到本地分类: {e}", "error")
            return self.classify_tags(tags, set(), set(), set())

    def classify_tags_with_knowledge_base(self, tags: str, knowledge_base: Dict, 
                                        custom_chars: set, custom_artists: set, custom_copyrights: set) -> Dict[str, List[str]]:
        """使用知识库进行标签分类"""
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        classified = {
            "special": [],
            "characters": [],
            "copyrights": [],
            "artists": [],
            "general": [],
            "quality": [],
            "meta": [],
            "rating": []
        }
        
        # 合并知识库和内置数据库（外部知识库优先级更高）
        merged_database = {}
        
        # 首先加载内置数据库
        for category, tags in self.tag_database.items():
            merged_database[category] = set(tags) if not isinstance(tags, set) else tags.copy()
        
        # 然后合并外部知识库，并处理重复标签（按优先级顺序处理）
        if knowledge_base:
            # 按优先级顺序处理类别，确保重要类别的标签不被覆盖
            priority_order = ['special', 'quality', 'rating', 'meta', 'characters', 'copyrights', 'artists', 'general']
            
            # 收集所有已分类的标签，避免重复
            classified_tags = set()
            
            for category in priority_order:
                if category in knowledge_base:
                    external_tags = knowledge_base[category]
                    
                    if category not in merged_database:
                        merged_database[category] = set()
                    
                    # 确保是set类型
                    if not isinstance(merged_database[category], set):
                        merged_database[category] = set(merged_database[category])
                    if not isinstance(external_tags, set):
                        external_tags = set(external_tags)
                    
                    # 只添加尚未被分类的标签
                    new_tags = external_tags - classified_tags
                    merged_database[category].update(new_tags)
                    classified_tags.update(new_tags)
            
            # 处理其他未按优先级处理的类别
            for category, external_tags in knowledge_base.items():
                if category not in priority_order:
                    if category not in merged_database:
                        merged_database[category] = set()
                    
                    if not isinstance(external_tags, set):
                        external_tags = set(external_tags)
                    
                    new_tags = external_tags - classified_tags
                    merged_database[category].update(new_tags)
                    classified_tags.update(new_tags)
        
        # 确保所有未分类的标签都有默认类别
        for category in ["special", "characters", "copyrights", "artists", "general", "quality", "meta", "rating"]:
            if category not in merged_database:
                merged_database[category] = set()
        
        for tag in tag_list:
            category = self.classify_single_tag_with_knowledge(tag, merged_database, custom_chars, custom_artists, custom_copyrights)
            classified[category].append(tag)
        
        return classified

    def classify_single_tag_with_knowledge(self, tag: str, knowledge_base: Dict, 
                                         custom_chars: set, custom_artists: set, custom_copyrights: set) -> str:
        """使用知识库分类单个标签（优化版本）"""
        tag_lower = tag.lower().strip()
        
        # 按优先级顺序检查，避免不必要的循环
        
        # 1. 检查special类别（最高优先级，通常是数量标签）
        if 'special' in knowledge_base and tag_lower in knowledge_base['special']:
            return "special"
        
        # 2. 检查自定义标签（用户指定的优先级高）
        if tag in custom_chars:
            return "characters"
        if tag in custom_artists:
            return "artists"
        if tag in custom_copyrights:
            return "copyrights"
        
        # 3. 检查quality和rating（这些很重要且数量少）
        for priority_category in ['quality', 'rating']:
            if priority_category in knowledge_base and tag_lower in knowledge_base[priority_category]:
                return priority_category
        
        # 4. 检查非角色模式，防止常见标签被误分类为角色
        for pattern in self.non_character_patterns:
            if pattern.match(tag_lower):
                return "general"
        
        # 5. 检查general类别（最大的类别，但在模式匹配之前检查）
        if 'general' in knowledge_base and tag_lower in knowledge_base['general']:
            return "general"
        
        # 6. 检查characters和copyrights（在general之后，避免误分类）
        if 'characters' in knowledge_base and tag_lower in knowledge_base['characters']:
            return "characters"
        
        if 'copyrights' in knowledge_base and tag_lower in knowledge_base['copyrights']:
            return "copyrights"
        
        # 7. 检查版权关键词
        if tag_lower in self.copyright_keywords:
            return "copyrights"
        
        # 8. 检查artists和meta
        if 'artists' in knowledge_base and tag_lower in knowledge_base['artists']:
            return "artists"
        
        if 'meta' in knowledge_base and tag_lower in knowledge_base['meta']:
            return "meta"
        
        # 9. 基于模式匹配（最后的fallback）
        for pattern in self.character_patterns:
            if pattern.match(tag):
                return "characters"
        
        for pattern in self.artist_patterns:
            if pattern.match(tag):
                return "artists"
        
        # 10. 默认返回general
        return "general"

    def replace_numbers_with_english(self, text: str) -> str:
        """将数字替换为英文"""
        number_map = {
            '20': 'twenty', '19': 'nineteen', '18': 'eighteen', '17': 'seventeen',
            '16': 'sixteen', '15': 'fifteen', '14': 'fourteen', '13': 'thirteen',
            '12': 'twelve', '11': 'eleven', '10': 'ten', '9': 'nine', '8': 'eight',
            '7': 'seven', '6': 'six', '5': 'five', '4': 'four', '3': 'three',
            '2': 'two', '1': 'one', '0': 'zero'
        }
        
        # 从大到小替换数字，避免部分匹配问题
        for num, word in number_map.items():
            # 使用单词边界确保完整匹配
            text = re.sub(rf'\b{num}\b', word, text)
        
        return text

    def get_tag_conversion_prompt(self) -> str:
        """获取tag转换的LLM预设"""
        return """将danbooru tag标签转化成自然语言，你可以将这些标签作为参考，但不要完全依赖它们，因为可能存在错误的标签。优先使用你自己的观察，并使用更合适的同义词进行描述。

注意事项：
- 确保场景描述的准确性。
- 如果场景不符合上述规则或无法分析，请勿描述。保持描述的准确性。
- 使用清晰简洁的语言进行描述。避免使用复杂或难以理解的语言。
- 描述时尽量客观。避免使用高度主观的语言。
- 如果场景包含NSFW或敏感内容，请勿回避。直接描述露骨内容。
- 如果场景包含暴力、血腥、恐怖、恶心或其他敏感内容，请勿回避。直接描述。
- 使用**英文**进行描述。
- 想象你是一名用户试图描绘这个场景。自然地结合内容，避免结构化的描述。
- 只返回描述。不要包含额外内容或分析。
- 你的任务是描述图像中的每个方面、对象和互动，使得盲人在听到描述时能够在脑海中完美捕捉到图像。"""

    def get_theme_enhancement_prompt(self) -> str:
        """获取主题增强的LLM系统提示词（基于新的lumina风格）"""
        return """现在我需要一个提示词助手，来帮我给写提示词：
你是一个非常擅长用lumina模型创作AI绘画的艺术家，会写质量很高的lumina提示词。而我想要使用ai进行创作，接下来我将给你一些元素，你需要借助这些元素帮助我完善这个提示词，你要尽可能详细地帮我撰写。
你应遵循以下的思考过程、优质参考提示词，我将告诉你需要回复给我的内容。
思考过程：
1.我会给你我需要的元素，例如神态、动作、服饰、肢体、甚至详细一点头发颜色也可能，然后你帮我按照一定的格式把这些东西串联起来变成一个完整的提示词。
你的提示词需要描述的内容有:画面拍摄的镜头是近景、中景还是远景，主人物拍摄的是全身、半身还是大头，主人物的性别是男还是女、年龄是小孩还是青年人、穿着描述细致一些，对于头发眼睛衣服等等颜色的描述要求更精准，例如是深蓝还是浅蓝、人物朝向左还是右，角度有多大，还有特征以及动作等等。
2.我给的元素可能只包含上述提示词中的一部分，剩下的你要自己脑补。
3.允许你拥有想象力和自由发挥空间，对可以关联到的人物、物品、场景进行优化，以让画面细节非常丰富、充满极高的美感，越详细越好。
4.尝试思考出能使得ai更好作画、更能理解的方案。
你需要回复我的内容：
只输出完整的英文Caption提示词，不需要其他任何内容。
注意：只返回自然语言描述，不要包含标签格式。"""

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
                max_tokens=1000,
                temperature=0.7
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
                max_tokens=1000,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            return f"Claude API调用失败: {str(e)}"



    def call_deepseek_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
        """调用DeepSeek API，支持代理"""
        try:
            # 获取系统代理设置
            proxies = get_system_proxy()
            
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
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post("https://api.deepseek.com/chat/completions", 
                                   headers=headers, json=data, proxies=proxies, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            return f"DeepSeek API调用失败: {str(e)}"

    def call_custom_api(self, api_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
        """调用自定义API，支持代理"""
        try:
            # 清理和验证API URL
            clean_api_url = self.clean_and_validate_url(api_url)
            
            # 获取系统代理设置
            proxies = get_system_proxy()
            
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
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(clean_api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=self.DEFAULT_TIMEOUT)
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
            return self.call_gemini_api(api_key, model_name, system_prompt, user_prompt, custom_api_url)
        elif ai_model == "deepseek":
            return self.call_deepseek_api(api_key, model_name, system_prompt, user_prompt)
        elif ai_model == "custom":
            if not custom_api_url:
                return "自定义模式需要提供API URL"
            return self.call_custom_api(custom_api_url, api_key, model_name, system_prompt, user_prompt)
        else:
            return f"不支持的AI模型: {ai_model}"

    def enhance_with_llm(self, tags: str, drawing_theme: str, api_url: str, api_key: str, model_name: str, proxy_http: str = "", proxy_https: str = "") -> str:
        """使用LLM增强提示词，根据输入情况选择不同策略"""
        if not api_key:
            return ""
        
        has_tags = bool(tags.strip())
        has_theme = bool(drawing_theme.strip())
        
        if has_tags and has_theme:
            # 同时有tag和绘图主题：使用新的主题增强策略
            system_prompt = self.get_theme_enhancement_prompt()
            user_prompt = f"请以以下内容（绘图主题提示词）主题结合tag提示词生成内容：\n主题：{drawing_theme}\nTag提示词：{tags}"
            
        elif has_tags and not has_theme:
            # 只有tag：转换为自然语言
            system_prompt = self.get_tag_conversion_prompt()
            user_prompt = f"请将以下danbooru标签转换为自然语言描述：{tags}"
            
        elif not has_tags and has_theme:
            # 只有绘图主题：使用主题增强
            system_prompt = self.get_theme_enhancement_prompt()
            user_prompt = drawing_theme
            
        else:
            # 都没有输入
            return ""
        
        return self.call_simple_llm_api(api_url, api_key, model_name, system_prompt, user_prompt, proxy_http, proxy_https)



    def call_simple_llm_api(self, api_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, proxy_http: str = "", proxy_https: str = "") -> str:
        """简化的LLM API调用，支持Gemini自动格式转换和代理"""
        try:
            # 清理和验证API URL
            clean_api_url = self.clean_and_validate_url(api_url)
            
            # 获取代理设置（优先使用手动设置）
            proxies = get_system_proxy(proxy_http, proxy_https)
            if proxies:
                self.safe_log(f"🌐 使用代理设置: {proxies}")
            
            # 检测Gemini API并自动转换格式
            if "generativelanguage.googleapis.com" in clean_api_url or "gemini" in model.lower():
                return self._call_gemini_api(api_key, model, system_prompt, user_prompt, proxies)
            
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
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(clean_api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.Timeout:
            return "API调用超时，请检查网络连接"
        except Exception as e:
            return f"API调用失败: {str(e)}"

    def _call_gemini_api(self, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """简化的Gemini API调用，参考 gemini_nodes.py 的正确实现"""
        try:
            # 验证和修正模型名称
            corrected_model = self._validate_gemini_model_name(model)
            
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
                self.safe_log(f"🌐 使用代理 (httpx格式): {httpx_proxies}")
            else:
                self.safe_log("🌐 未使用代理")
            
            # 创建 httpx 客户端
            client = httpx.Client(
                base_url="https://generativelanguage.googleapis.com",
                params={'key': api_key},
                proxies=httpx_proxies,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            try:
                # 构建请求体
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                body = {
                    "contents": [{
                        "parts": [{"text": combined_prompt}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 4000,
                        "temperature": 0.7
                    }
                }
                
                # 使用相对端点路径
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
                    return f"Gemini API请求错误: {error_detail}"
                
                response.raise_for_status()
                
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            return parts[0]['text'].strip()
                
                return "Gemini API响应格式异常"
                
            finally:
                client.close()
            
        except ImportError:
            # 如果 httpx 不可用，回退到 requests 方法
            return self._call_gemini_api_requests_fallback(api_key, model, system_prompt, user_prompt, proxies)
        except Exception as e:
            return f"Gemini API调用失败: {str(e)}"
    
    def _call_gemini_api_requests_fallback(self, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """使用 requests 的 Gemini API 调用备用方法"""
        try:
            corrected_model = self._validate_gemini_model_name(model)
            
            # 修正：API 密钥应该通过 URL 参数传递，而不是 header
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{corrected_model}:generateContent?key={api_key}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            data = {
                "contents": [{
                    "parts": [{"text": combined_prompt}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 4000,
                    "temperature": 0.7
                }
            }
            
            response = requests.post(api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=self.DEFAULT_TIMEOUT)
            
            # 增强错误处理
            if response.status_code == 400:
                error_detail = ""
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', {}).get('message', '未知错误')
                except:
                    error_detail = f"HTTP 400 - 请检查模型名称和 API 密钥"
                return f"Gemini API请求错误: {error_detail}"
            
            response.raise_for_status()
            
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        return parts[0]['text'].strip()
            
            return "Gemini API响应格式异常"
            
        except requests.exceptions.Timeout:
            return "Gemini API调用超时"
        except Exception as e:
            return f"Gemini API调用失败: {str(e)}"
    
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
            self.safe_log(f"🔧 Gemini模型名称修正: {model} -> {corrected}")
            return corrected
        
        # 如果模型名已经正确或未知，直接返回
        return model

    def call_classification_llm_api(self, api_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, proxy_http: str = "", proxy_https: str = "") -> str:
        """专门用于分类的LLM API调用，使用更低的temperature以获得更稳定的结果"""
        try:
            # 清理和验证API URL
            clean_api_url = self.clean_and_validate_url(api_url)
            
            # 获取代理设置（优先使用手动设置）
            proxies = get_system_proxy(proxy_http, proxy_https)
            
            # 检测是否为Gemini API
            if "generativelanguage.googleapis.com" in clean_api_url or "gemini" in model.lower():
                return self._call_gemini_classification(api_key, model, system_prompt, user_prompt, proxies)
            
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
                "max_tokens": 2000,  # 分类需要更多token
                "temperature": 0.1   # 分类需要更确定性的输出
            }
            
            response = requests.post(clean_api_url, headers=headers, json=data, 
                                   proxies=proxies, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.Timeout:
            return "分类API调用超时"
        except Exception as e:
            return f"API调用失败: {str(e)}"
    
    def _call_gemini_classification(self, api_key: str, model: str, system_prompt: str, user_prompt: str, proxies=None) -> str:
        """简化的Gemini分类API调用，参考 gemini_nodes.py 的正确实现"""
        try:
            # 验证和修正模型名称
            corrected_model = self._validate_gemini_model_name(model)
            
            try:
                # 尝试使用 httpx（推荐方式）
                import httpx
                
                # 转换代理格式为 httpx 兼容格式
                httpx_proxies = None
                if proxies:
                    httpx_proxies = {}
                    if 'http' in proxies and proxies['http']:
                        httpx_proxies['http://'] = proxies['http']
                    if 'https' in proxies and proxies['https']:
                        httpx_proxies['https://'] = proxies['https']
                    self.safe_log(f"🌐 分类API使用代理 (httpx格式): {httpx_proxies}")
                else:
                    self.safe_log("🌐 分类API未使用代理")
                
                client = httpx.Client(
                    base_url="https://generativelanguage.googleapis.com",
                    params={'key': api_key},
                    proxies=httpx_proxies,
                    timeout=self.DEFAULT_TIMEOUT
                )
                
                try:
                    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                    
                    body = {
                        "contents": [{
                            "parts": [{"text": combined_prompt}]
                        }],
                        "generationConfig": {
                            "maxOutputTokens": 2000,
                            "temperature": 0.1
                        }
                    }
                    
                    endpoint = f"/v1beta/models/{corrected_model}:generateContent"
                    response = client.post(endpoint, json=body)
                    
                    if response.status_code == 400:
                        error_detail = ""
                        try:
                            error_json = response.json()
                            error_detail = error_json.get('error', {}).get('message', '未知错误')
                        except:
                            error_detail = f"HTTP 400 - 请检查模型名称和 API 密钥"
                        return f"Gemini分类API请求错误: {error_detail}"
                    
                    response.raise_for_status()
                    
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            parts = candidate['content']['parts']
                            if len(parts) > 0 and 'text' in parts[0]:
                                return parts[0]['text'].strip()
                    
                    return "Gemini分类API响应格式异常"
                    
                finally:
                    client.close()
                    
            except ImportError:
                # 回退到 requests 方法
                corrected_model = self._validate_gemini_model_name(model)
                
                # 修正：API 密钥通过 URL 参数传递
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{corrected_model}:generateContent?key={api_key}"
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": combined_prompt}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 2000,
                        "temperature": 0.1
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=data, 
                                       proxies=proxies, timeout=self.DEFAULT_TIMEOUT)
                
                if response.status_code == 400:
                    error_detail = ""
                    try:
                        error_json = response.json()
                        error_detail = error_json.get('error', {}).get('message', '未知错误')
                    except:
                        error_detail = f"HTTP 400 - 请检查模型名称和 API 密钥"
                    return f"Gemini分类API请求错误: {error_detail}"
                
                response.raise_for_status()
                
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            return parts[0]['text'].strip()
                
                return "Gemini分类API响应格式异常"
            
        except Exception as e:
            return f"Gemini分类API调用失败: {str(e)}"

    def apply_text_formatting(self, text: str) -> str:
        """应用文本格式化处理"""
        if not text:
            return text
        
        # 去除下划线，替换为空格
        text = re.sub(r'_', ' ', text)
        
        # 转义括号（除了权重括号）
        # 保护权重括号格式 (tag:weight)
        protected_weights = []
        weight_pattern = r'\([^:()]+:\d*\.?\d+\)'
        
        # 提取并保护权重括号
        matches = re.finditer(weight_pattern, text)
        for i, match in enumerate(matches):
            placeholder = f"__WEIGHT_{i}__"
            protected_weights.append((placeholder, match.group()))
            text = text.replace(match.group(), placeholder)
        
        # 转义普通括号
        text = re.sub(r'\((?![^:()]+:\d*\.?\d+\))', r'\\(', text)
        text = re.sub(r'(?<!\d)\)', r'\\)', text)
        
        # 恢复权重括号
        for placeholder, original in protected_weights:
            text = text.replace(placeholder, original)
        
        return text

    def apply_symbol_enhancement(self, classified_tags: Dict[str, List[str]], enable_enhancement: bool) -> Dict[str, List[str]]:
        """应用符号强化到指定类别的标签"""
        if not enable_enhancement:
            return classified_tags
        
        result = classified_tags.copy()
        
        # 应用角色符号强化：前缀#
        if result.get("characters"):
            enhanced_characters = []
            for tag in result["characters"]:
                # 将空格替换为下划线，并添加符号前缀
                enhanced_tag = f"{self.SYMBOL_PREFIX_CHARACTER}{tag.replace(' ', '_')}"
                enhanced_characters.append(enhanced_tag)
            result["characters"] = enhanced_characters
        
        # 应用画师符号强化：前缀@
        if result.get("artists"):
            enhanced_artists = []
            for tag in result["artists"]:
                # 清理画师标签格式
                clean_tag = tag
                if clean_tag.startswith("by "):
                    clean_tag = clean_tag[3:]
                elif "artist:" in clean_tag:
                    clean_tag = clean_tag.replace("artist:", "")
                
                # 将空格替换为下划线，并添加符号前缀
                enhanced_tag = f"{self.SYMBOL_PREFIX_ARTIST}{clean_tag.replace(' ', '_')}"
                enhanced_artists.append(enhanced_tag)
            result["artists"] = enhanced_artists
        
        return result

    def format_final_output(self, classified_tags: Dict[str, List[str]], enhanced_description: str, 
                           custom_characters: list = None, custom_artists: list = None, custom_copyrights: list = None) -> str:
        """格式化最终输出，使用固定的自然语言格式"""
        # 固定前缀
        prefix = "You are an assistant designed to generate anime images based on textual prompts. <Prompt Start> "
        
        # 收集所有元素
        # 1. 性别和量词
        gender_count = ""
        if classified_tags.get("special"):
            special_tags = classified_tags["special"]
            if special_tags:
                gender_count = special_tags[0]  # 取第一个作为主要描述
        
        # 2. 合并所有角色
        all_characters = []
        if classified_tags.get("characters"):
            all_characters.extend(classified_tags["characters"])
        if custom_characters:
            all_characters.extend(custom_characters)
        
        # 分离强化角色和普通角色
        enhanced_characters = []  # 强化格式的角色（保留下划线）
        normal_characters = []    # 普通角色（需要格式化）
        
        for char in all_characters:
            if char.startswith("#"):
                # 强化角色保持原始格式
                enhanced_characters.append(char)
            else:
                normal_characters.append(char)
        
        # 3. 合并所有版权
        all_copyrights = []
        if classified_tags.get("copyrights"):
            all_copyrights.extend(classified_tags["copyrights"])
        if custom_copyrights:
            all_copyrights.extend(custom_copyrights)
        
        # 4. 合并所有画师
        all_artists = []
        if classified_tags.get("artists"):
            all_artists.extend(classified_tags["artists"])
        if custom_artists:
            all_artists.extend(custom_artists)
        
        # 分离强化画师和普通画师
        enhanced_artists = []   # 强化格式的画师（保留下划线）
        normal_artists = []     # 普通画师（需要格式化）
        
        for artist in all_artists:
            if artist.startswith("@"):
                # 强化画师保持原始格式
                enhanced_artists.append(artist)
            else:
                # 清理普通画师名称
                clean_name = artist
                if clean_name.startswith("by "):
                    clean_name = clean_name[3:]
                elif "artist:" in clean_name:
                    clean_name = clean_name.replace("artist:", "")
                normal_artists.append(clean_name)
        
        # 5. 构建固定格式的自然语言描述
        description_parts = []
        
        # 对普通内容进行文本格式化（转换下划线等）
        formatted_normal_artists = [self.apply_text_formatting(artist) for artist in normal_artists]
        formatted_normal_characters = [self.apply_text_formatting(char) for char in normal_characters]
        formatted_copyrights = [self.apply_text_formatting(copyright) for copyright in all_copyrights]
        
        # 合并所有画师（先普通后强化）
        all_display_artists = formatted_normal_artists + enhanced_artists
        
        # 合并所有角色（先普通后强化）  
        all_display_characters = formatted_normal_characters + enhanced_characters
        
        # 画师风格部分
        if all_display_artists:
            if len(all_display_artists) == 1:
                style_part = f"The illustration should be in the distinct style of {all_display_artists[0]}"
            else:
                style_part = f"The illustration should be in the distinct style of {' and '.join(all_display_artists)}"
            description_parts.append(style_part)
        
        # 角色和版权部分
        if all_display_characters and formatted_copyrights:
            if len(all_display_characters) == 1:
                char_part = f"depicting {gender_count} named {all_display_characters[0]}" if gender_count else f"depicting {all_display_characters[0]}"
            else:
                char_part = f"depicting {gender_count} named {' and '.join(all_display_characters)}" if gender_count else f"depicting {' and '.join(all_display_characters)}"
            
            if len(formatted_copyrights) == 1:
                char_part += f" from {formatted_copyrights[0]}"
            else:
                char_part += f" from {' and '.join(formatted_copyrights)}"
            
            description_parts.append(char_part)
        elif all_display_characters:
            if len(all_display_characters) == 1:
                char_part = f"depicting {gender_count} named {all_display_characters[0]}" if gender_count else f"depicting {all_display_characters[0]}"
            else:
                char_part = f"depicting {gender_count} named {' and '.join(all_display_characters)}" if gender_count else f"depicting {' and '.join(all_display_characters)}"
            description_parts.append(char_part)
        elif formatted_copyrights:
            if len(formatted_copyrights) == 1:
                copy_part = f"depicting {gender_count} from {formatted_copyrights[0]}" if gender_count else f"from {formatted_copyrights[0]}"
            else:
                copy_part = f"depicting {gender_count} from {' and '.join(formatted_copyrights)}" if gender_count else f"from {' and '.join(formatted_copyrights)}"
            description_parts.append(copy_part)
        elif gender_count:
            description_parts.append(f"depicting {gender_count}")
        
        # 自然语言详细描述
        detail_description = ""
        if enhanced_description:
            detail_description = enhanced_description
        elif classified_tags.get("general"):
            # 将通用标签转换为简洁的描述
            general_tags = classified_tags["general"]
            if general_tags:
                # 简化处理，只提取关键特征
                key_features = []
                for tag in general_tags[:5]:  # 只取前5个重要特征
                    clean_tag = tag.replace("_", " ")
                    key_features.append(clean_tag)
                
                if key_features:
                    detail_description = f"with {', '.join(key_features)}"
        
        if detail_description:
            description_parts.append(detail_description)
        
        # 添加质量标签
        if classified_tags.get("quality"):
            quality_tags = classified_tags["quality"]
            positive_quality = [tag for tag in quality_tags if tag not in ["worst quality", "low quality", "bad quality", "jpeg artifacts", "blurry"]]
            if positive_quality:
                description_parts.extend(positive_quality)
        
        # 组合最终描述
        if description_parts:
            final_content = ". ".join(description_parts)
            # 确保句子以句号结尾
            if not final_content.endswith('.') and not any(final_content.endswith(q) for q in ["masterpiece", "best quality", "high quality"]):
                final_content += "."
        else:
            final_content = "An anime-style illustration."
        
        return prefix + final_content

    def process_prompt(self, danbooru_tags: str, drawing_theme: str,
                      api_url: str, api_key: str, model_name: str,
                      classification_mode: str = "local_knowledge", 
                      custom_characters: str = "", custom_artists: str = "", custom_copyrights: str = "", 
                      enable_symbol_enhancement: bool = True,
                      proxy_http: str = "", proxy_https: str = "") -> Tuple[str, str, str, Dict, str]:
        """主处理函数"""
        
        log_entries = []
        log_entries.append("=== 高级提示词处理开始 ===")
        log_entries.append(f"输入标签: {danbooru_tags[:self.MAX_LOG_LENGTH]}{'...' if len(danbooru_tags) > self.MAX_LOG_LENGTH else ''}")
        log_entries.append(f"绘图主题: {drawing_theme[:self.MAX_LOG_LENGTH]}{'...' if len(drawing_theme) > self.MAX_LOG_LENGTH else ''}")
        
        # 记录代理设置
        if proxy_http or proxy_https:
            log_entries.append(f"🌐 手动代理设置 - HTTP: {proxy_http or '无'}, HTTPS: {proxy_https or '无'}")
        else:
            log_entries.append("🌐 将自动检测系统代理设置")
        
        # 步骤1: 数字替换
        processed_tags = self.replace_numbers_with_english(danbooru_tags)
        if processed_tags != danbooru_tags:
            log_entries.append("数字替换完成")
        
        # 步骤2: 解析自定义标签（直接添加到输出的标签）
        custom_chars_list = self.parse_custom_tags(custom_characters)
        custom_artists_list = self.parse_custom_tags(custom_artists)
        custom_copyrights_list = self.parse_custom_tags(custom_copyrights)
        log_entries.append(f"自定义标签解析完成 - 角色:{len(custom_chars_list)}, 画师:{len(custom_artists_list)}, 版权:{len(custom_copyrights_list)}")
        
        # 保留空集合用于分类时的查找
        custom_chars_set = set(custom_chars_list) if custom_chars_list else set()
        custom_artists_set = set(custom_artists_list) if custom_artists_list else set()
        custom_copyrights_set = set(custom_copyrights_list) if custom_copyrights_list else set()
        
        # 步骤3: 分类标签（选择分类模式）
        classified_tags = {}
        if processed_tags.strip():
            if classification_mode == "llm_classification" and api_key:
                classified_tags = self.classify_tags_with_llm(processed_tags, api_url, api_key, model_name, proxy_http, proxy_https)
                log_entries.append(f"LLM标签分类完成 - 总计:{sum(len(tags) for tags in classified_tags.values())}个标签")
            else:
                # 使用配置的知识库路径
                knowledge_base = self.load_knowledge_base_from_folder(self.KNOWLEDGE_BASE_PATH)
                if knowledge_base:
                    total_tags = sum(len(tags) for tags in knowledge_base.values() if tags)
                    log_entries.append(f"加载Tag knowledge成功 - {len(knowledge_base)} 个类别，{total_tags} 个标签")
                else:
                    log_entries.append("Tag knowledge为空，使用内置知识库进行分类")
                
                classified_tags = self.classify_tags_with_knowledge_base(
                    processed_tags, knowledge_base, custom_chars_set, custom_artists_set, custom_copyrights_set
                )
                log_entries.append(f"本地知识库分类完成 - 总计:{sum(len(tags) for tags in classified_tags.values())}个标签")
        else:
            # 初始化空分类
            classified_tags = {category: [] for category in ["special", "characters", "copyrights", "artists", "general", "quality", "meta", "rating"]}
            log_entries.append("无标签输入，跳过分类")
        
        # 步骤4: LLM增强
        enhanced_description = ""
        if api_key:
            log_entries.append(f"使用模型: {model_name}")
            enhanced_description = self.enhance_with_llm(processed_tags, drawing_theme, api_url, api_key, model_name, proxy_http, proxy_https)
            if enhanced_description and not enhanced_description.startswith("API调用失败"):
                log_entries.append("LLM增强完成")
            else:
                log_entries.append(f"LLM增强失败: {enhanced_description}")
                enhanced_description = ""  # 清空失败的结果
        else:
            log_entries.append("LLM增强跳过 - 无API密钥")
        
        # 步骤5: 应用符号强化（包括自定义标签）
        enhanced_tags = self.apply_symbol_enhancement(classified_tags, enable_symbol_enhancement)
        
        # 对自定义标签也应用符号强化
        if enable_symbol_enhancement:
            if custom_chars_list:
                custom_chars_list = [f"{self.SYMBOL_PREFIX_CHARACTER}{char.replace(' ', '_')}" for char in custom_chars_list]
            if custom_artists_list:
                custom_artists_list = [f"{self.SYMBOL_PREFIX_ARTIST}{artist.replace(' ', '_')}" for artist in custom_artists_list]
            log_entries.append("符号强化完成 - @画师强化, #角色强化（包括自定义标签）")
        else:
            log_entries.append("跳过符号强化")
        
        # 步骤6: 文本格式化
        formatted_enhanced = self.apply_text_formatting(enhanced_description)
        
        log_entries.append("文本格式化将在最终输出时处理")
        
        # 步骤7: 生成最终输出，合并自定义标签
        final_prompt = self.format_final_output(enhanced_tags, formatted_enhanced, 
                                               custom_chars_list, custom_artists_list, custom_copyrights_list)
        
        # 生成格式化提示词（去除前缀的纯内容版本）
        formatted_prompt = final_prompt.replace("You are an assistant designed to generate anime images based on textual prompts. <Prompt Start> ", "")
        
        log_entries.append("最终输出生成完成")
        log_entries.append("=== 处理完成 ===")
        
        processing_log = "\n".join(log_entries)
        
        return (final_prompt, formatted_enhanced, formatted_prompt, enhanced_tags, processing_log)


# 节点映射
NODE_CLASS_MAPPINGS = {
    "AdvancedPromptProcessor": AdvancedPromptProcessor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedPromptProcessor": "高级提示词处理器",
}