# 🚀 Advanced Prompt Processor 快速开始指南

## 📦 极简安装

### 🎯 一键安装（推荐）
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Wuqisheng123/advanced-prompt-processor.git
```

**就是这么简单！** 🎉

- ✅ **自动依赖检查**: 启动时自动检测所需依赖
- ✅ **自动安装**: 缺失依赖时自动安装，无需手动操作  
- ✅ **零配置**: 克隆后重启ComfyUI即可使用

### 🔄 安装过程

1. **克隆仓库** → 2. **重启ComfyUI** → 3. **自动安装依赖** → 4. **开始使用**

ComfyUI启动时，您会看到：
```
🔍 Advanced Prompt Processor 依赖检查...
✅ 所有核心依赖已就绪
```

或者：
```
🔍 Advanced Prompt Processor 依赖检查...
⚠️ 缺少依赖: numpy
🔧 正在安装 numpy>=1.19.0...
✅ numpy>=1.19.0 安装成功
✅ 所有核心依赖已就绪
```

### 🛠️ 如果遇到问题
```bash
# 手动安装依赖（如果自动安装失败）
pip install pandas requests numpy urllib3 openpyxl
```

插件采用**通用导入系统**，会在启动时自动：
- ✅ 检测并安装缺失依赖
- ✅ 尝试多种导入策略
- ✅ 兼容Windows/Linux/macOS
- ✅ 自动修复环境问题

## 🎯 核心节点快速上手

### 🧠 高级提示词处理器

**最重要的节点，建议先掌握！**

#### 基本使用
1. 在节点菜单找到 **AI → Advanced Prompt → 高级提示词处理器**
2. 连接节点到工作流：
   ```
   文本输入 → 高级提示词处理器 → CLIP文本编码器
   ```

#### 核心输入参数
- **danbooru_tags**: 输入标签，如 `1girl, long_hair, blue_eyes, smile`
- **drawing_theme**: 绘图主题，如 `beautiful anime portrait`
- **classification_mode**: 
  - `local_knowledge` - 本地分类（推荐，无需API）
  - `llm_classification` - AI在线分类（需要API）

#### 输出说明
- **final_prompt**: 📝 最终优化的提示词
- **enhanced_description**: 🧠 AI增强描述（需要API）
- **formatted_prompt**: 📋 纯文本格式提示词
- **classified_tags**: 📊 分类后的标签字典
- **processing_log**: 📄 处理日志和调试信息

### 🎲 随机元素选择器

#### 增强随机提示词选择器
1. 确保 `Random prompt` 文件夹中有Excel文件
2. 基本设置：
   - **excel_file_path**: `所长个人法典结构化fix.xlsx`
   - **selection_mode**: `random` 或 `by_category`
   - **prompt_count**: 选择数量（1-20）

#### 随机画师/角色选择器
1. **画师选择器**: 使用 `random画师.xlsx`
2. **角色选择器**: 使用 `random角色.xlsx`
3. 可启用**权重控制**和**避免重复**选项

### 🔗 Gelbooru标签提取器

#### 从图片URL提取标签
1. 输入Gelbooru图片URL
2. 选择站点（推荐 `safebooru.org`）
3. 设置输出格式和数量限制
4. 自动提取并分类标签

### 📄 XML提示词生成器

#### 生成结构化提示词
1. 选择输入类型：
   - `description` - 自然语言描述
   - `tags` - 标签列表
2. 配置API设置（同高级提示词处理器）
3. 生成XML格式的结构化提示词

## 🤖 AI功能配置

### 🔑 API密钥设置

如需使用AI增强功能，在对应节点配置：

#### OpenAI GPT
- **API地址**: `https://api.openai.com/v1/chat/completions`
- **API密钥**: 您的OpenAI API Key
- **模型**: `gpt-3.5-turbo` 或 `gpt-4`

#### Anthropic Claude  
- **API地址**: `https://api.anthropic.com/v1/messages`
- **API密钥**: 您的Anthropic API Key
- **模型**: `claude-3-sonnet-20240229`

#### Google Gemini
- **API地址**: `https://generativelanguage.googleapis.com`
- **API密钥**: 您的Google API Key
- **模型**: `gemini-1.5-flash` 或 `gemini-2.5-flash`

#### DeepSeek
- **API地址**: `https://api.deepseek.com/v1/chat/completions`
- **API密钥**: 您的DeepSeek API Key
- **模型**: `deepseek-chat`

