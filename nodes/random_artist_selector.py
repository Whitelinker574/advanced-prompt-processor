# -*- coding: utf-8 -*-
"""
随机画师选择器
从画师Excel文件中随机抽取画师名称
"""
import random
import os
import pandas as pd
import sys
import subprocess
from typing import List, Tuple, Optional

def ensure_openpyxl():
    """确保openpyxl可用，如果没有则尝试安装"""
    try:
        import openpyxl
        return True
    except ImportError:
        print("⚠️ openpyxl未安装，正在尝试安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl>=3.0.0", "--quiet"])
            print("✅ openpyxl安装成功")
            # 重新导入以验证安装
            import openpyxl
            return True
        except Exception as e:
            print(f"❌ openpyxl安装失败: {e}")
            print("请手动安装: pip install openpyxl")
            return False

def safe_read_excel(file_path, **kwargs):
    """安全的Excel读取函数，确保openpyxl可用"""
    if not ensure_openpyxl():
        raise ImportError("无法安装openpyxl，Excel读取功能不可用")
    return pd.read_excel(file_path, **kwargs)


class RandomArtistSelector:
    """
    随机画师选择器 - 从画师Excel文件中随机选择画师
    支持从多个sheet中选择，提供多种格式化选项
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "artist_file_path": ("STRING", {
                    "default": "random画师.xlsx",
                    "placeholder": "画师Excel文件路径（会自动在Random prompt文件夹中查找）"
                }),
                "artist_count": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "number",
                    "tooltip": "要随机选择的画师数量"
                }),
            },
            "optional": {
                "sheet_name": ("STRING", {
                    "default": "Sheet1",
                    "placeholder": "Excel工作表名称，留空使用第一个sheet"
                }),
                "format_style": (["original", "parentheses", "by_prefix", "clean"], {
                    "default": "parentheses"
                }),
                "random_seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 0xffffffffffffffff,
                    "tooltip": "随机种子，-1为随机"
                }),
                "avoid_duplicates": ("BOOLEAN", {"default": True}),
                "weight_artists": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "是否给画师添加权重括号"
                }),
                "artist_weight": ("FLOAT", {
                    "default": 1.1,
                    "min": 0.5,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "画师权重值（仅在weight_artists启用时有效）"
                }),
                "auto_random_seed": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "自动生成9位数随机种子"
                }),
            },
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("selected_artists", "formatted_artists", "artist_info", "processing_log")
    FUNCTION = "select_random_artists"
    CATEGORY = "AI/Random Artist"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """强制节点每次都重新执行，避免ComfyUI缓存"""
        import time
        return time.time()
    
    def __init__(self):
        self.artist_data = None
        self.last_file_path = None
        self.available_sheets = []
        
    def resolve_artist_path(self, file_path: str) -> str:
        """解析画师文件路径，支持相对路径和绝对路径"""
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # 尝试相对于当前脚本目录的路径
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        possible_paths = [
            file_path,
            os.path.join(script_dir, "Random prompt", "random画师.xlsx"),
            os.path.join(script_dir, "Random prompt", os.path.basename(file_path)),
            os.path.join(script_dir, file_path),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return file_path
    
    def load_artist_data(self, file_path: str, sheet_name: str = "") -> bool:
        """加载画师数据"""
        try:
            final_path = self.resolve_artist_path(file_path)
            
            if not os.path.exists(final_path):
                print(f"画师文件不存在: {final_path}")
                return False
            
            # 检查是否需要重新加载
            if self.last_file_path == final_path and self.artist_data is not None:
                return True
            
            # 获取所有sheet信息
            xl = pd.ExcelFile(final_path)
            self.available_sheets = xl.sheet_names
            
            # 确定要使用的sheet
            target_sheet = sheet_name if sheet_name else xl.sheet_names[0]
            if target_sheet not in xl.sheet_names:
                print(f"Sheet '{target_sheet}' 不存在，使用第一个sheet: {xl.sheet_names[0]}")
                target_sheet = xl.sheet_names[0]
            
            # 加载数据
            self.artist_data = safe_read_excel(final_path, sheet_name=target_sheet)
            self.last_file_path = final_path
            
            print(f"成功加载画师数据，共 {len(self.artist_data)} 个画师，使用sheet: {target_sheet}")
            return True
            
        except Exception as e:
            print(f"加载画师文件失败: {e}")
            return False
    
    def get_artist_column(self) -> Optional[str]:
        """自动检测画师列名"""
        if self.artist_data is None:
            return None
        
        columns = self.artist_data.columns.tolist()
        
        # 优先级顺序检查列名
        priority_names = ['画师', 'artist', 'Artist', 'kedama milk', 'name', 'Name']
        
        for name in priority_names:
            if name in columns:
                return name
        
        # 如果没有匹配的，使用第一列
        return columns[0] if columns else None
    
    def format_artist_name(self, artist_name: str, style: str, weight: float = 1.1, use_weight: bool = False) -> str:
        """格式化画师名称"""
        if pd.isna(artist_name):
            return ""
        
        name = str(artist_name).strip()
        
        if not name:
            return ""
        
        # 根据格式风格处理
        if style == "original":
            formatted = name
        elif style == "parentheses":
            # 添加括号格式：(artist_name)
            formatted = f"({name})"
        elif style == "by_prefix":
            # 添加"by"前缀：by artist_name
            formatted = f"by {name}"
        elif style == "clean":
            # 清理格式，移除特殊字符但保留基本结构
            formatted = name.replace("\\", "").replace("(", "").replace(")", "")
            # 如果清理后为空，使用原始名称
            if not formatted.strip():
                formatted = name
        else:
            formatted = name
        
        # 如果启用权重，添加权重括号
        if use_weight and weight != 1.0:
            formatted = f"({formatted}:{weight:.1f})"
        
        return formatted
    
    def select_artists(self, count: int, avoid_duplicates: bool = True) -> List[str]:
        """选择指定数量的画师"""
        if self.artist_data is None:
            return []
        
        artist_column = self.get_artist_column()
        if not artist_column:
            return []
        
        # 获取所有画师名称并去除空值
        all_artists = self.artist_data[artist_column].dropna().astype(str).tolist()
        all_artists = [name.strip() for name in all_artists if name.strip()]
        
        if not all_artists:
            return []
        
        # 选择画师
        if avoid_duplicates and count <= len(all_artists):
            selected = random.sample(all_artists, count)
        else:
            # 允许重复或数量超过可用画师数
            selected = [random.choice(all_artists) for _ in range(count)]
        
        return selected
    
    def get_sheet_info(self) -> str:
        """获取sheet信息"""
        if not self.available_sheets:
            return "未加载文件信息"
        
        info = [f"可用的sheet: {', '.join(self.available_sheets)}"]
        
        if self.artist_data is not None:
            artist_column = self.get_artist_column()
            if artist_column:
                info.append(f"使用列: {artist_column}")
                info.append(f"总画师数: {len(self.artist_data)}")
                
                # 显示一些示例画师
                sample_artists = self.artist_data[artist_column].dropna().head(5).tolist()
                if sample_artists:
                    info.append(f"示例画师: {', '.join(str(name) for name in sample_artists)}")
        
        return "\n".join(info)
    
    def select_random_artists(self, artist_file_path: str, artist_count: int, 
                            sheet_name: str = "", format_style: str = "parentheses",
                            random_seed: int = -1, avoid_duplicates: bool = True,
                            weight_artists: bool = False, artist_weight: float = 1.1,
                            auto_random_seed: bool = True) -> Tuple[str, str, str, str]:
        """主要的随机画师选择函数"""
        
        log_entries = []
        log_entries.append("=== 随机画师选择开始 ===")
        
        # 设置随机种子
        if auto_random_seed:
            # 生成9位数随机种子 (100000000 - 999999999)
            new_seed = random.randint(100000000, 999999999)
            random.seed(new_seed)
            log_entries.append(f"🎲 自动生成9位数随机种子: {new_seed}")
        elif random_seed != -1:
            random.seed(random_seed)
            log_entries.append(f"使用指定随机种子: {random_seed}")
        else:
            log_entries.append("使用系统默认随机种子")
        
        # 加载画师数据
        if not self.load_artist_data(artist_file_path, sheet_name):
            error_msg = f"无法加载画师文件: {artist_file_path}"
            log_entries.append(error_msg)
            return error_msg, "", "", "\n".join(log_entries)
        
        log_entries.append(f"成功加载画师文件")
        
        # 选择画师
        selected_artists = self.select_artists(artist_count, avoid_duplicates)
        
        if not selected_artists:
            error_msg = "没有可用的画师数据"
            log_entries.append(error_msg)
            return error_msg, "", "", "\n".join(log_entries)
        
        log_entries.append(f"成功选择了 {len(selected_artists)} 个画师")
        
        # 格式化画师名称
        formatted_artists = []
        for artist in selected_artists:
            formatted = self.format_artist_name(artist, format_style, artist_weight, weight_artists)
            if formatted:
                formatted_artists.append(formatted)
        
        # 生成输出
        selected_artists_text = ", ".join(selected_artists)
        formatted_artists_text = ", ".join(formatted_artists)
        
        # 生成详细信息
        artist_info_parts = []
        artist_info_parts.append("=== 选择的画师详细信息 ===")
        for i, (original, formatted) in enumerate(zip(selected_artists, formatted_artists), 1):
            artist_info_parts.append(f"第{i}个画师:")
            artist_info_parts.append(f"  原始名称: {original}")
            artist_info_parts.append(f"  格式化后: {formatted}")
        
        artist_info_parts.append(f"\n格式化风格: {format_style}")
        if weight_artists:
            artist_info_parts.append(f"权重值: {artist_weight}")
        
        # 添加文件信息
        sheet_info = self.get_sheet_info()
        if sheet_info:
            artist_info_parts.append(f"\n=== 文件信息 ===")
            artist_info_parts.append(sheet_info)
        
        artist_info = "\n".join(artist_info_parts)
        
        log_entries.append("画师选择和格式化完成")
        log_entries.append("=== 随机画师选择完成 ===")
        
        processing_log = "\n".join(log_entries)
        
        return selected_artists_text, formatted_artists_text, artist_info, processing_log


# 节点映射
NODE_CLASS_MAPPINGS = {
    "RandomArtistSelector": RandomArtistSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomArtistSelector": "随机画师选择器",
}