# Tag knowledge 知识库说明

这个文件夹包含了分类存储的标签知识库，每个类别有独立的CSV文件进行管理。

## 文件结构

- `special.csv` - 人数和基本信息标签
- `characters.csv` - 角色名称标签
- `copyrights.csv` - 版权作品标签
- `artists.csv` - 画师名称标签
- `general.csv` - 通用描述标签
- `quality.csv` - 质量相关标签
- `meta.csv` - 元数据标签
- `rating.csv` - 内容评级标签

## 文件格式

每个CSV文件都包含以下列：
- `tag` - 标签名称（必需）
- `description` - 标签描述（可选）

## 使用方法

1. 在ComfyUI节点中，将`knowledge_base_folder`参数设置为`Tag knowledge`（或留空使用默认值）
2. 选择`classification_mode`为`local_knowledge`
3. 系统会自动读取该文件夹下的所有相关CSV文件

## 自定义管理

### 添加新标签
1. 打开对应类别的CSV文件（如角色标签打开`characters.csv`）
2. 在最后一行添加新的标签和描述
3. 保存文件

### 修改现有标签
1. 打开对应的CSV文件
2. 直接修改标签名称或描述
3. 保存文件

### 备选文件名
系统支持多种文件名，如果你想使用中文文件名：
- `人数标签.csv` 代替 `special.csv`
- `角色.csv` 代替 `characters.csv`
- `版权.csv` 代替 `copyrights.csv`
- `画师.csv` 代替 `artists.csv`
- `通用.csv` 代替 `general.csv`
- `质量.csv` 代替 `quality.csv`
- `元数据.csv` 代替 `meta.csv`
- `评级.csv` 代替 `rating.csv`

## 注意事项

1. **编码格式**：确保所有CSV文件保存为UTF-8编码
2. **列名要求**：每个文件必须包含`tag`列，`description`列为可选
3. **标签格式**：建议使用小写，多个单词用空格分隔
4. **自动重载**：修改文件后重新运行节点即可生效，无需重启ComfyUI

## 高级用法

### 纯文本格式
除了CSV格式，也支持纯文本格式（每行一个标签）：
```
1girl
1boy
2girls
2boys
```

### 混合模式
可以同时保留原有的`knowledge_base.csv`文件与分类文件，系统会自动合并所有标签。

### 团队协作
建议将此文件夹纳入版本控制系统（如Git），方便团队成员共同维护标签库。