### 💡 重要提示
- **API调用是可选的** - 不配置API也可以使用本地知识库功能
- **本地分类推荐** - 速度快，无成本，准确度高
- **AI增强可选** - 适合需要创意扩展的场景

## 🎨 实用工作流示例

### 🌟 推荐工作流 1：基础增强
```
KSampler种子 → 随机提示词选择器 → 高级提示词处理器 → CLIP文本编码器
```
- 适合：日常图片生成
- 特点：简单高效，结果多样

### 🎭 推荐工作流 2：角色组合
```
随机角色选择器 ↘
                  → 文本合并 → 高级提示词处理器 → CLIP文本编码器
随机画师选择器 ↗
```
- 适合：角色插画生成
- 特点：角色和画风组合

### 🖼️ 推荐工作流 3：参考重建
```
图片URL → Gelbooru提取器 → 高级提示词处理器 → CLIP文本编码器
```
- 适合：参考图片风格重现
- 特点：精确标签提取

### 🎯 推荐工作流 4：结构化创作
```
创意描述 → XML生成器 → 文本处理 → 高级提示词处理器 → CLIP文本编码器
```
- 适合：结构化创意实现
- 特点：从概念到实现

## ⚙️ 常用设置推荐

### 🎯 高级提示词处理器最佳设置
- **分类模式**: `local_knowledge`（速度快，无成本）
- **符号强化**: ✅ 开启（提升生成质量）
- **自定义标签**: 根据需要添加专属角色/画师

### 🎲 随机选择器最佳设置
- **自动随机种子**: ✅ 开启（确保每次不同）
- **避免重复**: ✅ 开启（多元素选择时）
- **权重控制**: 可选开启（需要强调时）

### 🔗 Gelbooru提取器最佳设置
- **站点选择**: `safebooru.org`（内容安全）
- **输出格式**: `classified`（按类别分类）
- **数量限制**: 50-100（平衡速度和完整性）

## 🔍 故障排除

### ❌ 常见问题

#### 1. 节点不显示
**解决方案**:
- 确认插件安装到正确目录
- 重启ComfyUI
- 检查控制台错误信息

#### 2. 依赖安装失败  
**解决方案**:
```bash
# 手动安装
pip install pandas requests numpy urllib3 openpyxl

# 或者使用清华源（中国用户）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas requests numpy urllib3 openpyxl
```

#### 3. Excel文件读取失败
**解决方案**:
- 确保文件在 `Random prompt` 文件夹中
- 检查文件格式是否为 `.xlsx`
- 确认文件未被Excel等程序占用

#### 4. API调用失败
**解决方案**:
- 验证API密钥格式正确
- 检查网络连接和防火墙
- 查看节点输出的处理日志
- 尝试使用本地分类模式

#### 5. 内存不足
**解决方案**:
- 关闭不必要的其他程序
- 减少同时运行的节点数量
- 清理ComfyUI缓存

### ⚡ 性能优化建议

#### 🚀 提升速度
- 首次运行后，知识库会自动缓存
- 使用本地分类模式（比API快10倍+）
- 避免频繁更换Excel文件

#### 💾 节省内存
- 多个节点实例会共享数据（v2.0优化）
- 定期重启ComfyUI清理缓存
- 关闭不用的浏览器标签页

## 📚 进阶学习

### 📖 推荐阅读顺序
1. **本指南** - 快速上手基础功能
2. **[终极用户指南](ULTIMATE_USER_GUIDE.md)** - 深入了解高级功能
3. **[更新日志](CHANGELOG.md)** - 了解最新改进

### 🎯 学习路径
1. **入门** (5分钟): 掌握高级提示词处理器基本使用
2. **进阶** (15分钟): 学会配置AI API和随机选择器
3. **高级** (30分钟): 组合多个节点创建复杂工作流
4. **专家** (1小时): 自定义知识库和优化设置

## 🎉 开始创作

**恭喜！您已经掌握了Advanced Prompt Processor的核心功能。**

### ✨ 下一步
1. 🎯 尝试基础工作流生成第一张图片
2. 🎲 实验不同的随机选择器组合
3. 🧠 配置AI API体验增强功能
4. 🔧 根据需要调整和优化设置

### 💡 创作建议
- **从简单开始**: 先用基础功能，再逐步添加复杂性
- **多次实验**: 随机元素让每次运行都有新惊喜
- **记录设置**: 发现好的配置组合记得保存
- **社区交流**: 在ComfyUI社区分享您的创作和经验

---

🎨 **让创意无限飞翔，用AI点亮艺术梦想！** ✨