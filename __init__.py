"""
Advanced Prompt Processor - ComfyUI 提示词处理扩展
作者: whitelinker
版本: 2.0.0

通用节点导入系统 - 支持所有平台和Python环境
"""

import sys
import os
import importlib
import importlib.util
from pathlib import Path

# 插件信息
__version__ = "2.0.0"
__author__ = "whitelinker"
__description__ = "Advanced Prompt Processor for ComfyUI - 智能提示词处理、随机元素选择和Gelbooru标签集成"

def auto_install_dependencies():
    """自动安装缺失的依赖"""
    required_deps = ['pandas', 'requests', 'numpy', 'urllib3', 'openpyxl']
    missing_deps = []
    
    for dep in required_deps:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"🔧 Advanced Prompt Processor: 自动安装缺失依赖 {missing_deps}")
        try:
            import subprocess
            for dep in missing_deps:
                subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "--quiet"])
            print("✅ 依赖安装完成")
        except Exception as e:
            print(f"⚠️ 自动安装失败: {e}")
            print(f"请手动安装: pip install {' '.join(missing_deps)}")

def universal_import_node(module_name, class_name):
    """通用节点导入函数 - 兼容所有环境"""
    current_dir = Path(__file__).parent
    
    # 导入策略优先级
    strategies = [
        # 策略1: 相对导入 (标准方式)
        lambda: importlib.import_module(f".nodes.{module_name}", package=__package__),
        
        # 策略2: 绝对导入 (兼容方式)  
        lambda: importlib.import_module(f"nodes.{module_name}"),
        
        # 策略3: 添加路径后导入
        lambda: (
            sys.path.insert(0, str(current_dir)) or 
            importlib.import_module(f"nodes.{module_name}")
        ),
        
        # 策略4: 直接文件导入 (万能方式)
        lambda: load_module_from_file(
            f"nodes_{module_name}", 
            current_dir / "nodes" / f"{module_name}.py"
        )
    ]
    
    for i, strategy in enumerate(strategies, 1):
        try:
            module = strategy()
            if hasattr(module, class_name):
                return getattr(module, class_name)
        except Exception:
            continue
    
    raise ImportError(f"无法导入 {class_name} from {module_name}")

def load_module_from_file(module_name, file_path):
    """从文件路径直接加载模块"""
    if not file_path.exists():
        raise FileNotFoundError(f"模块文件不存在: {file_path}")
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建模块规范: {module_name}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 自动依赖检查和安装
try:
    # 优先使用startup_check，回退到基础版本
    try:
        from .scripts.startup_check import startup_check
        startup_check()
    except ImportError:
        auto_install_dependencies()
except Exception as e:
    print(f"Advanced Prompt Processor 依赖检查警告: {e}")

# 节点配置
NODES_CONFIG = [
    ("advanced_prompt_processor", "AdvancedPromptProcessor", "高级提示词处理器"),
    ("random_prompt_selector_enhanced", "RandomPromptSelectorEnhanced", "增强随机提示词选择器"),
    ("random_artist_selector", "RandomArtistSelector", "随机画师选择器"),
    ("random_character_selector", "RandomCharacterSelector", "随机角色选择器"),
    ("gelbooru_accurate_extractor", "GelbooruAccurateExtractor", "Gelbooru准确标签提取器"),
    ("xml_prompt_generator", "XMLPromptGenerator", "XML提示词生成器")
]

# 初始化节点映射
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# 通用节点加载
loaded_count = 0
for module_name, class_name, display_name in NODES_CONFIG:
    try:
        node_class = universal_import_node(module_name, class_name)
        NODE_CLASS_MAPPINGS[class_name] = node_class
        NODE_DISPLAY_NAME_MAPPINGS[class_name] = display_name
        loaded_count += 1
        
    except Exception as e:
        print(f"⚠️ 节点加载失败: {display_name} - {e}")

# 加载结果
if loaded_count > 0:
    print(f"✅ Advanced Prompt Processor: 成功加载 {loaded_count}/{len(NODES_CONFIG)} 个节点")
else:
    print("❌ Advanced Prompt Processor: 所有节点加载失败")
    print("请检查插件安装是否完整")

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']