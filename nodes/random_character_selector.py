# -*- coding: utf-8 -*-
"""
随机角色选择器
从角色Excel文件中随机抽取角色名称和外貌描述
"""
import random
import os
import pandas as pd
import sys
import subprocess
from typing import List, Tuple, Optional, Dict

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


class RandomCharacterSelector:
    """
    随机角色选择器 - 从角色Excel文件中随机选择角色
    支持角色触发词和外貌描述的组合输出
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character_file_path": ("STRING", {
                    "default": "random角色.xlsx",
                    "placeholder": "角色Excel文件路径（会自动在Random prompt文件夹中查找）"
                }),
                "character_count": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "number",
                    "tooltip": "要随机选择的角色数量"
                }),
            },
            "optional": {
                "output_mode": (["trigger_only", "description_only", "combined", "separated"], {
                    "default": "combined"
                }),
                "format_style": (["original", "parentheses", "clean"], {
                    "default": "original"
                }),
                "random_seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 0xffffffffffffffff,
                    "tooltip": "随机种子，-1为随机"
                }),
                "avoid_duplicates": ("BOOLEAN", {"default": True}),
                "weight_characters": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "是否给角色添加权重括号"
                }),
                "character_weight": ("FLOAT", {
                    "default": 1.1,
                    "min": 0.5,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "角色权重值（仅在weight_characters启用时有效）"
                }),
                "series_filter": ("STRING", {
                    "default": "",
                    "placeholder": "作品系列筛选，如：touhou, fate"
                }),
                "auto_random_seed": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "自动生成9位数随机种子"
                }),
            },
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("selected_characters", "character_descriptions", "combined_output", "character_info", "processing_log")
    FUNCTION = "select_random_characters"
    CATEGORY = "AI/Random Character"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """强制节点每次都重新执行，避免ComfyUI缓存"""
        import time
        return time.time()
    
    def __init__(self):
        self.character_data = None
        self.last_file_path = None
        
    def resolve_character_path(self, file_path: str) -> str:
        """解析角色文件路径，支持相对路径和绝对路径"""
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # 尝试相对于当前脚本目录的路径
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        possible_paths = [
            file_path,
            os.path.join(script_dir, "Random prompt", "random角色.xlsx"),
            os.path.join(script_dir, "Random prompt", os.path.basename(file_path)),
            os.path.join(script_dir, file_path),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return file_path
    
    def load_character_data(self, file_path: str) -> bool:
        """加载角色数据"""
        try:
            final_path = self.resolve_character_path(file_path)
            
            if not os.path.exists(final_path):
                print(f"角色文件不存在: {final_path}")
                return False
            
            # 检查是否需要重新加载
            if self.last_file_path == final_path and self.character_data is not None:
                return True
            
            # 加载数据
            self.character_data = safe_read_excel(final_path)
            self.last_file_path = final_path
            
            print(f"成功加载角色数据，共 {len(self.character_data)} 个角色")
            return True
            
        except Exception as e:
            print(f"加载角色文件失败: {e}")
            return False
    
    def get_character_columns(self) -> Tuple[Optional[str], Optional[str]]:
        """自动检测角色相关列名"""
        if self.character_data is None:
            return None, None
        
        columns = self.character_data.columns.tolist()
        
        # 检测触发词列
        trigger_column = None
        trigger_names = ['角色触发词', 'character', 'Character', 'name', 'Name', '角色名', '触发词']
        for name in trigger_names:
            if name in columns:
                trigger_column = name
                break
        
        # 检测描述列
        description_column = None
        desc_names = ['角色核心外貌描写提示词', 'description', 'Description', '外貌描述', '描述', '外貌', '特征']
        for name in desc_names:
            if name in columns:
                description_column = name
                break
        
        # 如果没有找到，使用前两列
        if not trigger_column and columns:
            trigger_column = columns[0]
        if not description_column and len(columns) > 1:
            description_column = columns[1]
        
        return trigger_column, description_column
    
    def filter_by_series(self, data: pd.DataFrame, series_filter: str) -> pd.DataFrame:
        """根据作品系列筛选角色"""
        if not series_filter.strip():
            return data
        
        trigger_column, _ = self.get_character_columns()
        if not trigger_column:
            return data
        
        # 支持多个系列筛选，用逗号分隔
        series_list = [s.strip().lower() for s in series_filter.split(',') if s.strip()]
        
        if not series_list:
            return data
        
        # 筛选包含任一指定系列的角色
        mask = data[trigger_column].str.lower().str.contains('|'.join(series_list), na=False)
        filtered_data = data[mask]
        
        print(f"系列筛选 '{series_filter}' 后剩余 {len(filtered_data)} 个角色")
        return filtered_data
    
    def format_character_content(self, content: str, style: str, weight: float = 1.1, use_weight: bool = False) -> str:
        """格式化角色内容"""
        if pd.isna(content):
            return ""
        
        formatted_content = str(content).strip()
        
        if not formatted_content:
            return ""
        
        # 根据格式风格处理
        if style == "parentheses":
            # 添加括号格式
            formatted_content = f"({formatted_content})"
        elif style == "clean":
            # 清理格式，移除特殊字符但保留基本结构
            formatted_content = formatted_content.replace("\\", "").replace("(", "").replace(")", "")
            # 如果清理后为空，使用原始内容
            if not formatted_content.strip():
                formatted_content = str(content).strip()
        # original 保持原样
        
        # 如果启用权重，添加权重括号
        if use_weight and weight != 1.0:
            formatted_content = f"({formatted_content}:{weight:.1f})"
        
        return formatted_content
    
    def select_characters(self, count: int, series_filter: str = "", avoid_duplicates: bool = True) -> List[Dict]:
        """选择指定数量的角色"""
        if self.character_data is None:
            return []
        
        # 应用系列筛选
        filtered_data = self.filter_by_series(self.character_data, series_filter)
        
        if len(filtered_data) == 0:
            print("筛选后没有可用的角色数据")
            return []
        
        # 选择角色
        if avoid_duplicates and count <= len(filtered_data):
            selected_indices = random.sample(range(len(filtered_data)), count)
            selected_characters = [filtered_data.iloc[i].to_dict() for i in selected_indices]
        else:
            # 允许重复或数量超过可用角色数
            selected_characters = [filtered_data.sample(n=1).iloc[0].to_dict() for _ in range(count)]
        
        return selected_characters
    
    def generate_output(self, selected_characters: List[Dict], output_mode: str, format_style: str, 
                       character_weight: float, weight_characters: bool) -> Tuple[str, str, str]:
        """生成不同格式的输出"""
        trigger_column, description_column = self.get_character_columns()
        
        if not trigger_column:
            return "", "", ""
        
        triggers = []
        descriptions = []
        combined_parts = []
        
        for char_data in selected_characters:
            # 获取触发词
            trigger = char_data.get(trigger_column, "")
            if trigger:
                formatted_trigger = self.format_character_content(trigger, format_style, character_weight, weight_characters)
                triggers.append(formatted_trigger)
            
            # 获取描述
            description = ""
            if description_column and description_column in char_data:
                description = char_data.get(description_column, "")
                if description:
                    formatted_desc = self.format_character_content(description, format_style, character_weight, weight_characters)
                    descriptions.append(formatted_desc)
            
            # 组合输出
            if output_mode == "combined":
                if trigger and description:
                    combined_parts.append(f"{formatted_trigger}, {formatted_desc}")
                elif trigger:
                    combined_parts.append(formatted_trigger)
                elif description:
                    combined_parts.append(formatted_desc)
        
        # 生成最终输出
        selected_triggers = ", ".join(triggers)
        selected_descriptions = ", ".join(descriptions)
        
        if output_mode == "trigger_only":
            combined_output = selected_triggers
        elif output_mode == "description_only":
            combined_output = selected_descriptions
        elif output_mode == "combined":
            combined_output = ", ".join(combined_parts)
        elif output_mode == "separated":
            # 分离模式：触发词和描述用分隔符隔开
            if selected_triggers and selected_descriptions:
                combined_output = f"{selected_triggers} | {selected_descriptions}"
            else:
                combined_output = selected_triggers or selected_descriptions
        else:
            combined_output = selected_triggers
        
        return selected_triggers, selected_descriptions, combined_output
    
    def get_file_info(self) -> str:
        """获取文件信息"""
        if self.character_data is None:
            return "未加载角色数据"
        
        trigger_column, description_column = self.get_character_columns()
        
        info_parts = []
        info_parts.append(f"总角色数: {len(self.character_data)}")
        
        if trigger_column:
            info_parts.append(f"触发词列: {trigger_column}")
        if description_column:
            info_parts.append(f"描述列: {description_column}")
        
        # 显示一些示例角色
        if trigger_column and len(self.character_data) > 0:
            sample_characters = self.character_data[trigger_column].head(5).tolist()
            info_parts.append(f"示例角色: {', '.join(str(char) for char in sample_characters)}")
        
        return "\n".join(info_parts)
    
    def select_random_characters(self, character_file_path: str, character_count: int,
                               output_mode: str = "combined", format_style: str = "original",
                               random_seed: int = -1, avoid_duplicates: bool = True,
                               weight_characters: bool = False, character_weight: float = 1.1,
                               series_filter: str = "", auto_random_seed: bool = True) -> Tuple[str, str, str, str, str]:
        """主要的随机角色选择函数"""
        
        log_entries = []
        log_entries.append("=== 随机角色选择开始 ===")
        
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
        
        # 加载角色数据
        if not self.load_character_data(character_file_path):
            error_msg = f"无法加载角色文件: {character_file_path}"
            log_entries.append(error_msg)
            return error_msg, "", "", "", "\n".join(log_entries)
        
        log_entries.append(f"成功加载角色文件")
        
        # 选择角色
        selected_characters = self.select_characters(character_count, series_filter, avoid_duplicates)
        
        if not selected_characters:
            error_msg = "没有可用的角色数据"
            log_entries.append(error_msg)
            return error_msg, "", "", "", "\n".join(log_entries)
        
        log_entries.append(f"成功选择了 {len(selected_characters)} 个角色")
        
        # 生成输出
        selected_triggers, selected_descriptions, combined_output = self.generate_output(
            selected_characters, output_mode, format_style, character_weight, weight_characters
        )
        
        # 生成详细信息
        character_info_parts = []
        character_info_parts.append("=== 选择的角色详细信息 ===")
        
        trigger_column, description_column = self.get_character_columns()
        
        for i, char_data in enumerate(selected_characters, 1):
            character_info_parts.append(f"第{i}个角色:")
            if trigger_column:
                trigger = char_data.get(trigger_column, "")
                character_info_parts.append(f"  触发词: {trigger}")
            if description_column:
                description = char_data.get(description_column, "")
                if description:
                    character_info_parts.append(f"  外貌描述: {description[:100]}{'...' if len(str(description)) > 100 else ''}")
        
        character_info_parts.append(f"\n输出模式: {output_mode}")
        character_info_parts.append(f"格式化风格: {format_style}")
        if weight_characters:
            character_info_parts.append(f"权重值: {character_weight}")
        if series_filter:
            character_info_parts.append(f"系列筛选: {series_filter}")
        
        # 添加文件信息
        file_info = self.get_file_info()
        if file_info:
            character_info_parts.append(f"\n=== 文件信息 ===")
            character_info_parts.append(file_info)
        
        character_info = "\n".join(character_info_parts)
        
        log_entries.append("角色选择和格式化完成")
        log_entries.append("=== 随机角色选择完成 ===")
        
        processing_log = "\n".join(log_entries)
        
        return selected_triggers, selected_descriptions, combined_output, character_info, processing_log


# 节点映射
NODE_CLASS_MAPPINGS = {
    "RandomCharacterSelector": RandomCharacterSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomCharacterSelector": "随机角色选择器",
}