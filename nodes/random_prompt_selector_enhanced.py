# -*- coding: utf-8 -*-
"""
增强的随机提示词选择器
从指定的Excel文件中随机抽取提示词内容，支持动态下拉菜单筛选
"""
import random
import os
import pandas as pd
import sys
import subprocess
from typing import Dict, List, Any, Tuple, Optional

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


class RandomPromptSelectorEnhanced:
    """
    增强的随机提示词选择器 - 支持动态下拉菜单筛选
    """
    
    # 类变量，用于缓存选项
    _cached_categories = ["All"]
    _cached_subcategories = ["All"]
    _last_excel_path = None
    
    @classmethod
    def _load_excel_options(cls, file_path=""):
        """加载Excel文件并提取类别和子类别选项"""
        try:
            # 解析Excel文件路径
            final_path = cls._resolve_excel_path(file_path or "所长个人法典结构化fix.xlsx")
            
            # 如果路径没变且已缓存，直接返回
            if cls._last_excel_path == final_path and len(cls._cached_categories) > 1:
                return
                
            if not os.path.exists(final_path):
                print(f"Excel文件不存在: {final_path}")
                return
                
            # 读取Excel文件
            data = safe_read_excel(final_path)
            cls._last_excel_path = final_path
            
            # 提取类别选项
            if '类别' in data.columns:
                categories = data['类别'].dropna().unique().tolist()
                categories.sort()
                cls._cached_categories = ["All"] + categories
            
            # 提取子类别选项
            if '子类' in data.columns:
                subcategories = data['子类'].dropna().unique().tolist()
                subcategories.sort()
                cls._cached_subcategories = ["All"] + subcategories
                
            print(f"✅ 成功加载选项: {len(cls._cached_categories)-1}个类别, {len(cls._cached_subcategories)-1}个子类")
            
        except Exception as e:
            print(f"加载Excel选项失败: {e}")
    
    @classmethod
    def _resolve_excel_path(cls, file_path: str) -> str:
        """解析Excel文件路径，支持相对路径和绝对路径"""
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # 尝试相对于当前脚本目录的路径
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 检查几个可能的路径
        possible_paths = [
            file_path,
            os.path.join(script_dir, "Random prompt", "所长个人法典结构化fix.xlsx"),
            os.path.join(script_dir, "Random prompt", os.path.basename(file_path)),
            os.path.join(script_dir, file_path),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return file_path

    @classmethod
    def INPUT_TYPES(cls):
        # 预加载选项
        cls._load_excel_options()
        
        return {
            "required": {
                "excel_file_path": ("STRING", {
                    "default": "所长个人法典结构化fix.xlsx",
                    "placeholder": "Excel文件路径（会自动在Random prompt文件夹中查找）"
                }),
                "selection_mode": (["random", "by_category", "by_subcategory", "mixed"], {
                    "default": "random"
                }),
                "prompt_count": ("INT", {
                    "default": 3,
                    "min": 1,
                    "max": 20,
                    "step": 1,
                    "display": "number",
                    "tooltip": "要随机选择的提示词数量"
                }),
                "category_filter": (cls._cached_categories, {
                    "default": "All",
                    "tooltip": "选择类别进行筛选"
                }),
                "subcategory_filter": (cls._cached_subcategories, {
                    "default": "All", 
                    "tooltip": "选择子类进行筛选"
                }),
            },
            "optional": {
                "combine_with_existing": ("BOOLEAN", {"default": True}),
                "existing_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "现有的提示词，新选择的内容将与此合并"
                }),
                "random_seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 0xffffffffffffffff,
                    "tooltip": "随机种子，-1为随机"
                }),
                "refresh_options": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "强制刷新类别选项（当Excel文件更新后使用）"
                }),
                "auto_random_seed": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "自动生成9位数随机种子"
                }),
            },
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("combined_prompt", "selected_prompts", "selected_info", "category_stats", "processing_log")
    FUNCTION = "select_random_prompts"
    CATEGORY = "Advanced Prompt Processor"
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """强制节点每次都重新执行，避免ComfyUI缓存"""
        import time
        return time.time()
    
    def __init__(self):
        self.excel_data = None
        self.last_file_path = None
        
    def load_excel_data(self, file_path: str) -> bool:
        """加载Excel数据"""
        try:
            # 智能路径处理
            final_path = self._resolve_excel_path(file_path)
            
            if not os.path.exists(final_path):
                print(f"Excel文件不存在: {final_path}")
                return False
                
            # 如果是同一个文件且已经加载过，就不重新加载
            if self.last_file_path == final_path and self.excel_data is not None:
                return True
                
            self.excel_data = safe_read_excel(final_path)
            self.last_file_path = final_path
            return True
        except Exception as e:
            print(f"加载Excel文件失败: {e}")
            return False
    
    def get_category_stats(self) -> str:
        """获取类别统计信息"""
        if self.excel_data is None:
            return "未加载数据"
            
        try:
            stats = []
            stats.append("=== 类别统计 ===")
            category_counts = self.excel_data['类别'].value_counts()
            for category, count in category_counts.head(10).items():
                stats.append(f"{category}: {count}条")
            
            stats.append("\n=== 子类统计（前20） ===")
            subcategory_counts = self.excel_data['子类'].value_counts()
            for subcategory, count in subcategory_counts.head(20).items():
                if pd.notna(subcategory):
                    stats.append(f"{subcategory}: {count}条")
                    
            return "\n".join(stats)
        except Exception as e:
            return f"统计信息生成失败: {e}"
    
    def filter_data(self, category_filter: str, subcategory_filter: str) -> pd.DataFrame:
        """根据筛选条件过滤数据"""
        filtered_data = self.excel_data.copy()
        
        # 处理类别筛选
        if category_filter and category_filter != "All":
            filtered_data = filtered_data[filtered_data['类别'] == category_filter]
        
        # 处理子类筛选
        if subcategory_filter and subcategory_filter != "All":
            filtered_data = filtered_data[filtered_data['子类'] == subcategory_filter]
            
        return filtered_data
    
    def select_by_mode(self, data: pd.DataFrame, mode: str, count: int) -> List[Dict]:
        """根据选择模式从数据中选择提示词"""
        if data.empty:
            return []
            
        selected = []
        
        try:
            if mode == "random":
                # 完全随机选择
                sample_data = data.sample(n=min(count, len(data)))
                
            elif mode == "by_category":
                # 按类别分组随机选择
                categories = data['类别'].unique()
                per_category = max(1, count // len(categories))
                
                for category in categories:
                    category_data = data[data['类别'] == category]
                    category_sample = category_data.sample(n=min(per_category, len(category_data)))
                    selected.extend(category_sample.to_dict('records'))
                    
                # 如果选择数量不足，随机补充
                if len(selected) < count:
                    remaining = count - len(selected)
                    used_indices = [item.get('index', -1) for item in selected if 'index' in item]
                    available_data = data[~data.index.isin(used_indices)]
                    if not available_data.empty:
                        additional = available_data.sample(n=min(remaining, len(available_data)))
                        selected.extend(additional.to_dict('records'))
                        
                return selected[:count]
                
            elif mode == "by_subcategory":
                # 按子类分组随机选择
                subcategories = data['子类'].dropna().unique()
                if len(subcategories) == 0:
                    sample_data = data.sample(n=min(count, len(data)))
                else:
                    per_subcategory = max(1, count // len(subcategories))
                    
                    for subcategory in subcategories:
                        subcategory_data = data[data['子类'] == subcategory]
                        subcategory_sample = subcategory_data.sample(n=min(per_subcategory, len(subcategory_data)))
                        selected.extend(subcategory_sample.to_dict('records'))
                        
                    # 如果选择数量不足，随机补充
                    if len(selected) < count:
                        remaining = count - len(selected)
                        used_indices = [item.get('index', -1) for item in selected if 'index' in item]
                        available_data = data[~data.index.isin(used_indices)]
                        if not available_data.empty:
                            additional = available_data.sample(n=min(remaining, len(available_data)))
                            selected.extend(additional.to_dict('records'))
                            
                    return selected[:count]
                    
            elif mode == "mixed":
                # 混合模式：一半按类别，一半随机
                half_count = count // 2
                
                # 先按类别选择
                categories = data['类别'].unique()
                per_category = max(1, half_count // len(categories))
                
                for category in categories:
                    category_data = data[data['类别'] == category]
                    category_sample = category_data.sample(n=min(per_category, len(category_data)))
                    selected.extend(category_sample.to_dict('records'))
                
                # 再随机选择剩余的
                remaining_count = count - len(selected)
                if remaining_count > 0:
                    used_indices = [item.get('index', -1) for item in selected if 'index' in item]
                    available_data = data[~data.index.isin(used_indices)]
                    if not available_data.empty:
                        additional = available_data.sample(n=min(remaining_count, len(available_data)))
                        selected.extend(additional.to_dict('records'))
                        
                return selected[:count]
            
            # 默认情况（random模式）
            if 'sample_data' in locals():
                selected = sample_data.to_dict('records')
                
        except Exception as e:
            print(f"选择过程出错: {e}")
            # 出错时回退到简单随机选择
            sample_data = data.sample(n=min(count, len(data)))
            selected = sample_data.to_dict('records')
            
        return selected
    
    def select_random_prompts(self, excel_file_path, selection_mode, prompt_count, category_filter="All", subcategory_filter="All", 
                            combine_with_existing=True, existing_prompt="", random_seed=-1, refresh_options=False, auto_random_seed=True):
        """主要的选择函数"""
        
        # 刷新选项（如果需要）
        if refresh_options:
            self._load_excel_options(excel_file_path)
        
        processing_log = []
        processing_log.append(f"开始处理: 文件={excel_file_path}, 模式={selection_mode}, 数量={prompt_count}")
        
        # 设置随机种子
        if auto_random_seed:
            # 生成9位数随机种子 (100000000 - 999999999)
            new_seed = random.randint(100000000, 999999999)
            random.seed(new_seed)
            processing_log.append(f"🎲 自动生成9位数随机种子: {new_seed}")
        elif random_seed >= 0:
            random.seed(random_seed)
            processing_log.append(f"使用指定随机种子: {random_seed}")
        else:
            processing_log.append("使用系统默认随机种子")
        
        # 加载Excel数据
        if not self.load_excel_data(excel_file_path):
            error_msg = "无法加载Excel文件"
            return "", "", error_msg, "", error_msg
        
        processing_log.append(f"成功加载Excel文件，共{len(self.excel_data)}行数据")
        
        # 应用筛选条件
        filter_info = []
        if category_filter != "All":
            filter_info.append(f"类别={category_filter}")
        if subcategory_filter != "All":
            filter_info.append(f"子类={subcategory_filter}")
            
        if filter_info:
            processing_log.append(f"应用筛选条件: {', '.join(filter_info)}")
        
        filtered_data = self.filter_data(category_filter, subcategory_filter)
        processing_log.append(f"筛选后剩余{len(filtered_data)}行数据")
        
        if filtered_data.empty:
            error_msg = "筛选后没有可用数据"
            return "", "", error_msg, self.get_category_stats(), "\n".join(processing_log)
        
        # 选择提示词
        selected_items = self.select_by_mode(filtered_data, selection_mode, prompt_count)
        processing_log.append(f"成功选择{len(selected_items)}条提示词")
        
        if not selected_items:
            error_msg = "没有选择到任何提示词"
            return "", "", error_msg, self.get_category_stats(), "\n".join(processing_log)
        
        # 提取提示词内容
        selected_prompts = []
        selected_info_parts = []
        
        for i, item in enumerate(selected_items, 1):
            # 尝试从不同的列获取提示词内容
            content = ""
            for col in ['提示词', 'prompt', '内容', 'content', 'text']:
                if col in item and pd.notna(item[col]):
                    content = str(item[col]).strip()
                    break
            
            if content:
                selected_prompts.append(content)
                
                # 生成详细信息
                info_parts = [f"#{i}: {content[:50]}..."]
                if '类别' in item and pd.notna(item['类别']):
                    info_parts.append(f"类别: {item['类别']}")
                if '子类' in item and pd.notna(item['子类']):
                    info_parts.append(f"子类: {item['子类']}")
                    
                selected_info_parts.append(" | ".join(info_parts))
        
        # 组合结果
        selected_text = ", ".join(selected_prompts)
        
        if combine_with_existing and existing_prompt.strip():
            combined_prompt = f"{existing_prompt.strip()}, {selected_text}"
        else:
            combined_prompt = selected_text
        
        selected_info = "\n".join(selected_info_parts)
        category_stats = self.get_category_stats()
        final_log = "\n".join(processing_log)
        
        return combined_prompt, selected_text, selected_info, category_stats, final_log


# 节点映射
NODE_CLASS_MAPPINGS = {
    "RandomPromptSelectorEnhanced": RandomPromptSelectorEnhanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomPromptSelectorEnhanced": "Random Prompt Selector (Enhanced)",
}